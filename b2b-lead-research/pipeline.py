"""
Main pipeline orchestrator.
"""
import os
import sys
import time
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from dotenv import load_dotenv

# Load env
load_dotenv()

from compliance import RobotsChecker, AuditLogger, ConsentClassifier
from discovery import GooglePlacesCollector, CompaniesHouseCollector, BingSearchCollector
from enrichment import WebsiteEnricher, PageSpeedEnricher, AICopywriter
from scoring import ScoringEngine
from exporters import ExcelExporter, TelegramDelivery, WebhookExporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LeadPipeline:
    """
    Main pipeline: discover → enrich → score → export → deliver.
    """
    
    def __init__(self):
        # Compliance
        self.robots = RobotsChecker()
        self.audit = AuditLogger()
        self.consent = ConsentClassifier()
        
        # Discovery (init if API keys available)
        self.places = None
        self.companies_house = None
        
        places_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if places_key:
            self.places = GooglePlacesCollector(api_key=places_key, audit_logger=self.audit)
        
        ch_key = os.getenv("COMPANIES_HOUSE_API_KEY")
        if ch_key:
            self.companies_house = CompaniesHouseCollector(ch_key, self.audit)
        
        # Enrichment
        self.website = WebsiteEnricher(self.robots, self.audit, self.consent)
        
        pagespeed_key = os.getenv("GOOGLE_PAGESPEED_API_KEY")
        if pagespeed_key:
            self.pagespeed = PageSpeedEnricher(pagespeed_key, self.audit)
        else:
            self.pagespeed = None
        
        # Scoring
        self.scorer = ScoringEngine()
        
        # Export
        self.exporter = ExcelExporter()
        
        # Telegram
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat:
            self.telegram = TelegramDelivery(telegram_token, telegram_chat)
        else:
            self.telegram = None
        
        # AI Copywriter
        self.ai_copywriter = AICopywriter(audit_logger=self.audit)
        
        # Webhook / CRM
        self.webhook = WebhookExporter(audit_logger=self.audit)
        
        # Bing Search (global discovery)
        bing_key = os.getenv("BING_SEARCH_API_KEY")
        if bing_key:
            self.bing = BingSearchCollector(api_key=bing_key, audit_logger=self.audit)
        else:
            self.bing = None
    
    def discover_uk(self, max_results: int = 100) -> List[Dict]:
        """Discover UK leads via Google Places + Companies House."""
        leads = []
        
        # Google Places searches
        if self.places:
            queries = [
                "online store UK",
                "ecommerce business UK",
                "online shop London",
                "boutique online UK",
                "fashion ecommerce UK",
            ]
            
            for query in queries:
                try:
                    results = self.places.search_text(query, region="gb", max_results=20)
                    for place in results:
                        place_id = place.get("place_id")
                        if place_id:
                            details = self.places.get_details(place_id)
                            if details:
                                lead = self.places.to_lead(details, "UK")
                                lead["record_id"] = str(uuid.uuid4())
                                lead["date_collected"] = datetime.utcnow().isoformat()
                                leads.append(lead)
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Places search failed: {e}")
        
        # Companies House
        if self.companies_house:
            try:
                companies = self.companies_house.search_ecommerce_companies(max_results=50)
                for company in companies:
                    lead = self.companies_house.to_lead(company)
                    lead["record_id"] = str(uuid.uuid4())
                    lead["date_collected"] = datetime.utcnow().isoformat()
                    leads.append(lead)
            except Exception as e:
                logger.error(f"Companies House search failed: {e}")
        
        # Deduplicate by website
        seen = set()
        unique = []
        for lead in leads:
            url = lead.get("website_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(lead)
            elif not url:
                unique.append(lead)
        
        logger.info(f"Discovered {len(unique)} unique UK leads")
        return unique[:max_results]
    
    def discover_global(self, country: str = "US", max_results: int = 100) -> List[Dict]:
        """Discover leads globally via Bing Search API."""
        if not self.bing:
            logger.warning("Bing Search not configured — set BING_SEARCH_API_KEY")
            return []
        
        try:
            leads = self.bing.discover_leads(country=country, max_results=max_results)
            for lead in leads:
                lead["record_id"] = str(uuid.uuid4())
                lead["date_collected"] = datetime.utcnow().isoformat()
            return leads
        except Exception as e:
            logger.error(f"Bing discovery failed for {country}: {e}")
            return []
    
    def enrich_leads(self, leads: List[Dict]) -> List[Dict]:
        """Enrich leads with website analysis."""
        enriched = []
        
        for lead in leads:
            try:
                # Website analysis
                lead = self.website.enrich(lead)
                
                # PageSpeed
                if self.pagespeed and lead.get("website_url"):
                    lead = self.pagespeed.enrich(lead)
                
                # AI Copywriter (generate outreach copy)
                if self.ai_copywriter and self.ai_copywriter.enabled:
                    lead = self.ai_copywriter.enrich(lead)
                
                enriched.append(lead)
                time.sleep(2)  # Polite delay
                
            except Exception as e:
                logger.error(f"Enrichment failed for {lead.get('business_name')}: {e}")
                enriched.append(lead)
        
        return enriched
    
    def score_leads(self, leads: List[Dict]) -> List[Dict]:
        """Score all leads."""
        for lead in leads:
            try:
                lead["website_quality_score"] = self.scorer.calculate(lead)
                lead["outreach_priority"] = self.scorer.determine_priority(
                    lead["website_quality_score"], lead
                )
                lead["improvement_opportunity"] = self.scorer.generate_opportunity(lead)
            except Exception as e:
                logger.error(f"Scoring failed for {lead.get('business_name')}: {e}")
                lead["website_quality_score"] = 50
                lead["outreach_priority"] = "WARM"
                lead["improvement_opportunity"] = "Review needed"
        
        return leads
    
    def process_batch(
        self,
        country: str = "UK",
        batch_size: int = 500,
        batch_number: int = 1
    ) -> Optional[str]:
        """
        Process one batch: discover → enrich → score → export → deliver.
        """
        logger.info(f"Starting batch #{batch_number} for {country}")
        
        # Discover
        if country == "UK":
            leads = self.discover_uk(max_results=batch_size)
        elif country in ("US", "AU", "CA", "IE", "NZ", "SG", "ZA", "IN"):
            leads = self.discover_global(country=country, max_results=batch_size)
        else:
            logger.warning(f"Country {country} not yet implemented")
            return None
        
        if not leads:
            logger.warning("No leads discovered")
            return None
        
        # Enrich
        logger.info(f"Enriching {len(leads)} leads...")
        leads = self.enrich_leads(leads)
        
        # Score
        logger.info("Scoring leads...")
        leads = self.score_leads(leads)
        
        # Export
        logger.info("Exporting to Excel...")
        file_path = self.exporter.export_batch(leads, country, batch_number)
        
        # Stats
        hot = sum(1 for l in leads if l.get("outreach_priority") == "HOT")
        warm = sum(1 for l in leads if l.get("outreach_priority") == "WARM")
        cold = sum(1 for l in leads if l.get("outreach_priority") == "COLD")
        
        # Webhook / CRM export
        if self.webhook and self.webhook.enabled:
            logger.info("Pushing to webhook/CRM...")
            webhook_stats = self.webhook.export_batch(leads)
            logger.info(f"Webhook stats: {webhook_stats}")
        
        # Deliver
        if self.telegram:
            logger.info("Delivering via Telegram...")
            self.telegram.send_batch_sync(
                file_path=file_path,
                country=country,
                batch_number=batch_number,
                total_records=len(leads),
                hot_count=hot,
                warm_count=warm,
                cold_count=cold,
            )
        
        logger.info(f"Batch #{batch_number} complete: {len(leads)} leads")
        return file_path
    
    def run(self, country: str = "UK", batches: int = 1):
        """Run full pipeline."""
        results = []
        for i in range(1, batches + 1):
            result = self.process_batch(country, batch_number=i)
            if result:
                results.append(result)
        return results


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="B2B E-commerce Lead Research")
    parser.add_argument("--country", default="UK", help="Country code")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches")
    parser.add_argument("--batch-size", type=int, default=500, help="Leads per batch")
    
    args = parser.parse_args()
    
    pipeline = LeadPipeline()
    pipeline.run(args.country, args.batches)


if __name__ == "__main__":
    main()