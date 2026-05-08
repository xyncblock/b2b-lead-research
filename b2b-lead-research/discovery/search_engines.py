"""
Multi-search engine scraper with fallback
"""

import requests
import re
import time
import logging
from typing import List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MultiSearchCollector:
    """Search multiple engines to avoid blocks"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search using multiple engines"""
        
        # Try StartPage first
        results = self._search_startpage(query, max_results)
        if results:
            return results
        
        # Fallback to other engines
        time.sleep(2)
        results = self._search_brave(query, max_results)
        if results:
            return results
        
        return []
    
    def _search_startpage(self, query: str, max_results: int) -> List[Dict]:
        """Search StartPage"""
        try:
            resp = self.session.get(
                'https://www.startpage.com/sp/search',
                params={'query': query, 'cat': 'web'},
                timeout=15
            )
            resp.raise_for_status()
            
            results = []
            # Parse results
            links = re.findall(r'class="w-gl__result-url"[^>]*href="(https?://[^"]+)"', resp.text)
            titles = re.findall(r'class="w-gl__result-title"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            
            for url, title in zip(links[:max_results], titles[:max_results]):
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                results.append({
                    'url': url,
                    'title': clean_title,
                    'domain': self._extract_domain(url)
                })
            
            return results
            
        except Exception as e:
            logger.warning(f"StartPage failed: {e}")
            return []
    
    def _search_brave(self, query: str, max_results: int) -> List[Dict]:
        """Search Brave"""
        try:
            resp = self.session.get(
                'https://search.brave.com/search',
                params={'q': query},
                timeout=15
            )
            
            results = []
            links = re.findall(r'href="(https?://[^"]+)"[^>]*class="result-header"', resp.text)
            titles = re.findall(r'class="snippet-title"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
            
            for url, title in zip(links[:max_results], titles[:max_results]):
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                results.append({
                    'url': url,
                    'title': clean_title,
                    'domain': self._extract_domain(url)
                })
            
            return results
            
        except Exception as e:
            logger.warning(f"Brave failed: {e}")
            return []
    
    def extract_emails(self, url: str) -> List[str]:
        """Extract emails from website"""
        try:
            resp = self.session.get(url, timeout=10)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
            
            # Filter
            skip = {'example.com', 'test.com', 'domain.com', 'gmail.com', 'yahoo.com'}
            valid = []
            for email in emails:
                domain = email.split('@')[1].lower()
                if domain not in skip and 'icon' not in email:
                    valid.append(email.lower())
            
            return list(set(valid))
            
        except Exception as e:
            return []
    
    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.replace('www.', '')
        except:
            return ''


if __name__ == "__main__":
    collector = MultiSearchCollector()
    results = collector.search("ecommerce store UK", max_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  {r['title'][:50]} - {r['domain']}")
