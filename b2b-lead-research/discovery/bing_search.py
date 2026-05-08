"""
Bing Search Scraper
Extracts results from Bing search pages
"""

import requests
import re
import base64
import time
from typing import List, Dict
from urllib.parse import urlparse


class BingSearchCollector:
    """Search using Bing"""
    
    def __init__(self):
        self.session = requests.Session()
        # Don't set headers - let requests use defaults
        # Bing blocks when we set User-Agent
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search Bing and return results"""
        try:
            resp = self.session.get(
                'https://www.bing.com/search',
                params={'q': query},
                timeout=15
            )
            resp.raise_for_status()
            
            return self._parse_results(resp.text, max_results)
            
        except Exception as e:
            print(f"Bing search failed: {e}")
            return []
    
    def _decode_bing_url(self, href: str) -> str:
        """Decode Bing redirect URL to get actual URL"""
        try:
            # Extract u parameter
            u_match = re.search(r'u=([a-zA-Z0-9_-]+)', href)
            if u_match:
                encoded = u_match.group(1)
                
                # Remove a1 prefix if present
                if encoded.startswith('a1'):
                    encoded = encoded[2:]
                
                # Pad to multiple of 4
                padding = 4 - len(encoded) % 4
                if padding != 4:
                    encoded += '=' * padding
                
                decoded = base64.urlsafe_b64decode(encoded)
                url = decoded.decode('utf-8', errors='ignore')
                
                if url.startswith('http'):
                    return url
        except Exception as e:
            pass
        
        return ""
    
    def _parse_results(self, html: str, max_results: int) -> List[Dict]:
        """Parse Bing HTML results"""
        results = []
        
        # Find all h2 blocks (contain titles and links)
        h2_blocks = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
        
        for block in h2_blocks[:max_results]:
            # Extract href
            href_match = re.search(r'href="([^"]+)"', block)
            # Extract title text
            title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
            
            if href_match and title_match:
                href = href_match.group(1)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                
                # Decode Bing redirect URL
                url = self._decode_bing_url(href)
                
                if url and 'bing.com' not in url:
                    domain = self._extract_domain(url)
                    results.append({
                        'title': title,
                        'url': url,
                        'domain': domain
                    })
        
        return results
    
    def extract_emails(self, url: str) -> List[str]:
        """Extract emails from website"""
        try:
            resp = self.session.get(url, timeout=10)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
            
            # Filter
            skip = {'example.com', 'test.com', 'domain.com', 'gmail.com', 'yahoo.com', 'hotmail.com'}
            valid = []
            for email in emails:
                domain = email.split('@')[1].lower()
                if domain not in skip and 'icon' not in email and 'sentry' not in email:
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
    collector = BingSearchCollector()
    results = collector.search("ecommerce store UK", max_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  {r['title'][:50]} - {r['domain']}")
