import os
import sys
import json
import time
import signal
from typing import Dict, Any, Optional, List

# Safely handle pythonw where stdout/stderr are None
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from discord_ipc import DiscordIPC

SETTINGS_PATH = os.path.join(PLUGIN_DIR, "settings.json")
CONFIG_PATH = os.path.join(PLUGIN_DIR, "config.json")
USER_PROFILE = os.environ.get("USERPROFILE", "")
DEFAULT_STATE_PATH = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "state.json")
PID_FILE_PATH = os.path.join(USER_PROFILE, ".gemini", "antigravity-cli", "discord-rpc", "daemon.pid")

def load_settings() -> Dict[str, Any]:
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
            "timer_mode": "session",
            "details_template": "{model} ({effort} Effort)",
            "state_template": "{emoji} {action} {branch_info} {files_info}",
            "large_text_template": "Antigravity CLI • {workspace}",
            "small_text_template": "{effort} Effort • Step {step} • {tool_count} tools"
        },
        "emojis": {
            "thinking": "🧠",
            "editing": "📝",
            "command": "⚡",
            "reading": "📖",
            "searching": "🔍",
            "processing": "✨",
            "idle": "💤"
        },
        "assets": {
            "large_image": "antigravity",
            "thinking_image": "thinking",
            "editing_image": "edit",
            "command_image": "edit",
            "idle_image": "idle"
        },
        "buttons": [
            {"label": "Antigravity CLI", "url": "https://antigravity.google"}
        ],
        "logging": {
            "state_file_path": DEFAULT_STATE_PATH
        }
    }

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

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                defaults["general"]["client_id"] = cfg.get("client_id", defaults["general"]["client_id"])
        except Exception:
            pass

    return defaults

DAEMON_PORT = 49281
_lock_socket = None

def acquire_daemon_lock() -> bool:
    global _lock_socket
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", DAEMON_PORT))
        s.listen(1)
        _lock_socket = s
        os.makedirs(os.path.dirname(PID_FILE_PATH), exist_ok=True)
        with open(PID_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False

def release_daemon_lock():
    global _lock_socket
    if _lock_socket:
        try:
            _lock_socket.close()
        except Exception:
            pass
        _lock_socket = None
    try:
        if os.path.exists(PID_FILE_PATH):
            with open(PID_FILE_PATH, "r", encoding="utf-8") as f:
                pid = f.read().strip()
            if pid == str(os.getpid()):
                os.remove(PID_FILE_PATH)
    except Exception:
        pass

def render_template(template_str: str, variables: Dict[str, str]) -> str:
    """Safely replace {variable} placeholders with their string values and trim clean."""
    res = template_str
    for k, v in variables.items():
        res = res.replace(f"{{{k}}}", str(v))
    # Clean up double spaces or trailing whitespace from empty placeholders
    parts = [p.strip() for p in res.split(" ") if p.strip()]
    return " ".join(parts)

def build_presence_payload(state: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    disp = settings.get("display", {})
    emojis = settings.get("emojis", {})
    assets = settings.get("assets", {})

    status = state.get("status", "idle")
    action = state.get("action", "Ready")
    model_name = state.get("model_name", "Gemini")
    thinking_effort = state.get("thinking_effort", "High")
    workspace = state.get("workspace_name", "")
    branch = state.get("git_branch", "")
    files_count = state.get("files_modified_count", 0)
    step = state.get("step_index", 0)
    tool_count = state.get("tool_calls_count", 0)
    current_tool = state.get("current_tool", "")
    current_target = state.get("current_target", "")

    # Pick emoji
    emoji = emojis.get("idle", "💤")
    if status == "thinking":
        emoji = emojis.get("thinking", "🧠")
    elif status in ("tool_use", "tool_completed"):
        if current_tool in ("write_to_file", "replace_file_content"):
            emoji = emojis.get("editing", "📝")
        elif current_tool == "run_command":
            emoji = emojis.get("command", "⚡")
        elif current_tool == "view_file":
            emoji = emojis.get("reading", "📖")
        elif current_tool in ("grep_search", "find_by_name"):
            emoji = emojis.get("searching", "🔍")
        else:
            emoji = emojis.get("command", "⚡")
    elif status == "processing":
        emoji = emojis.get("processing", "✨")

    lines_added = state.get("lines_added", 0)
    lines_removed = state.get("lines_removed", 0)
    show_diff = disp.get("show_lines_diff", True)

    diff_parts = []
    if lines_added > 0:
        diff_parts.append(f"+{lines_added}")
    if lines_removed > 0:
        diff_parts.append(f"-{lines_removed}")
    diff_badge = " ".join(diff_parts)
    diff_info = f"({diff_badge} lines)" if (show_diff and diff_badge) else ""

    workspace_info = f"[{workspace}]" if (disp.get("show_workspace", True) and workspace) else ""
    branch_info = f"({branch})" if (disp.get("show_git_branch", True) and branch) else ""
    files_info = f"({files_count} files)" if (disp.get("show_files_changed", True) and files_count > 0) else ""

    variables = {
        "model": model_name,
        "effort": thinking_effort,
        "status": status.capitalize(),
        "emoji": emoji,
        "action": action,
        "tool": current_tool,
        "target": os.path.basename(current_target) if current_target else "",
        "workspace": workspace if disp.get("show_workspace", True) else "",
        "workspace_info": workspace_info,
        "branch": branch if disp.get("show_git_branch", True) else "",
        "branch_info": branch_info,
        "files_count": str(files_count),
        "files_info": files_info,
        "lines_added": str(lines_added),
        "lines_removed": str(lines_removed),
        "diff_badge": diff_badge,
        "diff_info": diff_info,
        "step": str(step),
        "tool_count": str(tool_count)
    }

    # Render details & state from templates
    details_tmpl = disp.get("details_template", "{model} ({effort} Effort)")
    state_tmpl = disp.get("state_template", "{emoji} {action} {diff_info} {branch_info} {files_info}")
    large_text_tmpl = disp.get("large_text_template", "Antigravity CLI • {workspace}")
    small_text_tmpl = disp.get("small_text_template", "{effort} Effort • Step {step} • {tool_count} tools")

    details = render_template(details_tmpl, variables)
    state_line = render_template(state_tmpl, variables)
    large_text = render_template(large_text_tmpl, variables)
    small_text = render_template(small_text_tmpl, variables)

    # Timer calculation
    timer_mode = disp.get("timer_mode", "session")
    if timer_mode == "turn":
        start_ts = state.get("prompt_start_time", int(time.time()))
    else:
        start_ts = state.get("session_start_time", int(time.time()))

    # Assets & Small image
    large_image = assets.get("large_image", "antigravity")
    small_image = assets.get("idle_image", "idle")
    if status == "thinking":
        small_image = assets.get("thinking_image", "thinking")
    elif status in ("tool_use", "tool_completed"):
        small_image = assets.get("editing_image", "edit")

    # Buttons
    buttons = settings.get("buttons", [])

    return {
        "details": details[:128] if details else "Antigravity CLI",
        "state": state_line[:128] if state_line else "Ready",
        "start_timestamp": start_ts,
        "large_image": large_image,
        "large_text": large_text[:128] if large_text else "Antigravity CLI",
        "small_image": small_image,
        "small_text": small_text[:128] if small_text else "",
        "buttons": buttons
    }

def run_daemon():
    if not acquire_daemon_lock():
        print("[*] Another daemon instance is running. Exiting.")
        sys.exit(0)

    settings = load_settings()
    client_id = settings.get("general", {}).get("client_id", "1545821431181344850")
    ipc = DiscordIPC(client_id)

    running = True

    def handle_exit(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("[*] Antigravity Discord RPC Daemon started. Listening for live updates...")

    last_state_hash = ""
    last_discord_send = 0.0
    last_mtime = 0.0
    cached_state: Dict[str, Any] = {}
    held_action = ""
    held_until = 0.0
    pending_update = False

    try:
        while running:
            settings = load_settings()
            gen_cfg = settings.get("general", {})
            log_cfg = settings.get("logging", {})
            idle_timeout = gen_cfg.get("idle_timeout_seconds", 300)
            state_path = os.path.expanduser(log_cfg.get("state_file_path", DEFAULT_STATE_PATH))

            now_float = time.time()
            now_int = int(now_float)

            # Check if state file was modified
            if os.path.exists(state_path):
                try:
                    cur_mtime = os.path.getmtime(state_path)
                    if cur_mtime != last_mtime:
                        last_mtime = cur_mtime
                        with open(state_path, "r", encoding="utf-8") as f:
                            cached_state = json.load(f)
                except Exception:
                    pass

            state = dict(cached_state)

            last_active = state.get("last_active", now_int)
            is_stale = (now_int - last_active) > idle_timeout

            if is_stale and state.get("status") != "idle":
                state["status"] = "idle"
                state["action"] = "Idle / Away"
                held_action = ""

            # Action Hold Smoother: keep active tool actions visible for at least 1.8s
            # so rapid 20ms file edits and commands are clearly visible on Discord
            cur_status = state.get("status", "idle")
            cur_action = state.get("action", "")

            if cur_status == "tool_use" and cur_action:
                held_action = cur_action
                held_until = now_float + 1.8

            if held_action and now_float < held_until and cur_status in ("tool_completed", "processing", "thinking"):
                state["status"] = "tool_use"
                state["action"] = held_action
            elif now_float >= held_until:
                held_action = ""

            # Connect / reconnect Discord IPC if needed
            if not ipc.connected:
                ipc.connect()

            if ipc.connected:
                act = build_presence_payload(state, settings)
                current_hash = f"{act['details']}|{act['state']}|{act['small_text']}|{act.get('buttons')}|{act['large_image']}|{act['small_image']}|{is_stale}"

                if current_hash != last_state_hash:
                    pending_update = True

                time_since_send = now_float - last_discord_send

                # Send if state changed and at least 1.0s passed (to respect Discord IPC rate limit),
                # or periodically every 15s to keep connection alive
                if (pending_update and time_since_send >= 1.0) or (time_since_send >= 15.0):
                    success = ipc.set_activity(
                        details=act["details"],
                        state=act["state"],
                        start_timestamp=act["start_timestamp"],
                        large_image=act["large_image"],
                        large_text=act["large_text"],
                        small_image=act["small_image"],
                        small_text=act["small_text"],
                        buttons=act["buttons"]
                    )
                    if success:
                        last_state_hash = current_hash
                        last_discord_send = now_float
                        pending_update = False

            time.sleep(0.25)

    except Exception as e:
        print(f"[!] Daemon loop error: {e}")
    finally:
        print("[*] Shutting down Discord RPC Daemon...")
        if ipc.connected:
            try:
                ipc.clear_activity()
                ipc.close()
            except Exception:
                pass
        release_daemon_lock()
        print("[*] Cleanup complete.")

if __name__ == "__main__":
    run_daemon()
