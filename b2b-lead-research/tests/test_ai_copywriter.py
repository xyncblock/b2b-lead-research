"""
Tests for AI Copywriter enrichment module.
"""
import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from enrichment.ai_copywriter import AICopywriter


class TestAICopywriter:
    """Test AI outreach copy generation."""

    def test_init_without_api_key(self):
        """Should disable itself when no API key."""
        with patch.dict(os.environ, {}, clear=True):
            cw = AICopywriter()
            assert not cw.enabled

    def test_init_with_api_key(self):
        """Should enable when API key provided."""
        cw = AICopywriter(api_key="sk-test")
        assert cw.enabled
        assert cw.model == "gpt-4o-mini"

    def test_build_prompt_includes_business_name(self):
        """Prompt should include business name and issues."""
        cw = AICopywriter(api_key="sk-test")
        lead = {
            "business_name": "Test Boutique",
            "website_url": "https://test.com",
            "country": "UK",
            "ecommerce_platform": "Shopify",
            "website_quality_score": 35,
            "has_ssl": False,
            "mobile_friendly": False,
            "page_speed_score": 30,
            "improvement_opportunity": "missing SSL, not mobile-friendly",
        }
        prompt = cw._build_prompt(lead)
        assert "Test Boutique" in prompt
        assert "https://test.com" in prompt
        assert "missing SSL" in prompt

    def test_build_prompt_with_platform(self):
        """Should mention platform."""
        cw = AICopywriter(api_key="sk-test")
        lead = {
            "business_name": "Shop",
            "website_url": "https://shop.com",
            "ecommerce_platform": "WooCommerce",
            "has_ssl": True,
            "mobile_friendly": True,
        }
        prompt = cw._build_prompt(lead)
        assert "WooCommerce" in prompt

    def test_enrich_no_website(self):
        """Should mark no_website when URL missing."""
        cw = AICopywriter(api_key="sk-test")
        lead = {"business_name": "NoSite", "website_url": ""}
        result = cw.enrich(lead)
        assert result["ai_copy_status"] == "no_website"
        assert result["ai_outreach"] is None

    def test_enrich_disabled(self):
        """Should mark no_api_key when disabled."""
        cw = AICopywriter(api_key=None)
        lead = {"business_name": "Test", "website_url": "https://test.com"}
        result = cw.enrich(lead)
        assert result["ai_copy_status"] == "no_api_key"

    @patch("enrichment.ai_copywriter.requests.post")
    def test_call_llm_success(self, mock_post):
        """Should parse LLM JSON response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "subject": "Quick question about your site",
                "body": "Hi there,\\n\\nI noticed your site...\\n\\nBest, Alex",
                "pain_points": ["slow load time"],
                "talking_angle": "performance issues",
            })}}]
        }
        mock_post.return_value = mock_resp

        cw = AICopywriter(api_key="sk-test")
        result = cw._call_llm("test prompt")

        assert result is not None
        assert result["subject"] == "Quick question about your site"
        assert "slow load time" in result["pain_points"]
        assert result["model"] == "gpt-4o-mini"

    @patch("enrichment.ai_copywriter.requests.post")
    def test_call_llm_api_error(self, mock_post):
        """Should handle API errors gracefully."""
        mock_post.side_effect = Exception("Connection timeout")

        cw = AICopywriter(api_key="sk-test")
        result = cw._call_llm("test prompt")
        assert result is None

    @patch("enrichment.ai_copywriter.requests.post")
    def test_call_llm_openrouter_headers(self, mock_post):
        """Should add OpenRouter headers."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "subject": "S", "body": "B", "pain_points": [], "talking_angle": "A"
            })}}]
        }
        mock_post.return_value = mock_resp

        cw = AICopywriter(
            api_key="sk-test",
            api_base="https://openrouter.ai/api/v1",
        )
        cw._call_llm("prompt")

        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    @patch("enrichment.ai_copywriter.requests.post")
    def test_enrich_full_flow(self, mock_post):
        """Full enrich flow with mocked LLM."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "subject": "Your Shopify store",
                "body": "Hi\\n\\nI saw your store...\\n\\nBest, Alex",
                "pain_points": ["missing SSL"],
                "talking_angle": "security",
            })}}]
        }
        mock_post.return_value = mock_resp

        cw = AICopywriter(api_key="sk-test")
        lead = {
            "business_name": "Boutique",
            "website_url": "https://boutique.com",
            "country": "UK",
            "has_ssl": False,
            "mobile_friendly": True,
        }
        result = cw.enrich(lead)

        assert result["ai_copy_status"] == "generated"
        assert result["ai_outreach"]["subject"] == "Your Shopify store"
        assert "missing SSL" in result["ai_outreach"]["pain_points"]
