"""
Website quality scoring engine.
Scores 0-100 where lower = needs improvement.
"""
from typing import Dict, Optional
from datetime import datetime


class ScoringEngine:
    """
    Score websites on quality metrics.
    """
    
    # Scoring weights (total = 100)
    WEIGHTS = {
        "ssl": 10,
        "mobile": 15,
        "page_speed": 15,
        "design": 15,
        "social": 10,
        "checkout": 15,
        "content_freshness": 10,
        "domain_email": 10,
    }
    
    def score_ssl(self, has_ssl: Optional[bool]) -> float:
        """SSL certificate (10 pts)."""
        if has_ssl is None:
            return 5
        return 10 if has_ssl else 0
    
    def score_mobile(self, mobile_friendly: Optional[bool]) -> float:
        """Mobile responsive (15 pts)."""
        if mobile_friendly is None:
            return 7.5
        return 15 if mobile_friendly else 0
    
    def score_page_speed(self, score: Optional[float]) -> float:
        """Page speed >70 (15 pts)."""
        if score is None:
            return 7.5
        if score >= 90:
            return 15
        elif score >= 70:
            return 10
        elif score >= 50:
            return 5
        else:
            return 0
    
    def score_design(self, metrics: Optional[Dict]) -> float:
        """Modern design (15 pts)."""
        if not metrics:
            return 7.5
        
        score = 0
        if metrics.get("has_viewport_meta"):
            score += 3
        if metrics.get("has_schema_markup"):
            score += 3
        if metrics.get("has_favicon"):
            score += 2
        if metrics.get("has_modern_css"):
            score += 4
        if not metrics.get("has_flash", False):
            score += 2
        if not metrics.get("has_tables_for_layout", False):
            score += 1
        
        return min(score, 15)
    
    def score_social(self, handles: Optional[list]) -> float:
        """Working social links (10 pts)."""
        if not handles:
            return 0
        
        count = len(handles)
        if count >= 3:
            return 10
        elif count == 2:
            return 7
        elif count == 1:
            return 4
        return 0
    
    def score_checkout(self, functional: Optional[bool]) -> float:
        """Checkout functional (15 pts)."""
        if functional is None:
            return 7.5
        return 15 if functional else 0
    
    def score_content_freshness(self, last_update: Optional[datetime]) -> float:
        """Recent content <90 days (10 pts)."""
        if last_update is None:
            return 3
        
        days_since = (datetime.utcnow() - last_update).days
        if days_since < 30:
            return 10
        elif days_since < 90:
            return 7
        elif days_since < 180:
            return 4
        else:
            return 0
    
    def score_domain_email(self, email: Optional[str]) -> float:
        """Professional domain email (10 pts)."""
        if not email:
            return 0
        
        # Check if email uses domain (not gmail, yahoo, etc.)
        free_providers = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", 
                         "aol.com", "icloud.com", "mail.com", "protonmail.com"]
        domain = email.split("@")[1].lower() if "@" in email else ""
        
        if domain and domain not in free_providers:
            return 10
        return 3
    
    def calculate(self, lead: Dict) -> float:
        """
        Calculate total quality score.
        Returns 0-100 (higher = better website).
        """
        scores = {
            "ssl": self.score_ssl(lead.get("has_ssl")),
            "mobile": self.score_mobile(lead.get("mobile_friendly")),
            "page_speed": self.score_page_speed(lead.get("page_speed_score")),
            "design": self.score_design(lead.get("design_metrics")),
            "social": self.score_social(lead.get("social_handles")),
            "checkout": self.score_checkout(lead.get("checkout_functional")),
            "content_freshness": self.score_content_freshness(lead.get("last_content_update")),
            "domain_email": self.score_domain_email(lead.get("business_email_generic") or lead.get("business_email_named")),
        }
        
        total = sum(scores.values())
        return round(total, 1)
    
    def determine_priority(self, score: float, lead: Dict) -> str:
        """
        Determine outreach priority.
        
        HOT: score <40 + revenue signals
        WARM: score 40-65
        COLD: score >65
        """
        if score < 40:
            # Check revenue signals
            has_signals = self._has_revenue_signals(lead)
            if has_signals:
                return "HOT"
            else:
                return "WARM"  # Low score but no signals = warm
        elif score < 65:
            return "WARM"
        else:
            return "COLD"
    
    def _has_revenue_signals(self, lead: Dict) -> bool:
        """Check if business shows revenue signals."""
        signals = 0
        
        # Google reviews
        if lead.get("google_review_count", 0) > 10:
            signals += 1
        if lead.get("google_rating", 0) > 3.5:
            signals += 1
        
        # Social presence
        social = lead.get("social_handles", [])
        if len(social) >= 2:
            signals += 1
        
        # Products
        if lead.get("estimated_product_count", 0) > 5:
            signals += 1
        
        # Has phone
        if lead.get("business_phone"):
            signals += 1
        
        # Has professional email
        if lead.get("business_email_generic"):
            signals += 1
        
        return signals >= 3
    
    def generate_opportunity(self, lead: Dict) -> str:
        """Generate 1-sentence improvement opportunity."""
        issues = []
        
        if not lead.get("has_ssl", True):
            issues.append("missing SSL")
        if not lead.get("mobile_friendly", True):
            issues.append("not mobile-friendly")
        if lead.get("page_speed_score", 100) < 50:
            issues.append("very slow")
        if not lead.get("checkout_functional", True):
            issues.append("checkout issues")
        if lead.get("ecommerce_platform") in ["custom", None]:
            issues.append("outdated platform")
        if not lead.get("social_handles"):
            issues.append("no social presence")
        
        if not issues:
            return "Minor UX improvements could boost conversions"
        
        return f"Website has {', '.join(issues[:3])} — rebuild recommended"