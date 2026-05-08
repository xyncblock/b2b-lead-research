#!/usr/bin/env python3
"""
QA Testing Agent - Quick health checks with retry logic.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_runner import AgentRunner

def run_qa_checks():
    """Run quick QA health checks."""
    results = []
    
    # Check 1: Key files exist
    base_path = Path("/home/expertfox/.openclaw/workspace/b2b-lead-research")
    key_files = [
        "pipeline.py",
        "dashboard/app.py",
        "discovery/google_places.py",
        "discovery/google_search.py",
    ]
    
    for file in key_files:
        path = base_path / file
        exists = path.exists()
        results.append(f"{'✅' if exists else '❌'} {file} {'exists' if exists else 'MISSING'}")
    
    # Check 2: Syntax validation
    for file in key_files:
        path = base_path / file
        if path.exists():
            try:
                compile(path.read_text(), file, 'exec')
                results.append(f"✅ {file} syntax OK")
            except SyntaxError as e:
                results.append(f"❌ {file} syntax error: {e}")
    
    # Check 3: Quick import test
    try:
        sys.path.insert(0, str(base_path))
        import pipeline
        results.append("✅ pipeline imports successfully")
    except Exception as e:
        results.append(f"❌ pipeline import failed: {e}")
    
    # Check 4: Test one collector (small query)
    try:
        from discovery.google_search import GoogleSearchCollector
        collector = GoogleSearchCollector()
        # Just test initialization, don't actually search
        results.append("✅ GoogleSearchCollector initializes")
    except Exception as e:
        results.append(f"❌ GoogleSearchCollector failed: {e}")
    
    return "\n".join(results)


def main():
    runner = AgentRunner("qa-tester")
    result = runner.run(run_qa_checks)
    
    print("=" * 50)
    print("QA AGENT REPORT")
    print("=" * 50)
    
    if result["success"]:
        print(result["result"])
    else:
        print(f"❌ Agent failed after {result['attempts']} attempts")
        print(f"Error: {result.get('error', 'Unknown')}")
    
    health = runner.get_health()
    print(f"\nHealth: {health['status']} - {health['message']}")
    
    return result


if __name__ == "__main__":
    main()
