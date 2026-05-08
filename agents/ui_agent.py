#!/usr/bin/env python3
"""
UI/UX Agent - Quick dashboard improvements with retry logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_runner import AgentRunner

def run_ui_audit():
    """Quick UI audit and improvements."""
    results = []
    
    dashboard_path = Path("/home/expertfox/.openclaw/workspace/b2b-lead-research/dashboard/app.py")
    
    if not dashboard_path.exists():
        return "❌ Dashboard file not found"
    
    content = dashboard_path.read_text()
    changes_made = []
    
    # Check 1: Add page config if missing
    if "st.set_page_config" not in content:
        # Add at the beginning
        new_content = 'st.set_page_config(page_title="B2B Lead Research", layout="wide")\n\n' + content
        dashboard_path.write_text(new_content)
        changes_made.append("Added page config (title + wide layout)")
        content = new_content
    
    # Check 2: Improve sidebar title
    if "sidebar" in content.lower() and "B2B Lead Research" not in content:
        content = content.replace(
            'st.sidebar.title(',
            'st.sidebar.title("🎯 B2B Lead Research")\n# st.sidebar.title('
        )
        # Only apply if we actually changed something
        if content != dashboard_path.read_text():
            dashboard_path.write_text(content)
            changes_made.append("Improved sidebar title")
    
    # Check 3: Add loading spinner example if missing
    if "st.spinner" not in content:
        # This is a simple check - we won't auto-add complex code
        results.append("ℹ️ Consider adding loading spinners for better UX")
    
    if changes_made:
        results.append(f"✅ Changes made: {', '.join(changes_made)}")
    else:
        results.append("✅ Dashboard looks good, no changes needed")
    
    return "\n".join(results)


def main():
    runner = AgentRunner("ui-designer")
    result = runner.run(run_ui_audit)
    
    print("=" * 50)
    print("UI/UX AGENT REPORT")
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
