"""Tests for compliance modules."""
import pytest
import tempfile
import os
from compliance.robots_checker import RobotsChecker
from compliance.audit_logger import AuditLogger
from compliance.consent_classifier import ConsentClassifier


class TestRobotsChecker:
    """Test robots.txt checker."""
    
    def test_init(self):
        checker = RobotsChecker()
        assert checker.default_delay == 3.0
        assert checker.cache_ttl == 3600
    
    def test_get_domain(self):
        checker = RobotsChecker()
        assert checker._get_domain("https://example.com/page") == "https://example.com"
        assert checker._get_domain("http://test.org/path") == "http://test.org"
    
    def test_parse_robots_empty(self):
        checker = RobotsChecker()
        rules = checker._parse_robots("")
        assert rules["allowed"] is True
        assert rules["crawl_delay"] == 3.0
    
    def test_parse_robots_disallow_all(self):
        checker = RobotsChecker()
        content = "User-agent: *\nDisallow: /"
        rules = checker._parse_robots(content)
        assert rules["allowed"] is False
        assert "/" in rules["disallowed_paths"]
    
    def test_parse_robots_crawl_delay(self):
        checker = RobotsChecker()
        content = "User-agent: *\nCrawl-delay: 5"
        rules = checker._parse_robots(content)
        assert rules["crawl_delay"] == 5.0
    
    def test_parse_robots_sitemap(self):
        checker = RobotsChecker()
        content = "User-agent: *\nSitemap: https://example.com/sitemap.xml"
        rules = checker._parse_robots(content)
        assert "https://example.com/sitemap.xml" in rules["sitemaps"]
    
    def test_evaluate_url_allowed(self):
        checker = RobotsChecker()
        rules = {"allowed": True, "crawl_delay": 3.0, "disallowed_paths": ["/admin/"]}
        result = checker._evaluate_url("https://example.com/page", rules, None)
        assert result["allowed"] is True
    
    def test_evaluate_url_disallowed(self):
        checker = RobotsChecker()
        rules = {"allowed": True, "crawl_delay": 3.0, "disallowed_paths": ["/admin/"]}
        result = checker._evaluate_url("https://example.com/admin/dashboard", rules, None)
        assert result["allowed"] is False
        assert "admin" in result["reason"]
    
    def test_cache_hit(self):
        checker = RobotsChecker()
        domain = "https://example.com"
        rules = {"allowed": True, "crawl_delay": 2.0, "disallowed_paths": []}
        from datetime import datetime
        checker._cache[domain] = {"rules": rules, "fetched_at": datetime.utcnow()}
        result = checker.check_url("https://example.com/page")
        assert result["allowed"] is True


class TestConsentClassifier:
    """Test email consent classifier."""
    
    def test_generic_email(self):
        classifier = ConsentClassifier()
        result = classifier.classify_email("info@example.com")
        assert result["type"] == "generic"
        assert result["pecr_safe"] is True
        assert result["consent_required"] is False
    
    def test_named_email(self):
        classifier = ConsentClassifier()
        result = classifier.classify_email("john.smith@example.com")
        assert result["type"] == "named"
        assert result["pecr_safe"] is False
        assert result["consent_required"] is True
    
    def test_role_email(self):
        classifier = ConsentClassifier()
        result = classifier.classify_email("ceo@example.com")
        assert result["type"] == "role"
        assert result["pecr_safe"] is False
    
    def test_invalid_email(self):
        classifier = ConsentClassifier()
        result = classifier.classify_email("")
        assert result["type"] == "unknown"
    
    def test_get_safe_email(self):
        classifier = ConsentClassifier()
        emails = ["john@example.com", "info@example.com", "sales@example.com"]
        safe = classifier.get_safe_email(emails)
        assert safe == "info@example.com"
    
    def test_consent_status_b2b(self):
        classifier = ConsentClassifier()
        status = classifier.get_consent_status("info@example.com", None)
        assert status == "b2b_legitimate_interest"
    
    def test_consent_status_required(self):
        classifier = ConsentClassifier()
        status = classifier.get_consent_status(None, "john@example.com")
        assert status == "consent_required"
    
    def test_consent_status_none(self):
        classifier = ConsentClassifier()
        status = classifier.get_consent_status(None, None)
        assert status == "do_not_contact"


class TestAuditLogger:
    """Test audit logger."""
    
    def test_init_creates_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            logger = AuditLogger(db_path)
            assert os.path.exists(db_path)
    
    def test_log_fetch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            logger = AuditLogger(db_path)
            logger.log_fetch(
                operation="test_op",
                url="https://example.com",
                domain="example.com",
                status_code=200,
                source_api="test",
            )
            
            records = logger.get_audit_for_record(None)
            assert len(records) == 1
            assert records[0]["operation"] == "test_op"
    
    def test_log_erasure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            logger = AuditLogger(db_path)
            logger.log_erasure("rec-123", "user_request", "user@example.com")
            # Should not raise
    
    def test_export_to_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            logger = AuditLogger(db_path)
            logger.log_fetch(
                operation="test",
                url="https://example.com",
                domain="example.com",
            )
            output = os.path.join(tmpdir, "export.json")
            path = logger.export_to_json(output)
            assert os.path.exists(path)
