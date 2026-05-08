#!/usr/bin/env python3
"""
Hourly Report Agent - Compiles what all agents did in the last hour.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_DIR = Path("/home/expertfox/.openclaw/workspace/agents/state")

def generate_hourly_report():
    """Generate report of all agent activity in the last hour."""
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("📊 HOURLY AGENT REPORT")
    report_lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("=" * 60)
    
    one_hour_ago = datetime.now() - timedelta(hours=1)
    
    total_runs = 0
    total_success = 0
    total_errors = 0
    
    for state_file in sorted(STATE_DIR.glob("*.json")):
        agent_name = state_file.stem
        
        with open(state_file) as f:
            state = json.load(f)
        
        runs = state.get("runs", [])
        
        # Filter runs from last hour
        recent_runs = []
        for run in runs:
            run_time = datetime.fromisoformat(run["timestamp"])
            if run_time > one_hour_ago:
                recent_runs.append(run)
        
        if not recent_runs:
            continue
        
        report_lines.append(f"\n🤖 {agent_name.upper()}")
        report_lines.append("-" * 40)
        
        success_count = sum(1 for r in recent_runs if r["success"])
        error_count = len(recent_runs) - success_count
        
        total_runs += len(recent_runs)
        total_success += success_count
        total_errors += error_count
        
        report_lines.append(f"   Runs: {len(recent_runs)} | ✅ {success_count} | ❌ {error_count}")
        
        # Show last run details
        last_run = recent_runs[-1]
        status = "✅" if last_run["success"] else "❌"
        report_lines.append(f"   Last: {status} {last_run['duration']}s ({last_run['timestamp'][:19]})")
        
        if not last_run["success"] and "error" in last_run:
            report_lines.append(f"   Error: {last_run['error'][:100]}")
        
        # Show consecutive errors
        consecutive = state.get("consecutive_errors", 0)
        if consecutive > 0:
            report_lines.append(f"   ⚠️  {consecutive} consecutive errors")
    
    # Summary
    report_lines.append("\n" + "=" * 60)
    report_lines.append("📈 SUMMARY")
    report_lines.append("=" * 60)
    report_lines.append(f"Total Runs: {total_runs}")
    report_lines.append(f"Successful: {total_success}")
    report_lines.append(f"Failed: {total_errors}")
    report_lines.append(f"Success Rate: {(total_success/max(total_runs,1)*100):.1f}%")
    
    if total_errors == 0:
        report_lines.append("\n🎉 All agents healthy!")
    elif total_errors < 3:
        report_lines.append("\n⚠️  Some agents having issues")
    else:
        report_lines.append("\n🚨 Multiple agent failures - needs attention")
    
    return "\n".join(report_lines)


def main():
    report = generate_hourly_report()
    print(report)
    
    # Save to file
    report_file = Path("/home/expertfox/.openclaw/workspace/agents/reports")
    report_file.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    report_path = report_file / f"report-{timestamp}.txt"
    report_path.write_text(report)
    
    print(f"\n💾 Report saved: {report_path}")
    
    return report


if __name__ == "__main__":
    main()
