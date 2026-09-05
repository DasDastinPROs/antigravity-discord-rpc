import os
import sys
import json
import socket
import subprocess

def main():
    user_home = os.path.expanduser("~")
    plugin_dir = os.path.join(user_home, ".gemini", "config", "plugins", "discord-rpc")
    scripts_dir = os.path.join(plugin_dir, "scripts")
    mcp_script = os.path.join(scripts_dir, "mcp_discord_server.py")
    daemon_script = os.path.join(scripts_dir, "discord_daemon.py")
    gemini_settings = os.path.join(user_home, ".gemini", "settings.json")

    print("[*] Registering MCP Auto-Start with Antigravity CLI...")
    try:
        data = {}
        if os.path.exists(gemini_settings):
            with open(gemini_settings, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
        
        servers = data.setdefault("mcpServers", {})
        servers["discord-rpc"] = {
            "command": "python",
            "args": [mcp_script]
        }

        os.makedirs(os.path.dirname(gemini_settings), exist_ok=True)
        with open(gemini_settings, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("    [+] Successfully registered discord-rpc in ~/.gemini/settings.json")
    except Exception as e:
        print(f"    [!] Could not update ~/.gemini/settings.json: {e}")

    print("[*] Checking Discord RPC background daemon...")
    port_busy = False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 49281))
        s.close()
    except OSError:
        port_busy = True

    if not port_busy:
        print("    [*] Starting daemon in background...")
        python_exe = sys.executable
        pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        launcher = pythonw_exe if os.path.exists(pythonw_exe) else python_exe
        try:
            creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
            subprocess.Popen(
                [launcher, daemon_script],
                cwd=plugin_dir,
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
            print("    [+] Background daemon started.")
        except Exception as e:
            print(f"    [!] Failed to start daemon: {e}")
    else:
        print("    [+] Daemon is already running.")

if __name__ == "__main__":
    main()
