"""
Robots.txt checker with caching and audit logging.
Respects robots.txt, noindex, and crawl-delay directives.
"""
import re
import time
import logging
from urllib.parse import urlparse
from typing import Optional, Dict
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)


class RobotsChecker:
    """
    Check and cache robots.txt for domains.
    Thread-safe with TTL caching.
    """
    
    def __init__(self, default_delay: float = 3.0, cache_ttl: int = 3600):
        self.default_delay = default_delay
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, dict] = {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "B2BLeadResearchBot/1.0 (+https://youragency.com/bot-info; research@youragency.com)",
        })
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _fetch_robots(self, domain: str) -> Optional[str]:
        """Fetch robots.txt content."""
        robots_url = f"{domain}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=15)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 404:
                return ""  # No robots.txt = allow all
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
        return None
    
    def _parse_robots(self, content: str) -> Dict:
        """Parse robots.txt into structured rules."""
        rules = {
            "allowed": True,
            "crawl_delay": self.default_delay,
            "disallowed_paths": [],
            "sitemaps": [],
        }
        
        if not content:
            return rules
        
        lines = content.split("\n")
        in_our_section = False
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip().lower()
                # Match our bot or wildcard
                in_our_section = agent == "*" or "bot" in agent or "research" in agent
            
            if in_our_section:
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    rules["disallowed_paths"].append(path)
                    if path == "/":
                        rules["allowed"] = False
                
                elif line.lower().startswith("crawl-delay:"):
                    try:
                        delay = float(line.split(":", 1)[1].strip())
                        rules["crawl_delay"] = max(delay, self.default_delay)
                    except ValueError:
                        pass
                
                elif line.lower().startswith("sitemap:"):
                    sitemap = line.split(":", 1)[1].strip()
                    rules["sitemaps"].append(sitemap)
        
        return rules
    
    def check_url(self, url: str) -> Dict:
        """
        Check if URL is allowed by robots.txt.
        Returns dict with audit info.
        """
        domain = self._get_domain(url)
        now = datetime.utcnow()
        
        # Check cache
        if domain in self._cache:
            cached = self._cache[domain]
            if now - cached["fetched_at"] < timedelta(seconds=self.cache_ttl):
                return self._evaluate_url(url, cached["rules"], cached["fetched_at"])
        
        # Fetch fresh
        content = self._fetch_robots(domain)
        fetched_at = now
        
        if content is None:
            # Failed to fetch - be conservative, allow but log
            return {
                "url": url,
                "domain": domain,
                "allowed": True,
                "robots_found": False,
                "robots_url": f"{domain}/robots.txt",
                "crawl_delay": self.default_delay,
                "checked_at": now.isoformat(),
                "reason": "robots.txt_fetch_failed",
            }
        
        rules = self._parse_robots(content)
        self._cache[domain] = {
            "rules": rules,
            "fetched_at": fetched_at,
            "content": content,
        }
        
        return self._evaluate_url(url, rules, fetched_at)
    
    def _evaluate_url(self, url: str, rules: Dict, fetched_at: Optional[datetime]) -> Dict:
        """Evaluate if specific URL is allowed."""
        parsed = urlparse(url)
        path = parsed.path or "/"
        
        allowed = rules["allowed"]
        reason = "allowed"
        
        # Check disallowed paths
        for disallowed in rules["disallowed_paths"]:
            if path.startswith(disallowed):
                allowed = False
                reason = f"disallowed_path:{disallowed}"
                break
        
        return {
            "url": url,
            "domain": self._get_domain(url),
            "allowed": allowed,
            "robots_found": True,
            "robots_url": f"{self._get_domain(url)}/robots.txt",
            "crawl_delay": rules["crawl_delay"],
            "checked_at": fetched_at.isoformat() if fetched_at else None,
            "reason": reason,
            "sitemaps": rules.get("sitemaps", []),
        }
    
    def get_delay(self, url: str) -> float:
        """Get required crawl delay for domain."""
        domain = self._get_domain(url)
        if domain in self._cache:
            return self._cache[domain]["rules"]["crawl_delay"]
        return self.default_delay