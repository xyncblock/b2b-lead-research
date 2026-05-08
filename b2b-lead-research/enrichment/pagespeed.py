"""
Google PageSpeed Insights API for performance scoring.
"""
import requests
import logging
from typing import Optional, Dict

from compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class PageSpeedEnricher:
    """
    Get Lighthouse performance scores via PageSpeed Insights API.
    """
    
    API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    
    def __init__(self, api_key: str, audit_logger: Optional[AuditLogger] = None):
        self.api_key = api_key
        self.audit = audit_logger or AuditLogger()
    
    def get_score(self, url: str, strategy: str = "mobile") -> Optional[float]:
        """
        Get performance score for a URL.
        
        Args:
            url: Website URL
            strategy: "mobile" or "desktop"
        
        Returns:
            Score 0-100 or None
        """
        params = {
            "url": url,
            "key": self.api_key,
            "strategy": strategy,
            "category": "PERFORMANCE",
        }
        
        try:
            response = requests.get(self.API_URL, params=params, timeout=60)
            
            self.audit.log_fetch(
                operation="pagespeed",
                url=self.API_URL,
                domain="googleapis.com",
                status_code=response.status_code,
                response_size=len(response.content),
                source_api="google_pagespeed",
                metadata={"target_url": url, "strategy": strategy},
            )
            
            if response.status_code == 200:
                data = response.json()
                score = data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score")
                if score is not None:
                    return round(score * 100, 1)
            elif response.status_code == 429:
                logger.warning("PageSpeed API rate limit")
            
        except Exception as e:
            self.audit.log_fetch(
                operation="pagespeed",
                url=self.API_URL,
                domain="googleapis.com",
                error=str(e),
                source_api="google_pagespeed",
            )
            logger.warning(f"PageSpeed failed for {url}: {e}")
        
        return None
    
    def enrich(self, lead: Dict) -> Dict:
        """Enrich lead with PageSpeed score."""
        url = lead.get("website_url")
        if not url:
            return lead
        
        score = self.get_score(url)
        if score is not None:
            lead["page_speed_score"] = score
        
        return lead
