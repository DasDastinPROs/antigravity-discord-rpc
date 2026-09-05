import os
import sys
import json
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS_PATH = os.path.join(PLUGIN_DIR, "settings.json")
STOP_BAT = os.path.join(PLUGIN_DIR, "stop_daemon.bat")
START_BAT = os.path.join(PLUGIN_DIR, "start_daemon.bat")

def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return {}

def save_settings(data: dict):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("[+] Settings saved successfully! Daemon will apply changes in real time.")
    except Exception as e:
        print(f"[!] Error saving settings: {e}")

def restart_daemon():
    print("[*] Restarting daemon...")
    try:
        subprocess.run(["cmd", "/c", STOP_BAT], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["cmd", "/c", START_BAT], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[+] Daemon restarted successfully!")
    except Exception as e:
        print(f"[!] Could not restart daemon: {e}")

def print_menu(st: dict):
    disp = st.get("display", {})
    gen = st.get("general", {})
    buttons = st.get("buttons", [])

    print("\n" + "=" * 65)
    print("      ANTIGRAVITY CLI DISCORD RPC - CUSTOMIZER & SETTINGS")
    print("=" * 65)

    ws_status = "ON" if disp.get("show_workspace", True) else "OFF"
    alias = disp.get("workspace_alias", "")
    ws_display = f"{ws_status} (Alias: '{alias}')" if alias else ws_status

    gb_status = "ON" if disp.get("show_git_branch", True) else "OFF"
    te_status = "ON" if disp.get("show_thinking_effort", True) else "OFF"
    fc_status = "ON" if disp.get("show_files_changed", True) else "OFF"
    fn_status = "ON" if disp.get("show_file_names", True) else "OFF (Masked)"
    st_status = "ON" if disp.get("show_step_counter", True) else "OFF"
    ld_status = "ON" if disp.get("show_lines_diff", True) else "OFF"
    auto_status = "ON" if gen.get("auto_spawn_daemon", True) else "OFF"

    print(f" [1] Show Workspace Name:             [{ws_display}]")
    print(f" [2] Show Git Branch (🌿 main):        [{gb_status}]")
    print(f" [3] Show Thinking / Reasoning Effort: [{te_status}]")
    print(f" [4] Show Files Changed Counter:       [{fc_status}]")
    print(f" [5] Show Detailed File Names:         [{fn_status}]")
    print(f" [6] Show Steps & Tool Counters:       [{st_status}]")
    print(f" [D] Show Code Lines Diff (+/- lines): [{ld_status}]")
    print(f" [7] Auto-Spawn Background Daemon:     [{auto_status}]")
    print("-" * 65)
    print(f" [8] Details Template (Line 1):       [{disp.get('details_template', '')}]")
    print(f" [9] State Template (Line 2):         [{disp.get('state_template', '')}]")
    print(f" [A] Set Workspace Alias (custom name):[{alias or 'None'}]")
    print(f" [B] Configure Buttons ({len(buttons)} configured)")
    print(f" [C] Change Discord Client ID          [{gen.get('client_id', '')}]")
    print("-" * 65)
    print(" [O] Open settings.json in Notepad")
    print(" [R] Restart Discord RPC Daemon")
    print(" [Q] Quit & Save")
    print("=" * 65)

def main():
    while True:
        st = load_settings()
        disp = st.setdefault("display", {})
        gen = st.setdefault("general", {})

        print_menu(st)
        choice = input("\nSelect an option [1-9, A, B, C, D, O, R, Q]: ").strip().upper()

        if choice == "1":
            disp["show_workspace"] = not disp.get("show_workspace", True)
            save_settings(st)
        elif choice == "2":
            disp["show_git_branch"] = not disp.get("show_git_branch", True)
            save_settings(st)
        elif choice == "3":
            disp["show_thinking_effort"] = not disp.get("show_thinking_effort", True)
            save_settings(st)
        elif choice == "4":
            disp["show_files_changed"] = not disp.get("show_files_changed", True)
            save_settings(st)
        elif choice == "5":
            disp["show_file_names"] = not disp.get("show_file_names", True)
            save_settings(st)
        elif choice == "6":
            disp["show_step_counter"] = not disp.get("show_step_counter", True)
            disp["show_tool_counter"] = disp["show_step_counter"]
            save_settings(st)
        elif choice == "D":
            disp["show_lines_diff"] = not disp.get("show_lines_diff", True)
            save_settings(st)
        elif choice == "7":
            gen["auto_spawn_daemon"] = not gen.get("auto_spawn_daemon", True)
            save_settings(st)
        elif choice == "8":
            print("\nAvailable variables: {model}, {effort}, {status}, {workspace}, {step}")
            print(f"Current template: {disp.get('details_template', '')}")
            new_tmpl = input("Enter new template (or press Enter to keep): ").strip()
            if new_tmpl:
                disp["details_template"] = new_tmpl
                save_settings(st)
        elif choice == "9":
            print("\nAvailable variables: {emoji}, {action}, {diff_info}, {diff_badge}, {lines_added}, {lines_removed}, {branch}, {branch_info}, {files_count}, {files_info}, {workspace_info}")
            print(f"Current template: {disp.get('state_template', '')}")
            new_tmpl = input("Enter new template (or press Enter to keep): ").strip()
            if new_tmpl:
                disp["state_template"] = new_tmpl
                save_settings(st)
        elif choice == "A":
            cur_alias = disp.get("workspace_alias", "")
            print(f"\nCurrent alias: '{cur_alias}'")
            new_alias = input("Enter custom workspace name (or leave empty to use real folder name): ").strip()
            disp["workspace_alias"] = new_alias
            save_settings(st)
        elif choice == "B":
            buttons = st.setdefault("buttons", [])
            print(f"\nCurrent buttons ({len(buttons)}/2):")
            for idx, b in enumerate(buttons):
                print(f"  [{idx+1}] {b.get('label')} -> {b.get('url')}")
            print("\n[1] Edit Button 1 | [2] Edit Button 2 | [3] Remove all | [Enter] Back")
            b_choice = input("Choice: ").strip()
            if b_choice in ("1", "2"):
                idx = int(b_choice) - 1
                label = input(f"Button {b_choice} Label: ").strip()
                url = input(f"Button {b_choice} URL: ").strip()
                if label and url:
                    if idx < len(buttons):
                        buttons[idx] = {"label": label, "url": url}
                    else:
                        buttons.append({"label": label, "url": url})
                    save_settings(st)
            elif b_choice == "3":
                st["buttons"] = []
                save_settings(st)
        elif choice == "C":
            cur_id = gen.get("client_id", "")
            print(f"\nCurrent Client ID: {cur_id}")
            new_id = input("Enter new Discord Client ID: ").strip()
            if new_id:
                gen["client_id"] = new_id
                save_settings(st)
        elif choice == "O":
            subprocess.Popen(["notepad.exe", SETTINGS_PATH])
        elif choice == "R":
            restart_daemon()
        elif choice == "Q":
            print("[+] Exiting customizer.")
            break
        else:
            print("[!] Invalid option. Please select from the menu.")

if __name__ == "__main__":
    main()
