"""
Excel exporter for lead batches.
"""
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class ExcelExporter:
    """
    Export leads to Excel with proper formatting.
    Filename: b2b_ecom_research_{COUNTRY}_{BATCH#}_{YYYYMMDD}.xlsx
    """
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_batch(
        self,
        leads: List[Dict],
        country: str,
        batch_number: int = 1
    ) -> str:
        """
        Export a batch of leads to Excel.
        
        Returns:
            Path to generated file
        """
        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = f"b2b_ecom_research_{country}_{batch_number:03d}_{date_str}.xlsx"
        filepath = self.output_dir / filename
        
        # Prepare data
        df = pd.DataFrame(leads)
        
        # Ensure all columns exist
        expected_cols = [
            "record_id", "country", "business_name", "registered_name",
            "website_url", "source_url", "date_collected", "website_status",
            "website_quality_score", "ecommerce_platform", "business_email_generic",
            "business_email_named", "business_phone", "business_address",
            "google_maps_url", "google_rating", "google_review_count",
            "social_handles", "product_categories", "estimated_product_count",
            "has_ssl", "mobile_friendly", "page_speed_score", "last_content_update",
            "improvement_opportunity", "outreach_priority", "consent_status",
            "checkout_functional", "design_metrics",
        ]
        
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
        # Reorder
        df = df[[c for c in expected_cols if c in df.columns]]
        
        # Calculate stats
        hot_count = len(df[df["outreach_priority"] == "HOT"])
        warm_count = len(df[df["outreach_priority"] == "WARM"])
        cold_count = len(df[df["outreach_priority"] == "COLD"])
        avg_score = df["website_quality_score"].mean() if len(df) > 0 else 0
        
        # Platform breakdown
        platform_counts = df["ecommerce_platform"].value_counts().to_dict() if "ecommerce_platform" in df.columns else {}
        
        # Create Excel
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # All leads
            df.to_excel(writer, sheet_name="All Leads", index=False)
            
            # Priority sheets
            for priority in ["HOT", "WARM", "COLD"]:
                priority_df = df[df["outreach_priority"] == priority]
                if not priority_df.empty:
                    priority_df.to_excel(writer, sheet_name=f"{priority} Leads", index=False)
            
            # Summary sheet
            summary_data = {
                "Metric": [
                    "Export Date",
                    "Country",
                    "Total Records",
                    "HOT Leads",
                    "WARM Leads",
                    "COLD Leads",
                    "Average Quality Score",
                    "With Website",
                    "With Email",
                    "With Phone",
                    "SSL Enabled",
                    "Mobile Friendly",
                    "Compliance Framework",
                    "LIA Document",
                    "Data Sources",
                    "Date Range",
                ],
                "Value": [
                    datetime.utcnow().isoformat(),
                    country,
                    len(df),
                    hot_count,
                    warm_count,
                    cold_count,
                    round(avg_score, 1),
                    df["website_url"].notna().sum(),
                    (df["business_email_generic"].notna() | df["business_email_named"].notna()).sum(),
                    df["business_phone"].notna().sum(),
                    df["has_ssl"].sum() if "has_ssl" in df.columns else 0,
                    df["mobile_friendly"].sum() if "mobile_friendly" in df.columns else 0,
                    "GDPR Article 6(1)(f) - Legitimate Interest",
                    "LIA.md",
                    "Google Places API, Companies House API, Public Websites",
                    f"{df['date_collected'].min() if 'date_collected' in df.columns else 'N/A'} to {datetime.utcnow().isoformat()}",
                ],
            }
            
            # Add platform breakdown
            for platform, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                summary_data["Metric"].append(f"Platform: {platform}")
                summary_data["Value"].append(count)
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
        
        logger.info(f"Exported {len(leads)} leads to {filepath}")
        return str(filepath)
    
    def _format_sheet(self, writer, sheet_name: str, df: pd.DataFrame):
        """Apply formatting to worksheet."""
        worksheet = writer.sheets[sheet_name]
        
        # Auto-width columns
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            col_letter = chr(65 + idx) if idx < 26 else f"A{chr(65 + idx - 26)}"
            worksheet.column_dimensions[col_letter].width = min(max_length, 50)
        
        # Add filters
        worksheet.auto_filter.ref = worksheet.dimensions