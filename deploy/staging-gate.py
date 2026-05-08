#!/usr/bin/env python3
"""Staging deployment gate — checks approval requests and deploys to Render."""

import json
import os
import subprocess
import sys
from pathlib import Path

REQUEST_FILE = Path("/tmp/staging-approval-request.json")
STATE_FILE = Path("/home/expertfox/.openclaw/workspace/deploy/.staging-gate-state.json")
RENDER_API_KEY = "rnd_4Oy4OQa1ZMFDmEtTtUTXhiPK1SZI"
DEPLOY_DIR = Path("/home/expertfox/.openclaw/workspace/deploy")
DEPLOY_SCRIPT = DEPLOY_DIR / "render-deploy.py"

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"notified": False, "last_status": None}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def send_telegram(text):
    # Use openclaw message tool via subprocess or rely on stdout being sent
    # For cron, we'll print and let the wrapper handle it
    print(f"[NOTIFY] {text}")

def deploy():
    if not DEPLOY_SCRIPT.exists():
        print(f"[ERROR] Deploy script not found: {DEPLOY_SCRIPT}")
        return False
    try:
        result = subprocess.run(
            ["python", str(DEPLOY_SCRIPT), "approve"],
            cwd=str(DEPLOY_DIR),
            env={**os.environ, "RENDER_API_KEY": RENDER_API_KEY},
            capture_output=True,
            text=True,
            check=True,
        )
        print("[DEPLOY] Success:", result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print("[DEPLOY] Failed:", e.stderr.strip() or e.stdout.strip())
        return False

def main():
    state = load_state()

    if not REQUEST_FILE.exists():
        if state["last_status"] is not None:
            print("[INFO] No pending request. Previous request cleared.")
            state["last_status"] = None
            state["notified"] = False
            save_state(state)
        else:
            print("[OK] No staging approval request pending.")
        sys.exit(0)

    try:
        request = json.loads(REQUEST_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] Failed to read request file: {e}")
        sys.exit(1)

    status = request.get("status", "pending")
    request_id = request.get("id", "unknown")

    # Only act on status changes
    if status == state.get("last_status") and status in ("approved", "denied"):
        print(f"[OK] Already handled status '{status}' for request {request_id}")
        sys.exit(0)

    if status == "approved":
        print(f"[ACTION] Request {request_id} approved. Deploying to Render...")
        if deploy():
            state["last_status"] = "approved"
            state["notified"] = True
            save_state(state)
            # Clean up after successful deploy
            REQUEST_FILE.unlink(missing_ok=True)
            print("[SUCCESS] Staging deployed and request cleaned up.")
        else:
            print("[FAILURE] Deploy failed. Request kept for retry.")
            sys.exit(1)

    elif status == "denied":
        print(f"[ACTION] Request {request_id} denied. Cancelling...")
        REQUEST_FILE.unlink(missing_ok=True)
        state["last_status"] = "denied"
        state["notified"] = False
        save_state(state)
        print("[CANCELLED] Request denied and cleaned up.")

    elif status == "pending":
        if not state["notified"]:
            send_telegram("🚀 Staging deployment pending. Reply 'approve staging' to deploy or 'deny staging' to cancel")
            state["notified"] = True
            state["last_status"] = "pending"
            save_state(state)
        else:
            print(f"[WAITING] Request {request_id} still pending. Already notified.")

    else:
        print(f"[WARN] Unknown status '{status}' for request {request_id}")

if __name__ == "__main__":
    main()
