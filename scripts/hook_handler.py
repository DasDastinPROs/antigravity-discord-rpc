import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS_PATH = os.path.join(PLUGIN_DIR, "settings.json")
CONFIG_PATH = os.path.join(PLUGIN_DIR, "config.json")

# Default paths
USER_PROFILE = os.environ.get("USERPROFILE", "")
DEFAULT_LOG_PATH = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "logs", "activity.log")
DEFAULT_STATE_PATH = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "state.json")
DAEMON_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "discord_daemon.py")
PID_FILE_PATH = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "daemon.pid")

def load_settings() -> Dict[str, Any]:
    """Load settings from settings.json, falling back to config.json if needed."""
    defaults = {
        "general": {
            "client_id": "1545821431181344850",
            "auto_spawn_daemon": True,
            "idle_timeout_seconds": 300,
            "update_interval_seconds": 2.5
        },
        "display": {
            "show_workspace": True,
            "workspace_alias": "",
            "show_git_branch": True,
            "show_thinking_effort": True,
            "show_files_changed": True,
            "show_file_names": True,
            "show_step_counter": True,
            "show_tool_counter": True,
            "timer_mode": "session"
        },
        "logging": {
            "enabled": True,
            "log_file_path": DEFAULT_LOG_PATH,
            "state_file_path": DEFAULT_STATE_PATH
        }
    }

    # First check settings.json
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    if isinstance(v, dict) and k in defaults:
                        defaults[k].update(v)
                    else:
                        defaults[k] = v
                return defaults
        except Exception:
            pass

    # Fallback check config.json
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                defaults["general"]["client_id"] = cfg.get("client_id", defaults["general"]["client_id"])
                defaults["general"]["auto_spawn_daemon"] = cfg.get("auto_spawn_daemon", True)
                defaults["display"]["show_workspace"] = cfg.get("show_workspace", True)
                defaults["display"]["show_thinking_effort"] = cfg.get("show_thinking_effort", True)
                defaults["display"]["show_files_changed"] = cfg.get("show_files_changed", True)
        except Exception:
            pass

    return defaults

def get_git_branch(workspace_path: str) -> Optional[str]:
    """Detect current Git branch directly from .git/HEAD in 0.1ms without subprocess overhead."""
    if not workspace_path or not os.path.exists(workspace_path):
        return None
    cur = os.path.abspath(workspace_path)
    while True:
        git_dir = os.path.join(cur, ".git")
        if os.path.isdir(git_dir):
            head_file = os.path.join(git_dir, "HEAD")
            if os.path.exists(head_file):
                try:
                    with open(head_file, "r", encoding="utf-8") as f:
                        line = f.read().strip()
                    if line.startswith("ref: refs/heads/"):
                        return line[len("ref: refs/heads/"):]
                    return line[:7]
                except Exception:
                    pass
        elif os.path.isfile(git_dir):
            try:
                with open(git_dir, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content.startswith("gitdir:"):
                    real_git = os.path.abspath(os.path.join(cur, content[len("gitdir:"):].strip()))
                    head_file = os.path.join(real_git, "HEAD")
                    if os.path.exists(head_file):
                        with open(head_file, "r", encoding="utf-8") as f:
                            line = f.read().strip()
                        if line.startswith("ref: refs/heads/"):
                            return line[len("ref: refs/heads/"):]
                        return line[:7]
            except Exception:
                pass
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

DAEMON_PORT = 49281

def is_daemon_running() -> bool:
    """Check if discord_daemon is running by testing if the daemon port is in use."""
    import socket
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_sock.bind(("127.0.0.1", DAEMON_PORT))
        test_sock.close()
        return False  # Port was free -> daemon not running
    except OSError:
        return True   # Port is occupied by running daemon

def spawn_daemon_if_needed(settings: Dict[str, Any]):
    """Launch detached daemon without console window if not running."""
    if not settings.get("general", {}).get("auto_spawn_daemon", True):
        return
    if is_daemon_running():
        return

    python_exe = sys.executable
    pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
    launcher = pythonw_exe if os.path.exists(pythonw_exe) else python_exe

    try:
        # Use PowerShell Start-Process to create a completely detached Windows process
        ps_cmd = f"Start-Process '{launcher}' -ArgumentList '\"{DAEMON_SCRIPT_PATH}\"' -WorkingDirectory '\"{PLUGIN_DIR}\"'"
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        try:
            creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
            subprocess.Popen(
                [launcher, DAEMON_SCRIPT_PATH],
                cwd=PLUGIN_DIR,
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
        except Exception:
            pass

def load_state(state_path: str) -> Dict[str, Any]:
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "conversation_id": "",
        "session_start_time": int(time.time()),
        "prompt_start_time": int(time.time()),
        "model_name": "Gemini",
        "thinking_effort": "High",
        "status": "idle",
        "action": "Ready",
        "action_raw": "",
        "current_tool": "",
        "current_target": "",
        "files_modified": [],
        "files_modified_count": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "diff_info": "",
        "step_index": 0,
        "tool_calls_count": 0,
        "workspace_name": "",
        "workspace_path": "",
        "git_branch": "",
        "updated_at": int(time.time()),
        "last_active": int(time.time())
    }

def save_state(state_path: str, state: Dict[str, Any]):
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    temp_path = state_path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(temp_path, state_path)
    except Exception:
        pass

def append_activity_log(log_path: str, log_entry: Dict[str, Any]):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def extract_thinking_effort(model_name: str) -> str:
    lower = model_name.lower()
    if "high" in lower:
        return "High"
    elif "medium" in lower or "med" in lower:
        return "Medium"
    elif "low" in lower:
        return "Low"
    elif "pro" in lower:
        return "High"
    elif "flash" in lower:
        return "Standard"
    return "High"

def parse_tool_summary(tool_name: str, args: Dict[str, Any], show_file_names: bool = True) -> tuple[str, str]:
    if not tool_name:
        return "", ""

    if tool_name in ("write_to_file", "replace_file_content"):
        target = args.get("TargetFile") or args.get("target_file") or ""
        basename = os.path.basename(target) if target else "file"
        file_label = basename if show_file_names else "file"
        action = f"Editing {file_label}" if tool_name == "replace_file_content" else f"Creating {file_label}"
        return action, target
    elif tool_name == "view_file":
        target = args.get("AbsolutePath") or args.get("path") or ""
        basename = os.path.basename(target) if target else "file"
        file_label = basename if show_file_names else "file"
        return f"Reading {file_label}", target
    elif tool_name == "run_command":
        cmd = args.get("CommandLine") or args.get("command") or ""
        cmd_snippet = (cmd[:35] + "...") if len(cmd) > 35 else cmd
        return f"Running: {cmd_snippet}" if cmd_snippet else "Running command", cmd
    elif tool_name in ("grep_search", "find_by_name"):
        query = args.get("Query") or args.get("Pattern") or ""
        return f"Searching: {query}" if query else "Searching codebase", query
    elif tool_name == "list_dir":
        dir_path = args.get("DirectoryPath") or ""
        return f"Listing {os.path.basename(dir_path) or 'dir'}", dir_path
    elif tool_name == "ask_question":
        return "Asking user question", ""
    else:
        return f"Executing {tool_name}", ""

def handle_hook(event_type: str):
    settings = load_settings()
    log_config = settings.get("logging", {})
    disp_config = settings.get("display", {})

    state_path = os.path.expanduser(log_config.get("state_file_path", DEFAULT_STATE_PATH))
    log_path = os.path.expanduser(log_config.get("log_file_path", DEFAULT_LOG_PATH))
    show_file_names = disp_config.get("show_file_names", True)
    custom_alias = disp_config.get("workspace_alias", "").strip()

    payload: Dict[str, Any] = {}
    try:
        raw_input = sys.stdin.read()
        if raw_input.strip():
            payload = json.loads(raw_input)
    except Exception:
        payload = {}

    state = load_state(state_path)
    now = int(time.time())
    iso_time = datetime.now(timezone.utc).isoformat()

    # Session Tracking
    conv_id = payload.get("conversationId") or state.get("conversation_id", "")
    if conv_id and conv_id != state.get("conversation_id"):
        state["conversation_id"] = conv_id
        state["session_start_time"] = now
        state["prompt_start_time"] = now
        state["files_modified"] = []
        state["files_modified_count"] = 0
        state["lines_added"] = 0
        state["lines_removed"] = 0
        state["diff_info"] = ""
        state["tool_calls_count"] = 0

    # Model name & Thinking effort
    model_name = payload.get("modelName") or state.get("model_name", "Gemini")
    if model_name and model_name != "auto":
        state["model_name"] = model_name
        state["thinking_effort"] = extract_thinking_effort(model_name)

    # Workspace & Git Branch
    workspaces = payload.get("workspacePaths") or []
    if workspaces:
        state["workspace_path"] = workspaces[0]
        raw_name = os.path.basename(workspaces[0].rstrip("/\\")) or workspaces[0]
        state["workspace_name"] = custom_alias if custom_alias else raw_name
        # Detect Git branch
        branch = get_git_branch(workspaces[0])
        if branch:
            state["git_branch"] = branch

    files_modified_set = set(state.get("files_modified", []))
    step_index = payload.get("stepIdx") or payload.get("step_index") or state.get("step_index", 0)
    state["step_index"] = step_index

    current_tool = state.get("current_tool", "")
    current_target = state.get("current_target", "")
    action_raw = event_type

    if event_type == "PreInvocation":
        state["status"] = "thinking"
        state["action"] = "Reasoning & Planning"
        state["prompt_start_time"] = now
        current_tool = ""
        current_target = ""
    elif event_type == "PostInvocation":
        state["status"] = "processing"
        if not current_tool:
            state["action"] = "Formulating response"
    elif event_type == "PreToolUse":
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        action, target = parse_tool_summary(tool_name, tool_args, show_file_names)
        current_tool = tool_name
        current_target = target
        action_raw = tool_name
        state["status"] = "tool_use"
        state["action"] = action
        state["current_tool"] = tool_name
        state["current_target"] = target
        state["tool_calls_count"] = state.get("tool_calls_count", 0) + 1

        # Code Diff Calculation (+lines / -lines)
        lines_add = 0
        lines_del = 0
        if tool_name == "replace_file_content":
            t_str = tool_args.get("TargetContent", "")
            r_str = tool_args.get("ReplacementContent", "")
            if t_str:
                lines_del = len(t_str.splitlines())
            if r_str:
                lines_add = len(r_str.splitlines())
        elif tool_name == "write_to_file":
            c_str = tool_args.get("CodeContent", "")
            t_f = tool_args.get("TargetFile", "")
            if c_str:
                lines_add = len(c_str.splitlines())
            if tool_args.get("Overwrite", False) and t_f and os.path.exists(t_f):
                try:
                    with open(t_f, "r", encoding="utf-8", errors="ignore") as f:
                        lines_del = len(f.read().splitlines())
                except Exception:
                    pass
        state["pending_lines_add"] = lines_add
        state["pending_lines_del"] = lines_del

    elif event_type == "PostToolUse":
        tool_name = state.get("current_tool", "")
        target = state.get("current_target", "")
        error = payload.get("error", "")

        if not error:
            add = state.pop("pending_lines_add", 0)
            dele = state.pop("pending_lines_del", 0)
            state["lines_added"] = state.get("lines_added", 0) + add
            state["lines_removed"] = state.get("lines_removed", 0) + dele

            diff_parts = []
            if state["lines_added"] > 0:
                diff_parts.append(f"+{state['lines_added']}")
            if state["lines_removed"] > 0:
                diff_parts.append(f"-{state['lines_removed']}")
            state["diff_info"] = " ".join(diff_parts) if diff_parts else ""

            if target and tool_name in ("write_to_file", "replace_file_content"):
                files_modified_set.add(target)
                state["files_modified"] = list(files_modified_set)
                state["files_modified_count"] = len(files_modified_set)
                basename = os.path.basename(target) if target else "file"
                diff_tag = f" (+{add}/-{dele})" if (add or dele) else ""
                state["action"] = f"Saved {basename}{diff_tag}" if show_file_names else f"Saved file{diff_tag}"

        state["status"] = "tool_completed"
        action_raw = tool_name
    elif event_type == "Stop":
        state["status"] = "idle"
        state["action"] = "Idle / Awaiting prompt"
        current_tool = ""
        current_target = ""

    state["action_raw"] = action_raw
    state["updated_at"] = now
    if state["status"] != "idle":
        state["last_active"] = now

    save_state(state_path, state)

    # Activity Logging
    if log_config.get("enabled", True):
        log_entry = {
            "timestamp": iso_time,
            "event": event_type,
            "conversation_id": conv_id,
            "model_name": state["model_name"],
            "thinking_effort": state["thinking_effort"],
            "status": state["status"],
            "action": state["action"],
            "current_tool": current_tool,
            "current_target": current_target,
            "files_modified_count": state.get("files_modified_count", 0),
            "files_modified": state.get("files_modified", []),
            "workspace": state.get("workspace_name", ""),
            "git_branch": state.get("git_branch", ""),
            "step_index": step_index,
            "tool_calls_count": state.get("tool_calls_count", 0),
            "payload": payload
        }
        append_activity_log(log_path, log_entry)

    spawn_daemon_if_needed(settings)

    # Output required contract JSON
    if event_type == "PreToolUse":
        sys.stdout.write(json.dumps({"decision": "allow"}))
    elif event_type == "Stop":
        sys.stdout.write(json.dumps({"decision": "stop"}))
    else:
        sys.stdout.write(json.dumps({}))
    sys.stdout.flush()

def main():
    event_type = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    try:
        handle_hook(event_type)
    except Exception as e:
        try:
            err_log = os.path.join(PLUGIN_DIR, "hook_errors.log")
            with open(err_log, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] Error in hook {event_type}: {e}\n")
        except Exception:
            pass

        if event_type == "PreToolUse":
            sys.stdout.write(json.dumps({"decision": "allow"}))
        elif event_type == "Stop":
            sys.stdout.write(json.dumps({"decision": "stop"}))
        else:
            sys.stdout.write(json.dumps({}))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
