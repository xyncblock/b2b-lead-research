"""Tests for enrichment modules."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from enrichment.website_analyzer import WebsiteEnricher
from enrichment.pagespeed import PageSpeedEnricher


class TestWebsiteEnricher:
    """Test website enricher."""
    
    def test_init(self):
        enricher = WebsiteEnricher()
        assert enricher.session is not None
    
    def test_check_mobile_true(self):
        from bs4 import BeautifulSoup
        enricher = WebsiteEnricher()
        soup = BeautifulSoup('<meta name="viewport" content="width=device-width">', "html.parser")
        assert enricher._check_mobile(soup) is True
    
    def test_check_mobile_false(self):
        from bs4 import BeautifulSoup
        enricher = WebsiteEnricher()
        soup = BeautifulSoup('<html></html>', "html.parser")
        assert enricher._check_mobile(soup) is False
    
    def test_detect_platform_shopify(self):
        enricher = WebsiteEnricher()
        html = "cdn.shopify.com"
        assert enricher._detect_platform(html) == "Shopify"
    
    def test_detect_platform_woocommerce(self):
        enricher = WebsiteEnricher()
        html = "wp-content/plugins/woocommerce"
        assert enricher._detect_platform(html) == "WooCommerce"
    
    def test_detect_platform_custom(self):
        enricher = WebsiteEnricher()
        html = "add to cart checkout basket"
        assert enricher._detect_platform(html) == "custom"
    
    def test_detect_platform_none(self):
        enricher = WebsiteEnricher()
        html = "just a blog"
        assert enricher._detect_platform(html) is None
    
    def test_extract_emails(self):
        enricher = WebsiteEnricher()
        html = "Contact us at info@test.com or sales@test.com"
        emails = enricher._extract_emails(html)
        assert "info@test.com" in emails
        assert "sales@test.com" in emails
    
    def test_extract_emails_filters_false_positives(self):
        enricher = WebsiteEnricher()
        html = "test@example.com image.png@domain.com"
        emails = enricher._extract_emails(html)
        assert "image.png@domain.com" not in emails
    
    def test_analyze_design(self):
        from bs4 import BeautifulSoup
        enricher = WebsiteEnricher()
        soup = BeautifulSoup(
            '<meta name="viewport" content="width=device-width">'
            '<script type="application/ld+json">{"@context":"schema.org"}</script>'
            '<link rel="icon" href="/favicon.ico">',
            "html.parser"
        )
        html = 'display: flex; <script type="application/ld+json">{"@context":"schema.org"}</script>'
        result = enricher._analyze_design(soup, html)
        assert result["has_viewport_meta"] is True
        assert result["has_schema_markup"] is True
        assert result["has_favicon"] is True
        assert result["has_modern_css"] is True
    
    def test_check_checkout_true(self):
        from bs4 import BeautifulSoup
        enricher = WebsiteEnricher()
        soup = BeautifulSoup("<html></html>", "html.parser")
        assert enricher._check_checkout(soup, "add to cart checkout") is True
    
    def test_enrich_no_website(self):
        enricher = WebsiteEnricher()
        lead = {"business_name": "Test"}
        result = enricher.enrich(lead)
        assert result["website_status"] == "no_website"
    
    @patch("enrichment.website_analyzer.requests.Session.get")
    def test_enrich_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://test.com"
        mock_response.text = '<html><meta name="viewport" content="width=device-width">' \
                            '<a href="https://facebook.com/testpage">FB</a>' \
                            'Contact: info@test.com</html>'
        mock_get.return_value = mock_response
        
        robots = Mock()
        robots.check_url.return_value = {"allowed": True}
        robots.get_delay.return_value = 0
        
        enricher = WebsiteEnricher(robots_checker=robots)
        lead = {"website_url": "test.com"}
        result = enricher.enrich(lead)
        assert result["website_status"] == "live"
        assert result["has_ssl"] is True
        assert result["mobile_friendly"] is True


class TestPageSpeedEnricher:
    """Test PageSpeed enricher."""
    
    def test_init(self):
        enricher = PageSpeedEnricher("test_key")
        assert enricher.api_key == "test_key"
    
    @patch("enrichment.pagespeed.requests.get")
    def test_get_score_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.85}
                }
            }
        }
        mock_get.return_value = mock_response
        
        enricher = PageSpeedEnricher("test_key")
        score = enricher.get_score("https://test.com")
        assert score == 85.0
    
    @patch("enrichment.pagespeed.requests.get")
    def test_get_score_rate_limit(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.content = b'{}'
        mock_get.return_value = mock_response
        
        enricher = PageSpeedEnricher("test_key")
        score = enricher.get_score("https://test.com")
        assert score is None
    
    def test_enrich_no_url(self):
        enricher = PageSpeedEnricher("test_key")
        lead = {"business_name": "Test"}
        result = enricher.enrich(lead)
        assert "page_speed_score" not in result
