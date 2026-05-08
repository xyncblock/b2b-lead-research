#!/usr/bin/env python3
"""
Agent Runner - Robust execution with retry logic and health tracking.
All agents go through this to ensure reliability.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# State tracking
STATE_DIR = Path("/home/expertfox/.openclaw/workspace/agents/state")
STATE_DIR.mkdir(exist_ok=True)

class AgentRunner:
    """Runs agents with retry logic and tracks health."""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.state_file = STATE_DIR / f"{agent_name}.json"
        self.state = self._load_state()
    
    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "runs": [],
            "consecutive_errors": 0,
            "total_runs": 0,
            "total_errors": 0,
        }
    
    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)
    
    def run(self, task_func, *args, **kwargs):
        """Run a task with retries and track health."""
        start_time = time.time()
        last_error = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                result = task_func(*args, **kwargs)
                
                # Success
                self.state["runs"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration": round(time.time() - start_time, 2),
                    "success": True,
                    "attempt": attempt,
                })
                self.state["consecutive_errors"] = 0
                self.state["total_runs"] += 1
                self._save_state()
                
                return {"success": True, "result": result, "attempts": attempt}
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)  # Exponential backoff
        
        # All retries failed
        self.state["runs"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "duration": round(time.time() - start_time, 2),
            "success": False,
            "error": last_error,
            "attempts": self.MAX_RETRIES,
        })
        self.state["consecutive_errors"] += 1
        self.state["total_errors"] += 1
        self.state["total_runs"] += 1
        self._save_state()
        
        return {"success": False, "error": last_error, "attempts": self.MAX_RETRIES}
    
    def get_health(self):
        """Get agent health status."""
        runs = self.state["runs"]
        if not runs:
            return {"status": "unknown", "message": "No runs yet"}
        
        last_run = runs[-1]
        consecutive_errors = self.state["consecutive_errors"]
        
        if consecutive_errors >= 3:
            return {
                "status": "critical",
                "message": f"{consecutive_errors} consecutive failures",
                "last_error": last_run.get("error", "Unknown"),
            }
        elif consecutive_errors > 0:
            return {
                "status": "warning",
                "message": f"{consecutive_errors} recent failures",
                "last_error": last_run.get("error", "Unknown"),
            }
        else:
            return {
                "status": "healthy",
                "message": f"Last run successful ({last_run['duration']}s)",
            }


def get_all_agents_health():
    """Get health report for all agents."""
    report = []
    for state_file in STATE_DIR.glob("*.json"):
        agent_name = state_file.stem
        with open(state_file) as f:
            state = json.load(f)
        
        runs = state.get("runs", [])
        if runs:
            last_run = runs[-1]
            report.append({
                "agent": agent_name,
                "status": "healthy" if last_run["success"] else "error",
                "last_run": last_run["timestamp"],
                "duration": last_run.get("duration", 0),
                "total_runs": state["total_runs"],
                "total_errors": state["total_errors"],
                "consecutive_errors": state["consecutive_errors"],
            })
    
    return report


if __name__ == "__main__":
    # Test
    runner = AgentRunner("test")
    
    def sample_task():
        return "Hello from agent"
    
    result = runner.run(sample_task)
    print(json.dumps(result, indent=2))
    print(json.dumps(runner.get_health(), indent=2))
