import os
import sys
import json
import time
import struct
import uuid
import socket
from typing import Optional, Dict, Any, List

class DiscordIPC:
    """
    Zero-dependency pure Python Discord IPC client.
    Cross-platform:
      - Windows: Named Pipes (\\\\.\\pipe\\discord-ipc-0..9)
      - Linux / macOS: Unix Domain Sockets ($XDG_RUNTIME_DIR/discord-ipc-0..9, /tmp/...)
    """
    OP_HANDSHAKE = 0
    OP_FRAME = 1
    OP_CLOSE = 2
    OP_PING = 3
    OP_PONG = 4

    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self.pipe = None
        self.sock: Optional[socket.socket] = None
        self.is_windows = sys.platform.startswith("win")
        self.connected = False
        self.user_data = None

    def find_pipe(self) -> Optional[Any]:
        """Search for active Discord IPC named pipe or socket (0 to 9)."""
        if self.is_windows:
            for i in range(10):
                pipe_path = f"\\\\.\\pipe\\discord-ipc-{i}"
                try:
                    test_pipe = open(pipe_path, "r+b", buffering=0)
                    test_pipe.close()
                    return pipe_path
                except (OSError, PermissionError, FileNotFoundError):
                    continue
        else:
            # Unix / macOS domain sockets
            candidates = []
            xdg = os.environ.get("XDG_RUNTIME_DIR")
            if xdg:
                candidates.append(xdg)
            tmpdir = os.environ.get("TMPDIR") or os.environ.get("TMP") or "/tmp"
            candidates.append(tmpdir)
            uid = getattr(os, "getuid", lambda: None)()
            if uid is not None:
                candidates.append(f"/run/user/{uid}")

            for base in candidates:
                for i in range(10):
                    sock_path = os.path.join(base, f"discord-ipc-{i}")
                    if os.path.exists(sock_path):
                        return sock_path
        return None

    def connect(self) -> bool:
        """Establish connection and perform initial handshake."""
        self.close()
        endpoint = self.find_pipe()
        if not endpoint:
            return False

        try:
            if self.is_windows:
                self.pipe = open(endpoint, "r+b", buffering=0)
            else:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(endpoint)

            # Send Handshake (Opcode 0)
            handshake_data = json.dumps({"v": 1, "client_id": self.client_id}).encode("utf-8")
            self._send(self.OP_HANDSHAKE, handshake_data)

            # Read Handshake Response
            opcode, data = self._recv()
            if opcode == self.OP_FRAME and data.get("cmd") == "DISPATCH" and data.get("evt") == "READY":
                self.user_data = data.get("data", {}).get("user", {})
                self.connected = True
                return True
            elif opcode == self.OP_CLOSE:
                self.close()
                return False
            else:
                self.connected = True
                return True
        except Exception:
            self.close()
            return False

    def _send(self, opcode: int, data: bytes):
        """Send a packet with 8-byte little-endian header (opcode, length) and JSON payload."""
        header = struct.pack("<II", opcode, len(data))
        packet = header + data
        if self.is_windows:
            if not self.pipe:
                raise BrokenPipeError("Pipe is not open")
            self.pipe.write(packet)
        else:
            if not self.sock:
                raise BrokenPipeError("Socket is not open")
            self.sock.sendall(packet)

    def _recv(self) -> tuple[int, Dict[str, Any]]:
        """Receive an 8-byte header and read the payload."""
        if self.is_windows:
            if not self.pipe:
                raise BrokenPipeError("Pipe is not open")
            header = self.pipe.read(8)
            if len(header) < 8:
                raise ConnectionResetError("Connection closed by peer")
            opcode, length = struct.unpack("<II", header)
            raw_data = self.pipe.read(length)
        else:
            if not self.sock:
                raise BrokenPipeError("Socket is not open")
            header = b""
            while len(header) < 8:
                chunk = self.sock.recv(8 - len(header))
                if not chunk:
                    raise ConnectionResetError("Connection closed by peer")
                header += chunk
            opcode, length = struct.unpack("<II", header)
            raw_data = b""
            while len(raw_data) < length:
                chunk = self.sock.recv(length - len(raw_data))
                if not chunk:
                    raise ConnectionResetError("Incomplete payload received")
                raw_data += chunk

        try:
            payload = json.loads(raw_data.decode("utf-8"))
        except Exception:
            payload = {}
        return opcode, payload

    def set_activity(
        self,
        details: Optional[str] = None,
        state: Optional[str] = None,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
        large_image: Optional[str] = None,
        large_text: Optional[str] = None,
        small_image: Optional[str] = None,
        small_text: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """Update Discord Rich Presence activity."""
        if not self.connected or (not self.pipe and not self.sock):
            if not self.connect():
                return False

        activity: Dict[str, Any] = {}

        if details:
            activity["details"] = str(details)[:128]
        if state:
            activity["state"] = str(state)[:128]

        timestamps: Dict[str, Any] = {}
        if start_timestamp:
            timestamps["start"] = int(start_timestamp)
        if end_timestamp:
            timestamps["end"] = int(end_timestamp)
        if timestamps:
            activity["timestamps"] = timestamps

        assets: Dict[str, Any] = {}
        if large_image:
            assets["large_image"] = str(large_image)[:128]
        if large_text:
            assets["large_text"] = str(large_text)[:128]
        if small_image:
            assets["small_image"] = str(small_image)[:128]
        if small_text:
            assets["small_text"] = str(small_text)[:128]
        if assets:
            activity["assets"] = assets

        if buttons:
            valid_buttons = []
            for b in buttons[:2]:
                if "label" in b and "url" in b:
                    valid_buttons.append({
                        "label": str(b["label"])[:32],
                        "url": str(b["url"])[:512]
                    })
            if valid_buttons:
                activity["buttons"] = valid_buttons

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity
            },
            "nonce": str(uuid.uuid4())
        }

        try:
            raw_payload = json.dumps(payload).encode("utf-8")
            self._send(self.OP_FRAME, raw_payload)
            opcode, resp = self._recv()
            return opcode == self.OP_FRAME and resp.get("cmd") == "SET_ACTIVITY"
        except Exception:
            self.close()
            return False

    def clear_activity(self) -> bool:
        """Clear active Rich Presence from Discord."""
        if not self.connected or (not self.pipe and not self.sock):
            return True

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": None
            },
            "nonce": str(uuid.uuid4())
        }

        try:
            raw_payload = json.dumps(payload).encode("utf-8")
            self._send(self.OP_FRAME, raw_payload)
            self._recv()
            return True
        except Exception:
            self.close()
            return False

    def close(self):
        """Close connection cleanly."""
        self.connected = False
        if self.pipe:
            try:
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
