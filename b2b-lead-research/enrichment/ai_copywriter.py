"""
AI Outreach Copy Generator
Generates personalized cold outreach emails for each lead using LLM APIs.
Supports OpenAI, OpenRouter, or any OpenAI-compatible endpoint.
"""
import os
import re
import json
import logging
from typing import Dict, Optional
from datetime import datetime

import requests

from compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class AICopywriter:
    """
    Generate personalized outreach copy for leads.

    Uses an LLM to craft context-aware cold emails based on:
    - Website quality analysis
    - Detected pain points
    - E-commerce platform
    - Improvement opportunities

    Config via env:
        OPENAI_API_KEY or OPENROUTER_API_KEY
        LLM_API_BASE (optional, defaults to OpenAI)
        LLM_MODEL (default: gpt-4o-mini)
    """

    SYSTEM_PROMPT = """You are a senior B2B sales copywriter specializing in e-commerce and web development services.
Your job is to write a short, personalized cold outreach email to a business owner whose website has quality issues.

Rules:
- Keep it under 120 words
- Mention 1-2 specific issues you noticed on their site
- Be friendly, not pushy
- Include a soft call-to-action (e.g., "happy to chat", "free audit")
- Never be generic — reference their actual business name and specific problems
- Use UK/AU English spelling if the business is in UK/AU
- Do NOT mention their score number
- Do NOT use overly salesy language like "revolutionize" or "game-changing"
- Sign off as a real person ("Best, [Name]") — use "Alex" as the default name

Output ONLY valid JSON in this exact format:
{
  "subject": "Short, curiosity-driven subject line",
  "body": "The email body with \\n for line breaks",
  "pain_points": ["specific issue 1", "specific issue 2"],
  "talking_angle": "One-sentence summary of the angle taken"
}"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.api_base = api_base or os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.audit = audit_logger or AuditLogger()
        self.enabled = bool(self.api_key)

    def _build_prompt(self, lead: Dict) -> str:
        """Build the user prompt from lead data."""
        name = lead.get("business_name", "their business")
        url = lead.get("website_url", "")
        platform = lead.get("ecommerce_platform", "unknown")
        score = lead.get("website_quality_score", 50)
        issues = lead.get("improvement_opportunity", "")
        has_ssl = lead.get("has_ssl", True)
        mobile = lead.get("mobile_friendly", True)
        speed = lead.get("page_speed_score")
        country = lead.get("country", "UK")
        social = lead.get("social_handles", [])
        products = lead.get("estimated_product_count")

        facts = []
        if not has_ssl:
            facts.append("missing SSL certificate")
        if not mobile:
            facts.append("not mobile-responsive")
        if speed is not None and speed < 50:
            facts.append(f"very slow page load ({speed}/100)")
        elif speed is not None and speed < 70:
            facts.append(f"slow page load ({speed}/100)")
        if platform in ["custom", None]:
            facts.append("running on a custom/old platform")
        elif platform:
            facts.append(f"running on {platform}")
        if not social:
            facts.append("no social media presence detected")
        if products is not None and products > 20:
            facts.append(f"large catalog (~{products} products)")

        facts_str = "; ".join(facts) if facts else "general website quality issues"

        return f"""Business: {name}
Website: {url}
Country: {country}
Platform: {platform}
Quality issues: {issues}
Specific facts: {facts_str}

Write a personalized cold outreach email for this business."""

    def _call_llm(self, prompt: str) -> Optional[Dict]:
        """Call the LLM API and return parsed JSON."""
        if not self.enabled:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # OpenRouter needs extra header
        if "openrouter" in self.api_base:
            headers["HTTP-Referer"] = "https://b2b-lead-research.local"
            headers["X-Title"] = "B2B Lead Research"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }

        start = datetime.utcnow()
        try:
            resp = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            self.audit.log_fetch(
                operation="ai_copywriter",
                url=f"{self.api_base}/chat/completions",
                domain=self.api_base.split("//")[-1].split("/")[0],
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="llm",
                metadata={"model": self.model, "prompt_tokens": len(prompt) // 4},
            )

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON
            parsed = json.loads(content)
            return {
                "subject": parsed.get("subject", "").strip(),
                "body": parsed.get("body", "").strip(),
                "pain_points": parsed.get("pain_points", []),
                "talking_angle": parsed.get("talking_angle", "").strip(),
                "generated_at": datetime.utcnow().isoformat(),
                "model": self.model,
            }

        except requests.RequestException as e:
            self.audit.log_fetch(
                operation="ai_copywriter",
                url=f"{self.api_base}/chat/completions",
                domain=self.api_base.split("//")[-1].split("/")[0],
                error=str(e),
                source_api="llm",
            )
            logger.warning(f"LLM call failed: {e}")
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"LLM response parsing failed: {e}")
            return None

    def enrich(self, lead: Dict) -> Dict:
        """Generate outreach copy for a lead."""
        if not self.enabled:
            lead["ai_outreach"] = None
            lead["ai_copy_status"] = "no_api_key"
            return lead

        # Only generate for leads with websites
        if not lead.get("website_url"):
            lead["ai_outreach"] = None
            lead["ai_copy_status"] = "no_website"
            return lead

        prompt = self._build_prompt(lead)
        result = self._call_llm(prompt)

        if result:
            lead["ai_outreach"] = result
            lead["ai_copy_status"] = "generated"
        else:
            lead["ai_outreach"] = None
            lead["ai_copy_status"] = "generation_failed"

        return lead
