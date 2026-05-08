"""
Consent classifier for email addresses.
Separates generic business emails (PECR-safe) from named individual emails.
"""
import re
from typing import Dict, Optional, List


class ConsentClassifier:
    """
    Classify email addresses for PECR/GDPR compliance.
    """
    
    # Generic business email patterns - PECR-safe for B2B
    GENERIC_PATTERNS = [
        r"^info@",
        r"^sales@",
        r"^contact@",
        r"^hello@",
        r"^support@",
        r"^enquiries@",
        r"^enquiry@",
        r"^orders@",
        r"^shop@",
        r"^admin@",
        r"^office@",
        r"^marketing@",
        r"^business@",
        r"^team@",
        r"^help@",
        r"^service@",
        r"^customerservice@",
        r"^customercare@",
        r"^care@",
        r"^general@",
        r"^mail@",
        r"^webmaster@",
        r"^press@",
        r"^media@",
        r"^partners@",
        r"^wholesale@",
        r"^trade@",
        r"^accounts@",
        r"^billing@",
        r"^payments@",
        r"^finance@",
        r"^legal@",
        r"^privacy@",
        r"^gdpr@",
        r"^dpo@",
        r"^data@",
        r"^feedback@",
        r"^complaints@",
        r"^returns@",
        r"^shipping@",
        r"^delivery@",
        r"^stock@",
        r"^inventory@",
        r"^purchasing@",
        r"^procurement@",
        r"^suppliers@",
        r"^careers@",
        r"^jobs@",
        r"^hr@",
        r"^recruitment@",
        r"^events@",
        r"^bookings@",
        r"^reservations@",
        r"^tickets@",
        r"^news@",
        r"^newsletter@",
        r"^subscribe@",
        r"^unsubscribe@",
        r"^abuse@",
        r"^security@",
        r"^noc@",
        r"^hostmaster@",
        r"^postmaster@",
    ]
    
    # Named individual patterns - require consent
    NAMED_INDICATORS = [
        r"^[a-z]+\.[a-z]+@",           # john.smith@
        r"^[a-z]+_[a-z]+@",             # john_smith@
        r"^[a-z]+[0-9]+@",              # john123@
        r"^[a-z]{2,20}@[a-z]+",         # john@company (short first name)
    ]
    
    # Role-based but still individual
    ROLE_BASED = [
        r"^ceo@",
        r"^founder@",
        r"^owner@",
        r"^director@",
        r"^manager@",
        r"^head@",
        r"^lead@",
        r"^chief@",
        r"^president@",
        r"^vp@",
        r"^md@",
    ]
    
    def classify_email(self, email: Optional[str]) -> Dict:
        """
        Classify an email address.
        
        Returns:
            {
                "email": str,
                "type": "generic" | "named" | "role" | "unknown",
                "consent_required": bool,
                "pecr_safe": bool,
                "reason": str,
            }
        """
        if not email or "@" not in email:
            return {
                "email": email,
                "type": "unknown",
                "consent_required": True,
                "pecr_safe": False,
                "reason": "invalid_or_missing",
            }
        
        email_lower = email.lower().strip()
        
        # Check generic patterns
        for pattern in self.GENERIC_PATTERNS:
            if re.search(pattern, email_lower):
                return {
                    "email": email,
                    "type": "generic",
                    "consent_required": False,
                    "pecr_safe": True,
                    "reason": "generic_business_address",
                }
        
        # Check role-based
        for pattern in self.ROLE_BASED:
            if re.search(pattern, email_lower):
                return {
                    "email": email,
                    "type": "role",
                    "consent_required": True,
                    "pecr_safe": False,
                    "reason": "role_based_individual",
                }
        
        # Check named indicators
        for pattern in self.NAMED_INDICATORS:
            if re.search(pattern, email_lower):
                return {
                    "email": email,
                    "type": "named",
                    "consent_required": True,
                    "pecr_safe": False,
                    "reason": "named_individual",
                }
        
        # Default: assume named individual if not clearly generic
        return {
            "email": email,
            "type": "named",
            "consent_required": True,
            "pecr_safe": False,
            "reason": "not_recognized_as_generic",
        }
    
    def classify_emails(self, emails: List[str]) -> Dict[str, Optional[Dict]]:
        """Classify multiple emails."""
        return {email: self.classify_email(email) for email in emails}
    
    def get_safe_email(self, emails: List[str]) -> Optional[str]:
        """Get first PECR-safe email from list."""
        for email in emails:
            result = self.classify_email(email)
            if result["pecr_safe"]:
                return email
        return None
    
    def get_consent_status(self, generic_email: Optional[str], named_email: Optional[str]) -> str:
        """
        Determine overall consent status for a lead.
        
        Returns:
            "b2b_legitimate_interest" - has generic email only
            "consent_required" - has named email
            "do_not_contact" - no valid email
        """
        if generic_email and not named_email:
            return "b2b_legitimate_interest"
        elif named_email:
            return "consent_required"
        else:
            return "do_not_contact"