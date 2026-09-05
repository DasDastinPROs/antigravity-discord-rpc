import os
import sys
import json
import time
import threading
import signal
from typing import Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from discord_ipc import DiscordIPC
from discord_daemon import (
    load_settings,
    build_presence_payload,
    acquire_daemon_lock,
    release_daemon_lock,
    DEFAULT_STATE_PATH
)

# Global stop event
_stop_event = threading.Event()
_ipc: Optional[DiscordIPC] = None

def discord_worker():
    """Background worker that manages Discord Rich Presence while the MCP server is alive."""
    global _ipc
    settings = load_settings()
    client_id = settings.get("general", {}).get("client_id", "1545821431181344850")
    _ipc = DiscordIPC(client_id)

    last_state_hash = ""

    # Ensure initial startup state exists
    state_path = settings.get("logging", {}).get("state_file_path", DEFAULT_STATE_PATH)
    if not os.path.exists(state_path):
        initial_state = {
            "conversation_id": "",
            "session_start_time": int(time.time()),
            "prompt_start_time": int(time.time()),
            "model_name": "Gemini 3.8 Flash (High)",
            "thinking_effort": "High",
            "status": "idle",
            "action": "Antigravity CLI Started",
            "current_tool": "",
            "current_target": "",
            "files_modified": [],
            "files_modified_count": 0,
            "step_index": 0,
            "tool_calls_count": 0,
            "workspace_name": "",
            "updated_at": int(time.time()),
            "last_active": int(time.time())
        }
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(initial_state, f, indent=2)
        except Exception:
            pass

    last_state_hash = ""
    last_discord_send = 0.0
    last_mtime = 0.0
    cached_state: Dict[str, Any] = {}
    held_action = ""
    held_until = 0.0
    pending_update = False

    while not _stop_event.is_set():
        try:
            settings = load_settings()
            gen_cfg = settings.get("general", {})
            log_cfg = settings.get("logging", {})
            idle_timeout = gen_cfg.get("idle_timeout_seconds", 300)
            s_path = os.path.expanduser(log_cfg.get("state_file_path", DEFAULT_STATE_PATH))

            now_float = time.time()
            now_int = int(now_float)

            if os.path.exists(s_path):
                try:
                    cur_mtime = os.path.getmtime(s_path)
                    if cur_mtime != last_mtime:
                        last_mtime = cur_mtime
                        with open(s_path, "r", encoding="utf-8") as f:
                            cached_state = json.load(f)
                except Exception:
                    pass

            state = dict(cached_state)

            last_active = state.get("last_active", now_int)
            is_stale = (now_int - last_active) > idle_timeout

            if is_stale and state.get("status") != "idle":
                state["status"] = "idle"
                state["action"] = "Idle / Awaiting prompt"
                held_action = ""

            # Action Hold Smoother
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

            if not _ipc.connected:
                _ipc.connect()

            if _ipc.connected:
                act = build_presence_payload(state, settings)
                current_hash = f"{act['details']}|{act['state']}|{act['small_text']}|{is_stale}"

                if current_hash != last_state_hash:
                    pending_update = True

                time_since_send = now_float - last_discord_send

                if (pending_update and time_since_send >= 1.0) or (time_since_send >= 15.0):
                    success = _ipc.set_activity(
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

        except Exception:
            pass

        _stop_event.wait(timeout=0.25)

    # Cleanup Discord on exit
    if _ipc and _ipc.connected:
        try:
            _ipc.clear_activity()
            _ipc.close()
        except Exception:
            pass

def send_mcp_response(resp: dict):
    line = json.dumps(resp, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

def handle_mcp_request(req: dict) -> Optional[dict]:
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "discord-rpc",
                    "version": "1.0.0"
                }
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "discord_update_status",
                        "description": "Update Discord Rich Presence state with custom text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "description": "Custom action or status to display"}
                            },
                            "required": ["status"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})
        if tool_name == "discord_update_status":
            custom_status = args.get("status", "Active")
            # Update state
            settings = load_settings()
            state_path = settings.get("logging", {}).get("state_file_path", DEFAULT_STATE_PATH)
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        st = json.load(f)
                    st["action"] = custom_status
                    st["updated_at"] = int(time.time())
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump(st, f, indent=2)
                except Exception:
                    pass
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Discord status updated to: {custom_status}"}]
                }
            }
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return None

def main():
    # Try to acquire lock socket to ensure single active Discord worker
    has_lock = acquire_daemon_lock()

    # Start background Discord worker
    worker_thread = None
    if has_lock:
        worker_thread = threading.Thread(target=discord_worker, daemon=True, name="DiscordWorker")
        worker_thread.start()

    # Listen on stdin for MCP messages
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                resp = handle_mcp_request(msg)
                if resp is not None:
                    send_mcp_response(resp)
            except Exception:
                pass
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        _stop_event.set()
        if worker_thread and worker_thread.is_alive():
            worker_thread.join(timeout=1.5)
        if has_lock:
            release_daemon_lock()

if __name__ == "__main__":
    main()
