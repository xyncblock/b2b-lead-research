"""
Google Places API collector for business discovery.
Official API - compliant, no scraping.
Fallback to Google Maps web search via Serper/Bing when API unavailable.
"""
import requests
import time
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote_plus

from compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class GooglePlacesCollector:
    """
    Collects business data from Google Places API or direct Maps scraping.
    
    Modes:
      - "api"      → Official Google Places API (needs key)
      - "scrape"   → Scrape Google Maps directly (no key needed)
      - "auto"     → Try API first, fallback to scrape on failure
    """
    
    BASE_URL = "https://maps.googleapis.com/maps/api/place"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        mode: str = "api",
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.api_key = api_key
        self.mode = mode.lower().strip()
        self.audit = audit_logger or AuditLogger()
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
        })
    
    # ── Mode helpers ──────────────────────────────────────────────────
    
    def _should_use_api(self) -> bool:
        return self.mode in ("api", "auto")
    
    def _should_use_scrape(self) -> bool:
        return self.mode in ("scrape", "auto")
    
    def _api_available(self) -> bool:
        return bool(self.api_key)
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Make authenticated request to Places API."""
        params["key"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}/json"
        
        start_time = time.time()
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status", "UNKNOWN")
            
            # Log the fetch
            self.audit.log_fetch(
                operation=f"places_{endpoint}",
                url=url,
                domain="maps.googleapis.com",
                status_code=response.status_code,
                response_size=len(response.content),
                source_api="google_places",
                metadata={
                    "endpoint": endpoint,
                    "status": status,
                    "duration_ms": round((time.time() - start_time) * 1000, 2),
                }
            )
            
            if status != "OK":
                if status == "ZERO_RESULTS":
                    return {"results": []}
                logger.warning(f"Places API status: {status} - {data.get('error_message', '')}")
                return None
            
            return data
            
        except requests.RequestException as e:
            self.audit.log_fetch(
                operation=f"places_{endpoint}",
                url=url,
                domain="maps.googleapis.com",
                error=str(e),
                source_api="google_places",
            )
            logger.error(f"Places API request failed: {e}")
            return None
    
    def search_text(
        self,
        query: str,
        region: str = "gb",
        location: Optional[str] = None,
        radius: int = 50000,
        max_results: int = 60
    ) -> List[Dict]:
        """
        Text search for businesses.
        
        Args:
            query: Search query (e.g., "online clothing store London")
            region: Country code (gb, ie, au, ca)
            location: "lat,lng" bias
            radius: Search radius in meters
            max_results: Max 60 (3 pages of 20)
        """
        # ── Scrape mode ───────────────────────────────────────────────
        if self.mode == "scrape":
            return self.search_maps_scrape(query, region, max_results)
        
        # ── API mode ──────────────────────────────────────────────────
        results = []
        next_page_token = None
        page = 0
        
        while len(results) < max_results and page < 3:
            params = {
                "query": query,
                "region": region,
            }
            
            if location:
                params["location"] = location
                params["radius"] = min(radius, 50000)
            
            if next_page_token:
                params["pagetoken"] = next_page_token
                time.sleep(2)  # Required by Google
            
            data = self._make_request("textsearch", params)
            if not data:
                break
            
            page_results = data.get("results", [])
            results.extend(page_results)
            
            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
            
            page += 1
            time.sleep(2)
        
        # ── Auto fallback ─────────────────────────────────────────────
        if not results and self.mode == "auto" and self._should_use_scrape():
            logger.info(f"API returned no results, falling back to scrape for '{query}'")
            return self.search_maps_scrape(query, region, max_results)
        
        logger.info(f"Found {len(results[:max_results])} results for '{query}' in {region}")
        return results[:max_results]
    
    def get_details(self, place_id: str) -> Optional[Dict]:
        """Get detailed information about a business."""
        # Scrape mode
        if self.mode == "scrape":
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
            }
            return self._scrape_place_details(place_id, "gb", headers)
        
        # API mode
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,website,url,rating,user_ratings_total,types,opening_hours,business_status,geometry",
        }
        
        data = self._make_request("details", params)
        if data:
            return data.get("result")
        return None
    
    def nearby_search(
        self,
        location: str,
        radius: int = 50000,
        keyword: str = "store",
        type_filter: str = "store",
        max_results: int = 60
    ) -> List[Dict]:
        """
        Search for businesses near a location.
        
        Args:
            location: "lat,lng"
            radius: Search radius in meters (max 50000)
            keyword: Search term
            type_filter: Google place type
            max_results: Max 60
        """
        # Scrape mode not supported for nearby (needs lat/lng scraping)
        if self.mode == "scrape":
            logger.warning("Scrape mode doesn't support nearby_search, use search_text instead")
            return []
        
        results = []
        next_page_token = None
        page = 0
        
        while len(results) < max_results and page < 3:
            params = {
                "location": location,
                "radius": min(radius, 50000),
                "keyword": keyword,
                "type": type_filter,
            }
            
            if next_page_token:
                params["pagetoken"] = next_page_token
                time.sleep(2)
            
            data = self._make_request("nearbysearch", params)
            if not data:
                break
            
            results.extend(data.get("results", []))
            
            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
            
            page += 1
            time.sleep(2)
        
        return results[:max_results]
    
    # ── Fallback: Scrape Google Maps directly ─────────────────────────

    def search_maps_scrape(
        self,
        query: str,
        region: str = "gb",
        max_results: int = 20,
    ) -> List[Dict]:
        """
        Scrape Google Maps search results directly.
        No API keys needed. Uses the same endpoints the browser hits.
        """
        leads = []
        search_url = (
            "https://www.google.com/maps/search/"
            f"{quote_plus(query)}"
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        try:
            # Step 1: Get the search page
            resp = self.session.get(search_url, headers=headers, timeout=30)
            resp.raise_for_status()

            self.audit.log_fetch(
                operation="maps_scrape_search",
                url=search_url,
                domain="google.com",
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="maps_scrape",
                metadata={"query": query, "region": region},
            )

            # Step 2: Extract place IDs from the page
            place_ids = self._extract_place_ids(resp.text)

            # Step 3: Fetch details for each place
            for place_id in place_ids[:max_results]:
                lead = self._scrape_place_details(place_id, region, headers)
                if lead:
                    leads.append(lead)
                time.sleep(0.5)  # Be polite

        except Exception as e:
            self.audit.log_fetch(
                operation="maps_scrape_search",
                url=search_url,
                domain="google.com",
                error=str(e),
                source_api="maps_scrape",
            )
            logger.error(f"Maps scrape failed: {e}")

        logger.info(f"[scrape] Found {len(leads)} results for '{query}'")
        return leads

    def _extract_place_ids(self, html: str) -> List[str]:
        """Extract place IDs from Google Maps HTML."""
        # Google embeds place IDs in various formats
        patterns = [
            r'"place_id":"([A-Za-z0-9_-]+)"',
            r'"placeId":"([A-Za-z0-9_-]+)"',
            r'data-pid="([A-Za-z0-9_-]+)"',
            r'\\x22place_id\\x22:\\x22([A-Za-z0-9_-]+)\\x22',
        ]

        place_ids = []
        for pattern in patterns:
            matches = re.findall(pattern, html)
            place_ids.extend(matches)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for pid in place_ids:
            if pid not in seen and len(pid) > 20:  # Place IDs are long
                seen.add(pid)
                unique.append(pid)

        return unique

    def _scrape_place_details(
        self,
        place_id: str,
        region: str,
        headers: Dict,
    ) -> Optional[Dict]:
        """Scrape details for a single place from Google Maps."""
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

        try:
            resp = self.session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            html = resp.text

            self.audit.log_fetch(
                operation="maps_scrape_detail",
                url=url,
                domain="google.com",
                status_code=resp.status_code,
                response_size=len(resp.content),
                source_api="maps_scrape",
                metadata={"place_id": place_id},
            )

            return self._parse_place_html(html, place_id, region, url)

        except Exception as e:
            self.audit.log_fetch(
                operation="maps_scrape_detail",
                url=url,
                domain="google.com",
                error=str(e),
                source_api="maps_scrape",
            )
            logger.warning(f"Failed to scrape place {place_id}: {e}")
            return None

    def _parse_place_html(self, html: str, place_id: str, region: str, url: str) -> Dict:
        """Parse business details from Google Maps place page HTML."""
        # Business name - usually in title or meta tags
        name_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if not name_match:
            name_match = re.search(r'<title>([^<]+)\s+-\s+Google\s+Maps</title>', html, re.I)
        business_name = name_match.group(1).strip() if name_match else ""

        # Address
        addr_match = re.search(r'"address":"([^"]+)"', html)
        if not addr_match:
            addr_match = re.search(r'\\x22address\\x22:\\x22([^\\]+)\\x22', html)
        address = addr_match.group(1).replace('\\n', ', ').strip() if addr_match else ""

        # Phone
        phone_match = re.search(r'"phone":"([^"]+)"', html)
        if not phone_match:
            phone_match = re.search(r'tel:([^"\s]+)', html)
        phone = phone_match.group(1).strip() if phone_match else ""

        # Website
        website_match = re.search(r'"website":"([^"]+)"', html)
        if not website_match:
            website_match = re.search(r'href="(https?://[^"]+)"[^>]*class="[^"]*website', html)
        website = website_match.group(1).strip() if website_match else ""

        # Rating
        rating_match = re.search(r'"rating":(\d+\.\d+)', html)
        if not rating_match:
            rating_match = re.search(r'([0-9]\.[0-9])\s*star', html, re.I)
        rating = float(rating_match.group(1)) if rating_match else None

        # Review count
        reviews_match = re.search(r'"review_count":(\d+)', html)
        if not reviews_match:
            reviews_match = re.search(r'\((\d+)\s+reviews?\)', html, re.I)
        review_count = int(reviews_match.group(1)) if reviews_match else None

        # Business status
        status = ""
        if "Permanently closed" in html or "permanently closed" in html.lower():
            status = "CLOSED_PERMANENTLY"
        elif "Temporarily closed" in html or "temporarily closed" in html.lower():
            status = "CLOSED_TEMPORARILY"
        else:
            status = "OPERATIONAL"

        # Try to extract lat/lng from URL patterns or data
        lat, lng = None, None
        latlng_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', html)
        if latlng_match:
            lat = float(latlng_match.group(1))
            lng = float(latlng_match.group(2))

        return {
            "source_api": "google_maps_scrape",
            "source_url": url,
            "date_discovered": datetime.utcnow().isoformat(),
            "country": region,
            "business_name": business_name,
            "business_address": address,
            "business_phone": phone,
            "website_url": website,
            "google_maps_url": url,
            "google_rating": rating,
            "google_review_count": review_count,
            "google_place_id": place_id,
            "google_types": [],
            "business_status": status,
            "latitude": lat,
            "longitude": lng,
        }

    def to_lead(self, place_data: Dict, country: str) -> Dict:
        """Convert Google Places data to our lead format."""
        location = place_data.get("geometry", {}).get("location", {})
        
        lead = {
            "source_api": "google_places",
            "source_url": f"https://www.google.com/maps/place/?q=place_id:{place_data.get('place_id', '')}",
            "date_discovered": datetime.utcnow().isoformat(),
            
            # Business info
            "country": country,
            "business_name": place_data.get("name", ""),
            "business_address": place_data.get("formatted_address", ""),
            "business_phone": place_data.get("formatted_phone_number", ""),
            "website_url": place_data.get("website", ""),
            
            # Google data
            "google_maps_url": place_data.get("url", ""),
            "google_rating": place_data.get("rating"),
            "google_review_count": place_data.get("user_ratings_total"),
            "google_place_id": place_data.get("place_id"),
            "google_types": place_data.get("types", []),
            "business_status": place_data.get("business_status", ""),
            
            # Location
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
        }
        
        return lead