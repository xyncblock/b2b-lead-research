"""Tests for discovery modules."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from discovery.google_places import GooglePlacesCollector
from discovery.companies_house import CompaniesHouseCollector


class TestGooglePlacesCollector:
    """Test Google Places collector."""
    
    def test_init_with_key(self):
        collector = GooglePlacesCollector(api_key="test_key")
        assert collector.api_key == "test_key"
        assert collector.mode == "api"
    
    def test_init_scrape_mode(self):
        collector = GooglePlacesCollector(mode="scrape")
        assert collector.mode == "scrape"
    
    def test_should_use_api(self):
        collector = GooglePlacesCollector(api_key="test", mode="api")
        assert collector._should_use_api() is True
    
    def test_should_use_scrape(self):
        collector = GooglePlacesCollector(mode="scrape")
        assert collector._should_use_scrape() is True
    
    def test_api_available(self):
        collector = GooglePlacesCollector(api_key="test")
        assert collector._api_available() is True
    
    def test_api_not_available(self):
        collector = GooglePlacesCollector()
        assert collector._api_available() is False
    
    @patch("discovery.google_places.requests.Session")
    def test_make_request_success(self, mock_session_class):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "OK", "results": []}'
        mock_response.json.return_value = {"status": "OK", "results": []}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        collector = GooglePlacesCollector(api_key="test")
        result = collector._make_request("textsearch", {"query": "test"})
        assert result is not None
        assert result["status"] == "OK"
    
    @patch("discovery.google_places.requests.Session")
    def test_make_request_error_status(self, mock_session_class):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "REQUEST_DENIED"}'
        mock_response.json.return_value = {"status": "REQUEST_DENIED"}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        collector = GooglePlacesCollector(api_key="test")
        result = collector._make_request("textsearch", {})
        assert result is None
    
    def test_to_lead(self):
        collector = GooglePlacesCollector(api_key="test")
        place_data = {
            "name": "Test Shop",
            "formatted_address": "123 Test St",
            "formatted_phone_number": "+44 123",
            "website": "https://test.com",
            "url": "https://maps.google.com/test",
            "rating": 4.5,
            "user_ratings_total": 100,
            "place_id": "ChIJ123",
            "types": ["store"],
            "business_status": "OPERATIONAL",
            "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
        }
        lead = collector.to_lead(place_data, "UK")
        assert lead["business_name"] == "Test Shop"
        assert lead["country"] == "UK"
        assert lead["google_rating"] == 4.5
        assert lead["latitude"] == 51.5
    
    def test_extract_place_ids(self):
        collector = GooglePlacesCollector()
        html = '<script>"place_id":"ChIJN1t_tDeuEmsRUsoyG83frY4"</script>'
        ids = collector._extract_place_ids(html)
        assert len(ids) == 1
        assert ids[0] == "ChIJN1t_tDeuEmsRUsoyG83frY4"
    
    def test_parse_place_html(self):
        collector = GooglePlacesCollector()
        html = '<meta property="og:title" content="Test Business">' \
               '<title>Test - Google Maps</title>' \
               '"address":"123 Test St"' \
               '"phone":"+44 123"' \
               '"website":"https://test.com"' \
               '"rating":4.5' \
               '"review_count":42'
        result = collector._parse_place_html(html, "ChIJ123", "gb", "https://maps.google.com")
        assert result["business_name"] == "Test Business"
        assert result["business_address"] == "123 Test St"
        assert result["business_phone"] == "+44 123"
        assert result["website_url"] == "https://test.com"
        assert result["google_rating"] == 4.5
        assert result["google_review_count"] == 42


class TestCompaniesHouseCollector:
    """Test Companies House collector."""
    
    def test_init(self):
        collector = CompaniesHouseCollector("test_key")
        assert collector.api_key == "test_key"
        assert "Authorization" in collector.session.headers
    
    def test_to_lead(self):
        collector = CompaniesHouseCollector("test_key")
        company_data = {
            "company_name": "Test Ltd",
            "company_number": "12345678",
            "company_status": "active",
            "type": "ltd",
            "registered_office_address": {
                "address_line_1": "123 Street",
                "locality": "London",
                "postal_code": "SW1A 1AA",
            },
            "date_of_creation": "2020-01-01",
            "sic_codes": ["47910"],
        }
        lead = collector.to_lead(company_data)
        assert lead["business_name"] == "Test Ltd"
        assert lead["company_number"] == "12345678"
        assert lead["country"] == "UK"
        assert "123 Street" in lead["business_address"]
