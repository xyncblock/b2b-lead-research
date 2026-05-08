"""Tests for scoring engine."""
import pytest
from datetime import datetime, timedelta
from scoring.engine import ScoringEngine


class TestScoringEngine:
    """Test scoring engine."""
    
    def test_init(self):
        engine = ScoringEngine()
        assert sum(engine.WEIGHTS.values()) == 100
    
    def test_score_ssl_true(self):
        engine = ScoringEngine()
        assert engine.score_ssl(True) == 10
    
    def test_score_ssl_false(self):
        engine = ScoringEngine()
        assert engine.score_ssl(False) == 0
    
    def test_score_ssl_none(self):
        engine = ScoringEngine()
        assert engine.score_ssl(None) == 5
    
    def test_score_mobile_true(self):
        engine = ScoringEngine()
        assert engine.score_mobile(True) == 15
    
    def test_score_mobile_false(self):
        engine = ScoringEngine()
        assert engine.score_mobile(False) == 0
    
    def test_score_page_speed_excellent(self):
        engine = ScoringEngine()
        assert engine.score_page_speed(95) == 15
    
    def test_score_page_speed_good(self):
        engine = ScoringEngine()
        assert engine.score_page_speed(75) == 10
    
    def test_score_page_speed_poor(self):
        engine = ScoringEngine()
        assert engine.score_page_speed(30) == 0
    
    def test_score_design_full(self):
        engine = ScoringEngine()
        metrics = {
            "has_viewport_meta": True,
            "has_schema_markup": True,
            "has_favicon": True,
            "has_modern_css": True,
            "has_flash": False,
            "has_tables_for_layout": False,
        }
        assert engine.score_design(metrics) == 15
    
    def test_score_design_none(self):
        engine = ScoringEngine()
        assert engine.score_design(None) == 7.5
    
    def test_score_social_many(self):
        engine = ScoringEngine()
        handles = [{"platform": "fb"}, {"platform": "ig"}, {"platform": "tw"}]
        assert engine.score_social(handles) == 10
    
    def test_score_social_none(self):
        engine = ScoringEngine()
        assert engine.score_social([]) == 0
    
    def test_score_checkout_true(self):
        engine = ScoringEngine()
        assert engine.score_checkout(True) == 15
    
    def test_score_content_freshness_recent(self):
        engine = ScoringEngine()
        recent = datetime.utcnow() - timedelta(days=10)
        assert engine.score_content_freshness(recent) == 10
    
    def test_score_content_freshness_old(self):
        engine = ScoringEngine()
        old = datetime.utcnow() - timedelta(days=200)
        assert engine.score_content_freshness(old) == 0
    
    def test_score_domain_email_professional(self):
        engine = ScoringEngine()
        assert engine.score_domain_email("info@example.com") == 10
    
    def test_score_domain_email_free(self):
        engine = ScoringEngine()
        assert engine.score_domain_email("shop@gmail.com") == 3
    
    def test_calculate_full(self):
        engine = ScoringEngine()
        lead = {
            "has_ssl": True,
            "mobile_friendly": True,
            "page_speed_score": 85,
            "design_metrics": {"has_viewport_meta": True, "has_schema_markup": True, 
                              "has_favicon": True, "has_modern_css": True,
                              "has_flash": False, "has_tables_for_layout": False},
            "social_handles": [{"p": "fb"}, {"p": "ig"}, {"p": "tw"}],
            "checkout_functional": True,
            "last_content_update": datetime.utcnow(),
            "business_email_generic": "info@example.com",
        }
        score = engine.calculate(lead)
        assert score == 100
    
    def test_determine_priority_hot(self):
        engine = ScoringEngine()
        lead = {"google_review_count": 20, "google_rating": 4.5, 
                "social_handles": [{}, {}], "estimated_product_count": 10,
                "business_phone": "123", "business_email_generic": "info@test.com"}
        assert engine.determine_priority(30, lead) == "HOT"
    
    def test_determine_priority_warm(self):
        engine = ScoringEngine()
        assert engine.determine_priority(50, {}) == "WARM"
    
    def test_determine_priority_cold(self):
        engine = ScoringEngine()
        assert engine.determine_priority(80, {}) == "COLD"
    
    def test_has_revenue_signals_true(self):
        engine = ScoringEngine()
        lead = {
            "google_review_count": 20,
            "google_rating": 4.5,
            "social_handles": [{}, {}, {}],
            "estimated_product_count": 10,
            "business_phone": "123",
            "business_email_generic": "info@test.com",
        }
        assert engine._has_revenue_signals(lead) is True
    
    def test_has_revenue_signals_false(self):
        engine = ScoringEngine()
        assert engine._has_revenue_signals({}) is False
    
    def test_generate_opportunity_issues(self):
        engine = ScoringEngine()
        lead = {"has_ssl": False, "mobile_friendly": False}
        opp = engine.generate_opportunity(lead)
        assert "missing SSL" in opp
        assert "not mobile-friendly" in opp
    
    def test_generate_opportunity_none(self):
        engine = ScoringEngine()
        lead = {"has_ssl": True, "mobile_friendly": True, "page_speed_score": 80,
                "checkout_functional": True, "ecommerce_platform": "Shopify",
                "social_handles": [{"p": "fb"}]}
        opp = engine.generate_opportunity(lead)
        assert "Minor UX" in opp or "rebuild recommended" in opp
