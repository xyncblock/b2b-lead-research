#!/usr/bin/env python3
"""
Render Deployment Manager
Handles dev auto-deploy and staging approval workflow.
"""

import os
import sys
import json
import requests
from datetime import datetime

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "rnd_4Oy4OQa1ZMFDmEtTtUTXhiPK1SZI")
RENDER_API_URL = "https://api.render.com/v1"

# Service IDs (will be fetched dynamically)
DEV_SERVICE = "b2b-leads-dev"
STAGING_SERVICE = "b2b-leads-staging"


def get_services():
    """List all Render services."""
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    
    try:
        resp = requests.get(
            f"{RENDER_API_URL}/services",
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Failed to fetch services: {e}")
        return []


def deploy_service(service_id: str) -> bool:
    """Trigger a deployment for a service."""
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    try:
        resp = requests.post(
            f"{RENDER_API_URL}/services/{service_id}/deploys",
            headers=headers,
            json={"clearCache": "do_not_clear"},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"✅ Deploy triggered: {data.get('id', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Deploy failed: {e}")
        return False


def get_service_url(service_name: str) -> str:
    """Get the URL for a service."""
    services = get_services()
    
    for service in services:
        if service.get("service") and service["service"].get("name") == service_name:
            return service["service"].get("url", "")
    
    return ""


def deploy_dev():
    """Deploy to dev environment (auto)."""
    print("🚀 Deploying to DEV...")
    
    services = get_services()
    for service in services:
        if service.get("service") and service["service"].get("name") == DEV_SERVICE:
            service_id = service["service"]["id"]
            if deploy_service(service_id):
                url = service["service"].get("url", "")
                print(f"🔗 Dev URL: {url}")
                return True
    
    print("❌ Dev service not found")
    return False


def request_staging_approval():
    """Request approval for staging deploy."""
    approval_file = "/tmp/staging-approval-request.json"
    
    request = {
        "status": "pending",
        "requested_at": datetime.now().isoformat(),
        "service": STAGING_SERVICE,
    }
    
    with open(approval_file, "w") as f:
        json.dump(request, f, indent=2)
    
    print("📨 Staging approval request created")
    print("Reply 'approve staging' to deploy or 'deny staging' to cancel")
    return True


def deploy_staging():
    """Deploy to staging (after approval)."""
    print("🚀 Deploying to STAGING...")
    
    services = get_services()
    for service in services:
        if service.get("service") and service["service"].get("name") == STAGING_SERVICE:
            service_id = service["service"]["id"]
            if deploy_service(service_id):
                url = service["service"].get("url", "")
                print(f"🔗 Staging URL: {url}")
                return True
    
    print("❌ Staging service not found")
    return False


def check_staging_status():
    """Check if staging deployment is approved."""
    approval_file = "/tmp/staging-approval-request.json"
    
    if not os.path.exists(approval_file):
        return None
    
    with open(approval_file) as f:
        request = json.load(f)
    
    return request.get("status")


def approve_staging():
    """Approve staging deployment."""
    approval_file = "/tmp/staging-approval-request.json"
    
    if not os.path.exists(approval_file):
        print("❌ No pending staging request")
        return False
    
    with open(approval_file) as f:
        request = json.load(f)
    
    request["status"] = "approved"
    request["approved_at"] = datetime.now().isoformat()
    
    with open(approval_file, "w") as f:
        json.dump(request, f, indent=2)
    
    print("✅ Staging approved! Deploying now...")
    return deploy_staging()


def deny_staging():
    """Deny staging deployment."""
    approval_file = "/tmp/staging-approval-request.json"
    
    if not os.path.exists(approval_file):
        print("❌ No pending staging request")
        return False
    
    with open(approval_file) as f:
        request = json.load(f)
    
    request["status"] = "denied"
    request["denied_at"] = datetime.now().isoformat()
    
    with open(approval_file, "w") as f:
        json.dump(request, f, indent=2)
    
    print("❌ Staging deployment denied")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python render-deploy.py [dev|staging|approve|deny|status]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "dev":
        deploy_dev()
    elif command == "staging":
        request_staging_approval()
    elif command == "approve":
        approve_staging()
    elif command == "deny":
        deny_staging()
    elif command == "status":
        status = check_staging_status()
        if status:
            print(f"Staging status: {status}")
        else:
            print("No pending staging request")
    else:
        print(f"Unknown command: {command}")
        print("Use: dev, staging, approve, deny, status")


if __name__ == "__main__":
    main()
