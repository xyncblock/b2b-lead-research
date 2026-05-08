"""Tests for exporter modules."""
import pytest
import tempfile
import os
from datetime import datetime

from exporters.excel import ExcelExporter


class TestExcelExporter:
    """Test Excel exporter."""
    
    def test_init(self):
        exporter = ExcelExporter()
        assert exporter.output_dir.exists()
    
    def test_export_batch_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ExcelExporter(output_dir=tmpdir)
            path = exporter.export_batch([], "UK", 1)
            assert os.path.exists(path)
    
    def test_export_batch_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ExcelExporter(output_dir=tmpdir)
            leads = [
                {
                    "record_id": "123",
                    "country": "UK",
                    "business_name": "Test Co",
                    "website_url": "https://test.com",
                    "website_quality_score": 45.0,
                    "outreach_priority": "WARM",
                    "ecommerce_platform": "Shopify",
                }
            ]
            path = exporter.export_batch(leads, "UK", 1)
            assert os.path.exists(path)
            assert "UK_001_" in path
    
    def test_export_batch_creates_sheets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ExcelExporter(output_dir=tmpdir)
            leads = [
                {"record_id": "1", "outreach_priority": "HOT", "website_quality_score": 30},
                {"record_id": "2", "outreach_priority": "WARM", "website_quality_score": 50},
                {"record_id": "3", "outreach_priority": "COLD", "website_quality_score": 80},
            ]
            path = exporter.export_batch(leads, "UK", 1)
            
            import pandas as pd
            xl = pd.ExcelFile(path)
            assert "All Leads" in xl.sheet_names
            assert "Summary" in xl.sheet_names
    
    def test_export_batch_stats_correct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ExcelExporter(output_dir=tmpdir)
            leads = [
                {"record_id": "1", "outreach_priority": "HOT", "website_quality_score": 30, "website_url": "https://a.com"},
                {"record_id": "2", "outreach_priority": "HOT", "website_quality_score": 35, "website_url": "https://b.com"},
                {"record_id": "3", "outreach_priority": "WARM", "website_quality_score": 50, "website_url": "https://c.com"},
            ]
            path = exporter.export_batch(leads, "UK", 1)
            
            import pandas as pd
            summary = pd.read_excel(path, sheet_name="Summary")
            metrics = dict(zip(summary["Metric"], summary["Value"]))
            assert metrics["Total Records"] == 3
            assert metrics["HOT Leads"] == 2
            assert metrics["WARM Leads"] == 1
            assert metrics["Average Quality Score"] == 38.3
