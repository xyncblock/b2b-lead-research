"""
Website enrichment - analyzes websites for quality signals.
Respects robots.txt, uses polite delays.
"""
import re
import time
import ssl
import socket
import logging
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from compliance.robots_checker import RobotsChecker
from compliance.audit_logger import AuditLogger
from compliance.consent_classifier import ConsentClassifier

logger = logging.getLogger(__name__)


class WebsiteEnricher:
    """
    Enriches lead data by analyzing their website.
    """
    
    PLATFORM_PATTERNS = {
        "Shopify": ["cdn.shopify.com", "myshopify.com", "shopify-checkout", "shopify.com"],
        "WooCommerce": ["wp-content/plugins/woocommerce", "wc-ajax", "woocommerce"],
        "Wix": ["wix.com", "wixstores", "static.wixstatic.com"],
        "Squarespace": ["squarespace.com", "static1.squarespace.com"],
        "BigCommerce": ["cdn11.bigcommerce.com", "bigcommerce.com"],
        "Magento": ["magento", "mageplaza"],
        "PrestaShop": ["prestashop"],
        "Ecwid": ["ecwid.com", "app.ecwid.com"],
        "Big Cartel": ["bigcartel.com"],
        "Weebly": ["weebly.com"],
        "3dcart": ["3dcart.com"],
        "Volusion": ["volusion.com"],
    }
    
    def __init__(
        self,
        robots_checker: Optional[RobotsChecker] = None,
        audit_logger: Optional[AuditLogger] = None,
        consent_classifier: Optional[ConsentClassifier] = None,
        default_delay: float = 3.0,
    ):
        self.robots = robots_checker or RobotsChecker(default_delay=default_delay)
        self.audit = audit_logger or AuditLogger()
        self.consent = consent_classifier or ConsentClassifier()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "B2BLeadResearchBot/1.0 (+https://youragency.com/bot-info; research@youragency.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        })
        self.last_request_time = 0
    
    def _respectful_get(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        """Make a respectful HTTP GET request."""
        # Check robots.txt
        robots_result = self.robots.check_url(url)
        if not robots_result["allowed"]:
            logger.info(f"Blocked by robots.txt: {url}")
            self.audit.log_fetch(
                operation="website_fetch_blocked",
                url=url,
                domain=urlparse(url).netloc,
                robots_result=robots_result,
                error="blocked_by_robots_txt",
            )
            return None
        
        # Enforce crawl delay
        delay = self.robots.get_delay(url)
        elapsed = time.time() - self.last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            self.last_request_time = time.time()
            
            self.audit.log_fetch(
                operation="website_fetch",
                url=url,
                domain=urlparse(url).netloc,
                robots_result=robots_result,
                status_code=response.status_code,
                response_size=len(response.content),
            )
            
            return response
        except requests.RequestException as e:
            self.audit.log_fetch(
                operation="website_fetch_error",
                url=url,
                domain=urlparse(url).netloc,
                robots_result=robots_result,
                error=str(e),
            )
            logger.warning(f"Request failed for {url}: {e}")
            return None
    
    def enrich(self, lead: Dict) -> Dict:
        """
        Enrich a lead by analyzing its website.
        """
        website_url = lead.get("website_url")
        if not website_url:
            lead["website_status"] = "no_website"
            return lead
        
        # Ensure URL has scheme
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"
            lead["website_url"] = website_url
        
        # Fetch homepage
        response = self._respectful_get(website_url)
        if not response:
            lead["website_status"] = "unreachable"
            return lead
        
        if response.status_code != 200:
            lead["website_status"] = f"http_{response.status_code}"
            return lead
        
        lead["website_status"] = "live"
        
        # Parse HTML
        soup = BeautifulSoup(response.text, "lxml")
        html = response.text.lower()
        
        # SSL check
        parsed = urlparse(response.url)
        lead["has_ssl"] = parsed.scheme == "https"
        
        # Mobile responsive
        lead["mobile_friendly"] = self._check_mobile(soup)
        
        # Platform detection
        lead["ecommerce_platform"] = self._detect_platform(html)
        
        # Emails
        emails = self._extract_emails(response.text)
        if emails:
            generic = self.consent.get_safe_email(emails)
            named = None
            for email in emails:
                classified = self.consent.classify_email(email)
                if classified["type"] == "named":
                    named = email
                    break
            
            lead["business_email_generic"] = generic
            lead["business_email_named"] = named
            lead["consent_status"] = self.consent.get_consent_status(generic, named)
        
        # Social links
        lead["social_handles"] = self._extract_social(soup, website_url)
        
        # Design metrics
        lead["design_metrics"] = self._analyze_design(soup, html)
        
        # Product estimate
        lead["estimated_product_count"] = self._estimate_products(website_url)
        
        # Content freshness
        lead["last_content_update"] = self._check_content_freshness(soup)
        
        # Checkout functional check
        lead["checkout_functional"] = self._check_checkout(soup, html)
        
        return lead
    
    def _check_mobile(self, soup: BeautifulSoup) -> bool:
        """Check for viewport meta tag."""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        return viewport is not None
    
    def _detect_platform(self, html: str) -> Optional[str]:
        """Detect e-commerce platform."""
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in html:
                    return platform
        
        # Check for generic e-commerce
        indicators = ["cart", "checkout", "add to cart", "basket", "product"]
        if any(i in html for i in indicators):
            return "custom"
        
        return None
    
    def _extract_emails(self, html: str) -> List[str]:
        """Extract email addresses from HTML."""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, html)
        
        # Filter out false positives
        filtered = []
        for email in emails:
            email = email.lower()
            if any(x in email for x in ["example.com", "domain.com", ".png", ".jpg", ".gif"]):
                continue
            if email not in filtered:
                filtered.append(email)
        
        return filtered
    
    def _extract_social(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract social media links."""
        patterns = {
            "facebook": r"facebook\.com/([^/\s\"']+)",
            "instagram": r"instagram\.com/([^/\s\"']+)",
            "twitter": r"twitter\.com/([^/\s\"']+)",
            "x": r"x\.com/([^/\s\"']+)",
            "linkedin": r"linkedin\.com/company/([^/\s\"']+)",
            "youtube": r"youtube\.com/(?:c/|channel/|user/)?([^/\s\"']+)",
            "tiktok": r"tiktok\.com/@([^/\s\"']+)",
            "pinterest": r"pinterest\.(?:com|co\.uk)/([^/\s\"']+)",
        }
        
        handles = []
        html = str(soup)
        
        for platform, pattern in patterns.items():
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in set(matches):
                if match and match not in ["sharer", "share", "plugins", "dialog", "home"]:
                    handles.append({
                        "platform": platform,
                        "username": match,
                        "url": f"https://{platform}.com/{match}" if platform != "x" else f"https://x.com/{match}"
                    })
                    break
        
        return handles
    
    def _analyze_design(self, soup: BeautifulSoup, html: str) -> Dict:
        """Analyze design quality."""
        return {
            "has_viewport_meta": soup.find("meta", attrs={"name": "viewport"}) is not None,
            "has_schema_markup": "schema.org" in html or "application/ld+json" in html,
            "has_social_links": any(x in html for x in ["facebook.com", "instagram.com", "twitter.com", "x.com"]),
            "has_favicon": soup.find("link", attrs={"rel": "icon"}) is not None or soup.find("link", attrs={"rel": "shortcut icon"}) is not None,
            "has_flash": "swfobject" in html or ".swf" in html,
            "has_tables_for_layout": len(soup.find_all("table")) > 5,
            "has_modern_css": "flex" in html or "grid" in html,
        }
    
    def _estimate_products(self, base_url: str) -> Optional[int]:
        """Estimate product count from sitemap."""
        sitemap_urls = [
            f"{base_url.rstrip('/')}/sitemap.xml",
            f"{base_url.rstrip('/')}/sitemap_index.xml",
        ]
        
        for sitemap_url in sitemap_urls:
            try:
                response = self._respectful_get(sitemap_url)
                if response and response.status_code == 200:
                    count = response.text.count("/product/")
                    count += response.text.count("/products/")
                    count += response.text.count("/item/")
                    if count > 0:
                        return count
            except:
                continue
        
        return None
    
    def _check_content_freshness(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Check for recent content signals."""
        # Look for copyright year
        text = soup.get_text()
        current_year = datetime.utcnow().year
        
        if str(current_year) in text:
            return datetime.utcnow()
        
        # Check meta dates
        for meta in soup.find_all("meta"):
            if meta.get("property") in ["article:modified_time", "og:updated_time"]:
                try:
                    return datetime.fromisoformat(meta.get("content", "").replace("Z", "+00:00"))
                except:
                    pass
        
        return None
    
    def _check_checkout(self, soup: BeautifulSoup, html: str) -> Optional[bool]:
        """Check if checkout appears functional."""
        checkout_indicators = [
            "checkout", "cart", "basket", "bag", 
            "add to cart", "buy now", "purchase"
        ]
        return any(indicator in html for indicator in checkout_indicators)