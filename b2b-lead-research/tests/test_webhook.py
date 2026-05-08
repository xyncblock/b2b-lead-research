"""
Tests for Webhook/CRM exporter.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from exporters.webhook import WebhookExporter


class TestWebhookExporter:
    """Test webhook and CRM export functionality."""

    def test_init_disabled(self):
        """Should disable when no URL."""
        with patch.dict(os.environ, {}, clear=True):
            wh = WebhookExporter()
            assert not wh.enabled

    def test_init_enabled(self):
        """Should enable with URL."""
        wh = WebhookExporter(webhook_url="https://hooks.zapier.com/test")
        assert wh.enabled
        assert wh.mode == "generic"

    def test_transform_generic(self):
        """Should create correct generic payload."""
        wh = WebhookExporter(webhook_url="https://test.com")
        lead = {
            "record_id": "abc-123",
            "business_name": "Acme Inc",
            "website_url": "https://acme.com",
            "business_email_generic": "hello@acme.com",
            "business_phone": "+44 20 1234 5678",
            "country": "UK",
            "ecommerce_platform": "Shopify",
            "website_quality_score": 45,
            "outreach_priority": "WARM",
            "improvement_opportunity": "slow site",
            "social_handles": [{"platform": "instagram", "username": "acme"}],
            "ai_outreach": {
                "subject": "Quick question",
                "body": "Hi...",
            },
        }
        payload = wh._transform_generic(lead)
        assert payload["event"] == "lead.discovered"
        assert payload["lead"]["business_name"] == "Acme Inc"
        assert payload["lead"]["quality_score"] == 45
        assert payload["lead"]["ai_subject"] == "Quick question"

    def test_transform_generic_no_ai(self):
        """Should handle leads without AI copy."""
        wh = WebhookExporter(webhook_url="https://test.com")
        lead = {
            "business_name": "NoAI",
            "website_url": "https://noai.com",
        }
        payload = wh._transform_generic(lead)
        assert payload["lead"]["ai_subject"] is None

    def test_transform_hubspot_no_email(self):
        """Should skip HubSpot if no email."""
        wh = WebhookExporter(webhook_url="https://test.com", mode="hubspot")
        lead = {"business_name": "NoEmail", "website_url": "https://test.com"}
        payload = wh._transform_hubspot(lead)
        assert payload is None

    def test_transform_hubspot_with_email(self):
        """Should create HubSpot payload."""
        wh = WebhookExporter(webhook_url="https://test.com", mode="hubspot")
        lead = {
            "business_name": "Acme",
            "website_url": "https://acme.com",
            "business_email_generic": "info@acme.com",
            "business_phone": "+1 555-1234",
            "country": "US",
            "website_quality_score": 55,
            "outreach_priority": "WARM",
            "ecommerce_platform": "WooCommerce",
        }
        payload = wh._transform_hubspot(lead)
        assert payload["properties"]["email"] == "info@acme.com"
        assert payload["properties"]["lifecyclestage"] == "lead"
        assert payload["properties"]["lead_priority"] == "WARM"

    def test_transform_pipedrive(self):
        """Should create Pipedrive payload."""
        wh = WebhookExporter(webhook_url="https://test.com", mode="pipedrive")
        lead = {
            "business_name": "Acme",
            "business_email_generic": "info@acme.com",
            "business_phone": "+1 555-1234",
            "website_quality_score": 40,
            "outreach_priority": "HOT",
            "ecommerce_platform": "Shopify",
            "improvement_opportunity": "slow loading",
        }
        payload = wh._transform_pipedrive(lead)
        assert payload["person"]["name"] == "Acme"
        assert len(payload["person"]["email"]) == 1
        assert payload["note"] is not None
        assert "slow loading" in payload["note"]["content"]

    @patch("exporters.webhook.requests.post")
    def test_send_generic_success(self, mock_post):
        """Should return True on 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()
        mock_post.return_value = mock_resp

        wh = WebhookExporter(webhook_url="https://hooks.zapier.com/test")
        result = wh._send_generic({"test": "data"})
        assert result is True

    @patch("exporters.webhook.requests.post")
    def test_send_generic_failure(self, mock_post):
        """Should return False on error."""
        mock_post.side_effect = Exception("Timeout")

        wh = WebhookExporter(webhook_url="https://hooks.zapier.com/test")
        result = wh._send_generic({"test": "data"})
        assert result is False

    @patch("exporters.webhook.requests.post")
    def test_send_hubspot_409_ok(self, mock_post):
        """Should treat 409 (contact exists) as success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.raise_for_status = Mock(side_effect=Exception("Conflict"))
        mock_post.return_value = mock_resp

        wh = WebhookExporter(webhook_url="https://test.com", mode="hubspot")
        result = wh._send_hubspot({"properties": {}})
        assert result is True

    @patch("exporters.webhook.requests.post")
    def test_send_pipedrive_with_note(self, mock_post):
        """Should create person then add note."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"data": {"id": 12345}}
        mock_post.return_value = mock_resp

        wh = WebhookExporter(webhook_url="https://test.com", mode="pipedrive")
        payload = {
            "person": {"name": "Acme", "email": []},
            "note": {"content": "Test note"},
        }
        result = wh._send_pipedrive(payload)
        assert result is True
        # Should have made 2 calls (person + note)
        assert mock_post.call_count == 2

    @patch("exporters.webhook.requests.post")
    def test_send_lead_generic(self, mock_post):
        """Full send_lead flow."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()
        mock_post.return_value = mock_resp

        wh = WebhookExporter(webhook_url="https://hooks.zapier.com/test", mode="generic")
        lead = {
            "record_id": "abc",
            "business_name": "Test",
            "website_url": "https://test.com",
        }
        result = wh.send_lead(lead)
        assert result is True

    def test_export_batch_disabled(self):
        """Should skip all when disabled."""
        wh = WebhookExporter(webhook_url=None)
        leads = [{"record_id": "1"}, {"record_id": "2"}]
        stats = wh.export_batch(leads)
        assert stats == {"sent": 0, "failed": 0, "skipped": 2}

    @patch("exporters.webhook.requests.post")
    def test_export_batch_mixed(self, mock_post):
        """Should track sent/failed correctly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()
        mock_post.return_value = mock_resp

        wh = WebhookExporter(webhook_url="https://test.com", mode="generic")
        leads = [
            {"record_id": "1", "business_name": "A", "website_url": "https://a.com"},
            {"record_id": "2", "business_name": "B", "website_url": "https://b.com"},
        ]
        stats = wh.export_batch(leads)
        assert stats["sent"] == 2
        assert stats["failed"] == 0
