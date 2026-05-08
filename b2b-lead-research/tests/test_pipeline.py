"""Tests for pipeline."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pipeline import LeadPipeline


class TestLeadPipeline:
    """Test lead pipeline."""
    
    def test_init_no_keys(self):
        pipeline = LeadPipeline()
        assert pipeline.places is None
        assert pipeline.companies_house is None
        assert pipeline.pagespeed is None
        assert pipeline.telegram is None
    
    @patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "test"})
    def test_init_with_places_key(self):
        pipeline = LeadPipeline()
        assert pipeline.places is not None
    
    def test_discover_uk_no_collectors(self):
        pipeline = LeadPipeline()
        leads = pipeline.discover_uk(max_results=10)
        assert leads == []
    
    def test_enrich_leads_empty(self):
        pipeline = LeadPipeline()
        result = pipeline.enrich_leads([])
        assert result == []
    
    def test_enrich_leads_no_website(self):
        pipeline = LeadPipeline()
        leads = [{"business_name": "Test"}]
        result = pipeline.enrich_leads(leads)
        assert len(result) == 1
        assert result[0]["website_status"] == "no_website"
    
    def test_score_leads_empty(self):
        pipeline = LeadPipeline()
        result = pipeline.score_leads([])
        assert result == []
    
    def test_score_leads(self):
        pipeline = LeadPipeline()
        leads = [{"business_name": "Test", "has_ssl": True, "mobile_friendly": True}]
        result = pipeline.score_leads(leads)
        assert "website_quality_score" in result[0]
        assert "outreach_priority" in result[0]
        assert "improvement_opportunity" in result[0]
    
    def test_score_leads_handles_errors(self):
        pipeline = LeadPipeline()
        leads = [{"business_name": "Test"}]
        result = pipeline.score_leads(leads)
        assert result[0]["website_quality_score"] == 50
        assert result[0]["outreach_priority"] == "WARM"
    
    def test_process_batch_unsupported_country(self):
        pipeline = LeadPipeline()
        result = pipeline.process_batch(country="US")
        assert result is None
    
    def test_process_batch_no_leads(self):
        pipeline = LeadPipeline()
        result = pipeline.process_batch(country="UK")
        assert result is None
    
    @patch("pipeline.LeadPipeline.discover_uk")
    @patch("pipeline.LeadPipeline.enrich_leads")
    @patch("pipeline.LeadPipeline.score_leads")
    def test_process_batch_success(self, mock_score, mock_enrich, mock_discover):
        mock_discover.return_value = [{"business_name": "Test"}]
        mock_enrich.return_value = [{"business_name": "Test", "website_url": "https://test.com"}]
        mock_score.return_value = [{
            "business_name": "Test",
            "website_quality_score": 45,
            "outreach_priority": "WARM",
            "improvement_opportunity": "Test opp",
        }]
        
        pipeline = LeadPipeline()
        result = pipeline.process_batch(country="UK", batch_size=1)
        assert result is not None
        assert result.endswith(".xlsx")
