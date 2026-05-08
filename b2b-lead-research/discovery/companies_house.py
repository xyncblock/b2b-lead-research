"""
Companies House API collector (UK only).
Free API for UK company data.
https://developer.company-information.service.gov.uk/
"""
import requests
import base64
import logging
from typing import List, Dict, Optional
from datetime import datetime

from compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class CompaniesHouseCollector:
    """
    Collects UK company data from Companies House API.
    Free tier: 600 requests per 5 minutes.
    """
    
    BASE_URL = "https://api.company-information.service.gov.uk"
    
    def __init__(self, api_key: str, audit_logger: Optional[AuditLogger] = None):
        self.api_key = api_key
        self.audit = audit_logger or AuditLogger()
        self.session = requests.Session()
        
        # Companies House uses HTTP Basic Auth with API key as username
        auth_string = base64.b64encode(f"{api_key}:".encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {auth_string}",
            "Accept": "application/json",
        })
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Companies House API."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params or {}, timeout=30)
            
            self.audit.log_fetch(
                operation="companies_house",
                url=url,
                domain="api.company-information.service.gov.uk",
                status_code=response.status_code,
                response_size=len(response.content),
                source_api="companies_house",
                metadata={"endpoint": endpoint},
            )
            
            if response.status_code == 429:
                logger.warning("Companies House rate limit hit")
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            self.audit.log_fetch(
                operation="companies_house",
                url=url,
                domain="api.company-information.service.gov.uk",
                error=str(e),
                source_api="companies_house",
            )
            logger.error(f"Companies House request failed: {e}")
            return None
    
    def search_companies(
        self,
        query: str,
        company_type: Optional[str] = None,
        location: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Search for companies.
        
        Args:
            query: Search term
            company_type: e.g., "ltd", "plc"
            location: e.g., "London"
            max_results: Maximum to return
        """
        results = []
        start_index = 0
        items_per_page = 20
        
        while len(results) < max_results:
            params = {
                "q": query,
                "start_index": start_index,
                "items_per_page": items_per_page,
            }
            
            if company_type:
                params["type"] = company_type
            
            data = self._make_request("search/companies", params)
            if not data:
                break
            
            items = data.get("items", [])
            if not items:
                break
            
            results.extend(items)
            start_index += items_per_page
            
            # Rate limiting - 600 req / 5 min = 2 req/sec
            import time
            time.sleep(0.5)
        
        # Filter by location if specified
        if location:
            location_lower = location.lower()
            results = [
                r for r in results
                if location_lower in r.get("address", {}).get("locality", "").lower()
                or location_lower in r.get("address_snippet", "").lower()
            ]
        
        logger.info(f"Found {len(results[:max_results])} companies for '{query}'")
        return results[:max_results]
    
    def get_company_details(self, company_number: str) -> Optional[Dict]:
        """Get full company details."""
        return self._make_request(f"company/{company_number}")
    
    def get_company_officers(self, company_number: str) -> Optional[Dict]:
        """Get company officers (directors)."""
        return self._make_request(f"company/{company_number}/officers")
    
    def get_filing_history(self, company_number: str) -> Optional[Dict]:
        """Get company filing history."""
        return self._make_request(f"company/{company_number}/filing-history")
    
    def to_lead(self, company_data: Dict) -> Dict:
        """Convert Companies House data to lead format."""
        address = company_data.get("registered_office_address", {})
        
        lead = {
            "source_api": "companies_house",
            "source_url": f"https://find-and-update.company-information.service.gov.uk/company/{company_data.get('company_number', '')}",
            "date_discovered": datetime.utcnow().isoformat(),
            
            "country": "UK",
            "business_name": company_data.get("company_name", ""),
            "registered_name": company_data.get("company_name", ""),
            "company_number": company_data.get("company_number", ""),
            "company_status": company_data.get("company_status", ""),
            "company_type": company_data.get("type", ""),
            
            "business_address": ", ".join(filter(None, [
                address.get("address_line_1", ""),
                address.get("address_line_2", ""),
                address.get("locality", ""),
                address.get("postal_code", ""),
                address.get("country", ""),
            ])),
            
            "date_of_creation": company_data.get("date_of_creation"),
            "sic_codes": company_data.get("sic_codes", []),
        }
        
        return lead
    
    def search_ecommerce_companies(
        self,
        location: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Search for e-commerce related companies.
        Uses SIC codes for retail/online businesses.
        """
        # SIC codes for retail and e-commerce
        ecommerce_sic = [
            "47910",  # Retail sale via mail order houses or via Internet
            "47990",  # Other retail sale not in stores, stalls or markets
            "47190",  # Other retail sale in non-specialised stores
            "47510",  # Retail sale of textiles in specialised stores
            "47520",  # Retail sale of hardware, paints and glass
            "47530",  # Retail sale of carpets, rugs, wall and floor coverings
            "47540",  # Retail sale of electrical household appliances
            "47550",  # Retail sale of musical instruments
            "47560",  # Retail sale of games and toys
            "47570",  # Retail sale of clothing
            "47580",  # Retail sale of footwear and leather goods
            "47590",  # Retail sale of furniture, lighting equipment and other household articles
            "47610",  # Retail sale of books in specialised stores
            "47620",  # Retail sale of newspapers and stationery
            "47630",  # Retail sale of music and video recordings
            "47640",  # Retail sale of sporting equipment
            "47650",  # Retail sale of games and toys
            "47710",  # Retail sale of clothing in specialised stores
            "47720",  # Retail sale of footwear and leather goods
            "47730",  # Retail sale of pharmaceutical goods
            "47740",  # Retail sale of medical and orthopaedic goods
            "47750",  # Retail sale of cosmetic and toilet articles
            "47760",  # Retail sale of flowers, plants, seeds, fertilisers
            "47770",  # Retail sale of watches and jewellery
            "47780",  # Retail sale of other new goods
            "47790",  # Retail sale of second-hand goods
            "47810",  # Retail sale via stalls and markets
            "47820",  # Retail sale via mail order houses or via Internet
            "47890",  # Retail sale not in stores, stalls or markets
        ]
        
        results = []
        
        for sic in ecommerce_sic[:5]:  # Limit SIC searches
            query = f"sic:{sic}"
            companies = self.search_companies(query, location=location, max_results=20)
            results.extend(companies)
        
        # Also search by keyword
        keyword_results = self.search_companies(
            "online shop OR ecommerce OR online store",
            location=location,
            max_results=50
        )
        results.extend(keyword_results)
        
        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            num = r.get("company_number")
            if num and num not in seen:
                seen.add(num)
                unique.append(r)
        
        return unique[:max_results]