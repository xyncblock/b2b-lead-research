"""
Google Search scraper for finding e-commerce stores and websites.
Searches Google web results, not Maps.
"""

import requests
import re
import time
import logging
import sys
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote_plus, urlparse

# Add parent to path for imports
sys.path.insert(0, '.')

try:
    from compliance.audit_logger import AuditLogger
except ImportError:
    # Fallback if compliance module not available
    class AuditLogger:
        def log_fetch(self, **kwargs):
            pass

logger = logging.getLogger(__name__)


class GoogleSearchCollector:
    """
    Scrape Google Search results to find e-commerce stores.
    No API key needed.
    """
    
    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self.audit = audit_logger or AuditLogger()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        })
        # Warm up session with DuckDuckGo to get cookies
        try:
            self.session.get('https://duckduckgo.com/', timeout=10)
        except:
            pass
    
    def search(
        self,
        query: str,
        region: str = "uk",
        max_results: int = 50,
    ) -> List[Dict]:
        """
        Search Google and extract website results.
        
        Args:
            query: Search query (e.g., "e-commerce stores UK")
            region: Country code for search
            max_results: Number of results to fetch
        """
        results = []
        start = 0
        
        while len(results) < max_results and start < max_results:
            page_results = self._search_page(query, region, start)
            if not page_results:
                break
            
            results.extend(page_results)
            start += 10
            time.sleep(2)  # Be polite
        
        # Remove duplicates
        seen = set()
        unique = []
        for r in results:
            domain = self._extract_domain(r["url"])
            if domain and domain not in seen:
                seen.add(domain)
                unique.append(r)
        
        logger.info(f"Found {len(unique)} unique websites for '{query}'")
        return unique[:max_results]
    
    def _search_page(self, query: str, region: str, start: int) -> List[Dict]:
        """Fetch search results - tries multiple search engines."""
        
        # Try DuckDuckGo first (less blocking)
        results = self._search_duckduckgo(query, start)
        if results:
            return results
        
        # Fallback to Bing
        results = self._search_bing(query, region, start)
        if results:
            return results
        
        # Last resort: Google (often blocked)
        return self._search_google(query, region, start)
    
    def _search_duckduckgo(self, query: str, start: int) -> List[Dict]:
        """Search DuckDuckGo (HTML version)."""
        url = "https://html.duckduckgo.com/html/"
        params = {
            "q": query,
            "s": start,
        }
        
        try:
            resp = self.session.post(url, data=params, timeout=30)
            resp.raise_for_status()
            
            self.audit.log_fetch(
                operation="duckduckgo_search",
                url=url,
                domain="duckduckgo.com",
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="duckduckgo_scrape",
                metadata={"query": query},
            )
            
            results = self._parse_duckduckgo_results(resp.text)
            
            # If no results, try alternative DuckDuckGo URL
            if not results:
                return self._search_duckduckgo_lite(query, start)
            
            return results
            
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []
    
    def _search_duckduckgo_lite(self, query: str, start: int) -> List[Dict]:
        """Try DuckDuckGo lite as fallback."""
        url = "https://lite.duckduckgo.com/lite/"
        params = {
            "q": query,
            "s": start,
        }
        
        try:
            resp = self.session.post(url, data=params, timeout=30)
            resp.raise_for_status()
            return self._parse_duckduckgo_results(resp.text)
        except Exception as e:
            logger.warning(f"DuckDuckGo lite failed: {e}")
            return []
    
    def _search_bing(self, query: str, region: str, start: int) -> List[Dict]:
        """Search Bing."""
        url = "https://www.bing.com/search"
        params = {
            "q": query,
            "first": start + 1,
            "cc": region.upper(),
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            
            self.audit.log_fetch(
                operation="bing_search",
                url=url,
                domain="bing.com",
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="bing_scrape",
                metadata={"query": query},
            )
            
            return self._parse_bing_results(resp.text)
            
        except Exception as e:
            logger.warning(f"Bing search failed: {e}")
            return []
    
    def _search_google(self, query: str, region: str, start: int) -> List[Dict]:
        """Search Google (often blocked)."""
        url = "https://www.google.com/search"
        params = {
            "q": query,
            "start": start,
            "num": 10,
            "gl": region,
            "hl": "en",
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            
            self.audit.log_fetch(
                operation="google_search",
                url=url,
                domain="google.com",
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="google_search_scrape",
                metadata={"query": query, "start": start},
            )
            
            return self._parse_results(resp.text)
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            return []
    
    def _parse_duckduckgo_results(self, html: str) -> List[Dict]:
        """Parse DuckDuckGo HTML results."""
        results = []
        
        # DuckDuckGo result pattern
        pattern = r'<a[^>]*class="result__a"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for url, title_html in matches:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and len(title) > 3:
                results.append({
                    "url": url,
                    "title": title,
                    "domain": self._extract_domain(url),
                })
        
        return results
    
    def _parse_bing_results(self, html: str) -> List[Dict]:
        """Parse Bing HTML results."""
        results = []
        
        # Bing result pattern
        pattern = r'<a[^>]*href="(https?://[^"]+)"[^>]*target="_blank"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for url, title_html in matches:
            # Skip Bing's own links
            if "bing.com" in url or "microsoft.com" in url:
                continue
            
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and len(title) > 3 and not title.startswith("http"):
                results.append({
                    "url": url,
                    "title": title,
                    "domain": self._extract_domain(url),
                })
        
        return results
    
    def _parse_results(self, html: str) -> List[Dict]:
        """Extract search results from Google HTML."""
        results = []
        
        # Find all result blocks - updated pattern for modern Google
        # Try multiple patterns since Google changes frequently
        patterns = [
            # Pattern 1: Standard search results
            r'<a[^>]*href="/url\?q=(https?://[^"]+)&amp;sa=[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            # Pattern 2: Alternative format
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            # Pattern 3: Simpler format
            r'href="/url\?q=(https?://[^&"]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for url, title_html in matches:
                # Clean URL (remove Google tracking)
                url = url.split("&sa=")[0]
                url = url.split("&amp;")[0]
                
                # Skip Google own domains and non-http
                if not url.startswith("http"):
                    continue
                if any(d in url for d in ["google.com", "youtube.com", "maps.google", "support.google"]):
                    continue
                
                # Clean title
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                title = title.replace("&nbsp;", " ").replace("&amp;", "&")
                
                if title and len(title) > 3:
                    results.append({
                        "url": url,
                        "title": title,
                        "domain": self._extract_domain(url),
                    })
        
        return results
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except:
            return ""
    
    def extract_emails(self, url: str) -> List[str]:
        """
        Visit a website and extract email addresses.
        """
        emails = []
        
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            # Extract emails from page
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            found = re.findall(email_pattern, resp.text)
            
            # Filter out common false positives
            skip = {"example.com", "test.com", "domain.com", "email.com", "yourdomain.com", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}
            for email in found:
                domain = email.split("@")[1].lower()
                if domain not in skip and not any(s in domain for s in ["google", "facebook", "twitter", "instagram", "linkedin"]):
                    emails.append(email.lower())
            
            # Also check contact/about pages
            if not emails:
                emails = self._check_contact_pages(url, resp.text)
            
            self.audit.log_fetch(
                operation="extract_emails",
                url=url,
                domain=self._extract_domain(url),
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="website_scrape",
                metadata={"emails_found": len(emails)},
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract emails from {url}: {e}")
        
        return list(set(emails))  # Remove duplicates
    
    def _check_contact_pages(self, base_url: str, homepage_html: str) -> List[str]:
        """Check contact/about pages for emails."""
        emails = []
        
        # Find contact page links
        contact_patterns = [
            r'href="([^"]*contact[^"]*)"',
            r'href="([^"]*about[^"]*)"',
            r'href="([^"]*team[^"]*)"',
        ]
        
        contact_urls = set()
        for pattern in contact_patterns:
            matches = re.findall(pattern, homepage_html, re.I)
            for match in matches:
                if match.startswith("http"):
                    contact_urls.add(match)
                elif match.startswith("/"):
                    parsed = urlparse(base_url)
                    contact_urls.add(f"{parsed.scheme}://{parsed.netloc}{match}")
        
        # Check each contact page
        for url in list(contact_urls)[:3]:  # Limit to 3 pages
            try:
                resp = self.session.get(url, timeout=10)
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                found = re.findall(email_pattern, resp.text)
                emails.extend(found)
            except:
                pass
            time.sleep(0.5)
        
        return list(set(emails))
    
    def search_ecommerce_stores(
        self,
        niche: str = "e-commerce",
        country: str = "UK",
        max_results: int = 50,
        extract_emails: bool = True,
    ) -> List[Dict]:
        """
        Search for e-commerce stores and optionally extract emails.
        
        Args:
            niche: Type of stores (e-commerce, fashion, electronics, etc.)
            country: Country to search in
            max_results: Number of stores to find
            extract_emails: Whether to visit sites and extract emails
        """
        query = f"{niche} online store {country}"
        
        print(f"🔍 Searching: {query}")
        results = self.search(query, region=country.lower(), max_results=max_results)
        
        leads = []
        for result in results:
            lead = {
                "source_api": "google_search",
                "source_url": result["url"],
                "date_discovered": datetime.utcnow().isoformat(),
                "country": country,
                "business_name": result["title"],
                "website_url": result["url"],
                "domain": result["domain"],
                "emails": [],
            }
            
            if extract_emails:
                print(f"📧 Checking emails for: {result['domain']}")
                lead["emails"] = self.extract_emails(result["url"])
                time.sleep(1)  # Be polite
            
            leads.append(lead)
        
        return leads


if __name__ == "__main__":
    # Example usage
    collector = GoogleSearchCollector()
    
    # Search for UK e-commerce stores
    stores = collector.search_ecommerce_stores(
        niche="e-commerce",
        country="UK",
        max_results=10,
        extract_emails=True,
    )
    
    print(f"\n{'='*60}")
    print(f"Found {len(stores)} stores")
    print(f"{'='*60}\n")
    
    for store in stores:
        print(f"🏪 {store['business_name']}")
        print(f"   URL: {store['website_url']}")
        if store['emails']:
            print(f"   Emails: {', '.join(store['emails'])}")
        print()
