#!/usr/bin/env python3
"""
Render Staging Approval Bot

This bot monitors your repo for staging branch pushes,
asks you for approval via Telegram, then triggers Render deploy.

Setup:
1. Set RENDER_API_KEY in environment
2. Set TELEGRAM_BOT_TOKEN (or use existing OpenClaw)
3. Run this as a cron job or webhook
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

# Config
RENDER_API_KEY = os.environ.get("RENDER_API_KEY")
RENDER_SERVICE_ID = os.environ.get("RENDER_STAGING_SERVICE_ID")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "yourusername/b2b-lead-research")
CHECK_INTERVAL = 60  # seconds

# State file
STATE_FILE = "/tmp/render-staging-state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_commit": None, "pending_approval": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_latest_staging_commit():
    """Check GitHub for latest staging commit."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/staging"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "sha": data["sha"][:7],
                "message": data["commit"]["message"],
                "author": data["commit"]["author"]["name"],
                "url": data["html_url"],
            }
    except Exception as e:
        print(f"Error checking GitHub: {e}")
    return None


def request_approval(commit_info):
    """Send approval request to Ak via Telegram."""
    message = f"""🚀 **Staging Deployment Pending**

**Commit:** `{commit_info['sha']}`
**Author:** {commit_info['author']}
**Message:** {commit_info['message']}

Reply with:
• `approve staging` → Deploy to staging
• `deny staging` → Cancel deployment

⏰ Expires in 30 minutes"""
    
    print(message)
    print("\n[Waiting for approval...]")
    return True


def deploy_to_render():
    """Trigger manual deploy on Render."""
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        print("❌ Missing RENDER_API_KEY or RENDER_SERVICE_ID")
        return False
    
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    try:
        resp = requests.post(url, headers=headers, json={}, timeout=30)
        if resp.status_code in (200, 201):
            print("✅ Staging deployment triggered on Render!")
            return True
        else:
            print(f"❌ Deploy failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error deploying: {e}")
        return False


def check_telegram_approval():
    """Check if Ak approved via Telegram."""
    # This would integrate with OpenClaw's message handling
    # For now, check a file that OpenClaw can write
    approval_file = "/tmp/staging-approval-response.json"
    if os.path.exists(approval_file):
        with open(approval_file, "r") as f:
            data = json.load(f)
        os.remove(approval_file)  # Consume it
        return data.get("action")  # "approve" or "deny"
    return None


def main():
    print("🔍 Render Staging Approval Bot started")
    print(f"Monitoring: {GITHUB_REPO}/staging")
    
    state = load_state()
    
    while True:
        commit = get_latest_staging_commit()
        
        if commit and commit["sha"] != state.get("last_commit"):
            print(f"\n🆕 New staging commit detected: {commit['sha']}")
            
            if request_approval(commit):
                state["pending_approval"] = True
                state["pending_commit"] = commit["sha"]
                save_state(state)
        
        # Check for approval response
        if state.get("pending_approval"):
            action = check_telegram_approval()
            
            if action == "approve":
                print("✅ Approval received! Deploying...")
                if deploy_to_render():
                    state["last_commit"] = state["pending_commit"]
                state["pending_approval"] = False
                save_state(state)
                
            elif action == "deny":
                print("❌ Deployment denied by Ak")
                state["pending_approval"] = False
                save_state(state)
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
