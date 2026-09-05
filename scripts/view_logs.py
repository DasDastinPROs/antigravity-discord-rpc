import os
import sys
import json

USER_PROFILE = os.environ.get("USERPROFILE", "")
STATE_FILE = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "state.json")
LOG_FILE = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "logs", "activity.log")

print("=" * 65)
print("      ANTIGRAVITY CLI DISCORD RPC & ACTIVITY LOGGER")
print("=" * 65)

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st = json.load(f)
        print("\n[Live State Snapshot]")
        print(f"  Model:            {st.get('model_name')}")
        print(f"  Thinking Effort:  {st.get('thinking_effort')}")
        print(f"  Status:           {st.get('status')}")
        print(f"  Action:           {st.get('action')}")
        print(f"  Files Modified:   {st.get('files_modified_count', 0)} file(s)")
        for fmod in st.get("files_modified", [])[:5]:
            print(f"    - {os.path.basename(fmod)} ({fmod})")
        lines_add = st.get('lines_added', 0)
        lines_del = st.get('lines_removed', 0)
        if lines_add or lines_del:
            print(f"  Lines Changed:    +{lines_add} / -{lines_del} lines")
        print(f"  Workspace:        {st.get('workspace_name')}")
        if st.get('git_branch'):
            print(f"  Git Branch:       🌿 {st.get('git_branch')}")
        print(f"  Step:             {st.get('step_index')}")
        print(f"  Tool Calls:       {st.get('tool_calls_count')}")
    except Exception as e:
        print(f"Error reading state: {e}")

if os.path.exists(LOG_FILE):
    print("\n[Recent Activity Log - Last 10 Events]")
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        for l in lines[-10:]:
            entry = json.loads(l)
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            ev = entry.get("event", "")
            act = entry.get("action", "")
            branch = entry.get("git_branch", "")
            b_info = f" [🌿 {branch}]" if branch else ""
            print(f"  [{ts}] [{ev:<14}] {act}{b_info}")
    except Exception as e:
        print(f"Error reading log: {e}")

print("=" * 65)
