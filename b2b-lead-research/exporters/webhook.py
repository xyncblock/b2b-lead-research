"""
Webhook/CRM Exporter
Push leads to external systems via HTTP POST.
Supports generic webhooks, HubSpot, Pipedrive, Zapier, Make.com.
"""
import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

import requests

from compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class WebhookExporter:
    """
    Export leads to external CRMs and automation tools via webhooks.

    Supported formats:
      - generic   → Raw JSON array POST
      - hubspot   → HubSpot Contacts API v3
      - pipedrive → Pipedrive Persons + Deals
      - zapier    → Zapier Webhooks (raw payload)
      - make      → Make.com Webhooks

    Env vars:
        WEBHOOK_URL        → Required for all modes
        WEBHOOK_MODE       → generic | hubspot | pipedrive | zapier | make
        WEBHOOK_AUTH_TOKEN → Optional Bearer token or API key
        HUBSPOT_API_KEY    → Required for hubspot mode
        PIPEDRIVE_API_KEY  → Required for pipedrive mode
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        mode: Optional[str] = None,
        auth_token: Optional[str] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.webhook_url = webhook_url or os.getenv("WEBHOOK_URL", "")
        self.mode = (mode or os.getenv("WEBHOOK_MODE", "generic")).lower().strip()
        self.auth_token = auth_token or os.getenv("WEBHOOK_AUTH_TOKEN", "")
        self.audit = audit_logger or AuditLogger()
        self.enabled = bool(self.webhook_url)

        # CRM-specific keys
        self.hubspot_key = os.getenv("HUBSPOT_API_KEY", "")
        self.pipedrive_key = os.getenv("PIPEDRIVE_API_KEY", "")

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _transform_generic(self, lead: Dict) -> Dict:
        """Raw lead payload for generic webhooks."""
        return {
            "event": "lead.discovered",
            "timestamp": datetime.utcnow().isoformat(),
            "lead": {
                "record_id": lead.get("record_id"),
                "business_name": lead.get("business_name"),
                "website_url": lead.get("website_url"),
                "business_email": lead.get("business_email_generic") or lead.get("business_email_named"),
                "business_phone": lead.get("business_phone"),
                "business_address": lead.get("business_address"),
                "country": lead.get("country"),
                "platform": lead.get("ecommerce_platform"),
                "quality_score": lead.get("website_quality_score"),
                "priority": lead.get("outreach_priority"),
                "improvement_opportunity": lead.get("improvement_opportunity"),
                "social_handles": lead.get("social_handles", []),
                "ai_subject": lead.get("ai_outreach", {}).get("subject") if lead.get("ai_outreach") else None,
                "ai_body": lead.get("ai_outreach", {}).get("body") if lead.get("ai_outreach") else None,
            },
        }

    def _transform_hubspot(self, lead: Dict) -> Dict:
        """HubSpot Contacts API v3 payload."""
        email = lead.get("business_email_generic") or lead.get("business_email_named")
        if not email:
            return None  # HubSpot needs email

        properties = {
            "email": email,
            "company": lead.get("business_name", ""),
            "website": lead.get("website_url", ""),
            "phone": lead.get("business_phone", ""),
            "address": lead.get("business_address", ""),
            "country": lead.get("country", ""),
            "lifecyclestage": "lead",
            "lead_priority": lead.get("outreach_priority", "WARM"),
            "website_quality_score": str(lead.get("website_quality_score", "")),
            "ecommerce_platform": lead.get("ecommerce_platform", ""),
            "improvement_opportunity": lead.get("improvement_opportunity", ""),
        }

        return {
            "properties": {k: v for k, v in properties.items() if v},
        }

    def _transform_pipedrive(self, lead: Dict) -> Dict:
        """Pipedrive Person + Note payload."""
        email = lead.get("business_email_generic") or lead.get("business_email_named")

        person = {
            "name": lead.get("business_name", "Unknown"),
            "email": [{"value": email, "primary": True}] if email else [],
            "phone": [{"value": lead.get("business_phone", ""), "primary": True}] if lead.get("business_phone") else [],
            "visible_to": 3,
            "d1a8d1c8b8d1e1f1a1b1c1d1e1f1a1b": lead.get("website_url", ""),  # custom field placeholder
        }

        note = None
        if lead.get("improvement_opportunity"):
            note = {
                "content": f"<b>Quality Score:</b> {lead.get('website_quality_score')}/100<br>"
                           f"<b>Priority:</b> {lead.get('outreach_priority')}<br>"
                           f"<b>Platform:</b> {lead.get('ecommerce_platform')}<br>"
                           f"<b>Opportunity:</b> {lead.get('improvement_opportunity')}",
            }

        return {"person": person, "note": note}

    def _send_generic(self, payload: Dict) -> bool:
        """Send to generic webhook."""
        try:
            resp = requests.post(
                self.webhook_url,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning(f"Webhook failed: {e}")
            return False

    def _send_hubspot(self, payload: Dict) -> bool:
        """Send to HubSpot Contacts API."""
        url = f"https://api.hubapi.com/crm/v3/objects/contacts?hapikey={self.hubspot_key}"
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 409:  # Contact exists — that's ok
                return True
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning(f"HubSpot push failed: {e}")
            return False

    def _send_pipedrive(self, payload: Dict) -> bool:
        """Send to Pipedrive API."""
        person = payload.get("person")
        note = payload.get("note")

        url = f"https://api.pipedrive.com/v1/persons?api_token={self.pipedrive_key}"
        try:
            resp = requests.post(url, json=person, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            person_id = data.get("data", {}).get("id")

            # Add note if we got a person
            if person_id and note:
                note_url = f"https://api.pipedrive.com/v1/notes?api_token={self.pipedrive_key}"
                note["person_id"] = person_id
                requests.post(note_url, json=note, timeout=30)

            return True
        except requests.RequestException as e:
            logger.warning(f"Pipedrive push failed: {e}")
            return False

    def send_lead(self, lead: Dict) -> bool:
        """Send a single lead to the configured webhook/CRM."""
        if not self.enabled:
            return False

        # Transform based on mode
        if self.mode == "hubspot":
            payload = self._transform_hubspot(lead)
            if payload is None:
                return False
            success = self._send_hubspot(payload)
        elif self.mode == "pipedrive":
            payload = self._transform_pipedrive(lead)
            success = self._send_pipedrive(payload)
        else:
            payload = self._transform_generic(lead)
            success = self._send_generic(payload)

        # Audit log
        self.audit.log_fetch(
            operation=f"webhook_{self.mode}",
            url=self.webhook_url,
            domain=self.webhook_url.split("//")[-1].split("/")[0] if self.webhook_url else "",
            status_code=200 if success else 500,
            response_size=0,
            source_api="webhook",
            metadata={
                "mode": self.mode,
                "lead_id": lead.get("record_id"),
                "business_name": lead.get("business_name"),
                "success": success,
            },
        )

        return success

    def export_batch(self, leads: List[Dict]) -> Dict[str, int]:
        """
        Export a batch of leads.

        Returns:
            {"sent": N, "failed": N, "skipped": N}
        """
        if not self.enabled:
            logger.info("Webhook exporter disabled (no WEBHOOK_URL)")
            return {"sent": 0, "failed": 0, "skipped": len(leads)}

        stats = {"sent": 0, "failed": 0, "skipped": 0}

        for lead in leads:
            # Skip leads without actionable data
            if self.mode == "hubspot" and not (lead.get("business_email_generic") or lead.get("business_email_named")):
                stats["skipped"] += 1
                continue

            if self.send_lead(lead):
                stats["sent"] += 1
            else:
                stats["failed"] += 1

        logger.info(f"Webhook export complete: {stats}")
        return stats
