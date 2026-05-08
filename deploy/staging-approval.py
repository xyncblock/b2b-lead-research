#!/usr/bin/env python3
"""
Staging Deployment Approval System

This script sends a Telegram message to Ak requesting approval
before deploying to staging. It blocks until approved or denied.

Usage:
    python staging-approval.py --commit abc123 --branch feature-x
"""

import argparse
import os
import sys
import time
import json
from datetime import datetime, timedelta

# Approval state file
APPROVAL_FILE = "/tmp/staging-approval.json"
TIMEOUT_MINUTES = 30


def request_approval(commit: str, branch: str, author: str) -> bool:
    """Send approval request and wait for response."""
    
    # Create approval request
    request = {
        "status": "pending",
        "commit": commit,
        "branch": branch,
        "author": author,
        "requested_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(minutes=TIMEOUT_MINUTES)).isoformat(),
    }
    
    with open(APPROVAL_FILE, "w") as f:
        json.dump(request, f, indent=2)
    
    # Print message that can be picked up by CI/CD
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  STAGING DEPLOYMENT AWAITING APPROVAL                        ║
╠══════════════════════════════════════════════════════════════╣
║  Commit:  {commit[:8]}                                          ║
║  Branch:  {branch[:40]:<40}           ║
║  Author:  {author[:40]:<40}           ║
╠══════════════════════════════════════════════════════════════╣
║  To approve:  Reply 'approve staging' in Telegram            ║
║  To deny:     Reply 'deny staging' in Telegram               ║
║  Expires:     {TIMEOUT_MINUTES} minutes                                    ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Wait for approval
    start_time = time.time()
    while time.time() - start_time < TIMEOUT_MINUTES * 60:
        if os.path.exists(APPROVAL_FILE):
            with open(APPROVAL_FILE, "r") as f:
                state = json.load(f)
            
            if state.get("status") == "approved":
                print("✅ Staging deployment APPROVED")
                return True
            elif state.get("status") == "denied":
                print("❌ Staging deployment DENIED")
                return False
        
        time.sleep(10)  # Check every 10 seconds
    
    print("⏰ Approval request EXPIRED")
    return False


def approve():
    """Mark staging as approved (called by Telegram bot)."""
    if not os.path.exists(APPROVAL_FILE):
        print("No pending approval request")
        return False
    
    with open(APPROVAL_FILE, "r") as f:
        state = json.load(f)
    
    state["status"] = "approved"
    state["approved_at"] = datetime.utcnow().isoformat()
    
    with open(APPROVAL_FILE, "w") as f:
        json.dump(state, f, indent=2)
    
    print("✅ Staging deployment approved")
    return True


def deny():
    """Mark staging as denied (called by Telegram bot)."""
    if not os.path.exists(APPROVAL_FILE):
        print("No pending approval request")
        return False
    
    with open(APPROVAL_FILE, "r") as f:
        state = json.load(f)
    
    state["status"] = "denied"
    state["denied_at"] = datetime.utcnow().isoformat()
    
    with open(APPROVAL_FILE, "w") as f:
        json.dump(state, f, indent=2)
    
    print("❌ Staging deployment denied")
    return True


def main():
    parser = argparse.ArgumentParser(description="Staging deployment approval")
    parser.add_argument("--commit", help="Commit hash")
    parser.add_argument("--branch", help="Branch name")
    parser.add_argument("--author", help="Commit author")
    parser.add_argument("--approve", action="store_true", help="Approve pending deployment")
    parser.add_argument("--deny", action="store_true", help="Deny pending deployment")
    
    args = parser.parse_args()
    
    if args.approve:
        sys.exit(0 if approve() else 1)
    elif args.deny:
        sys.exit(0 if deny() else 1)
    else:
        # Request approval
        approved = request_approval(
            commit=args.commit or "unknown",
            branch=args.branch or "unknown",
            author=args.author or "unknown",
        )
        sys.exit(0 if approved else 1)


if __name__ == "__main__":
    main()
