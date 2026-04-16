"""
Auth Client SDK - Integrate into your SMSBOT Python script.
Usage:
    from auth_client import AuthClient
    auth = AuthClient("https://your-server.com")
    if auth.verify():
        # Start your RDP logic
        auth.start_heartbeat()
    else:
        print("Authorization failed:", auth.last_error)

Requirements: pip install requests
"""
import hashlib
import platform
import uuid
import threading
import time
import sys
import os
import json

try:
    import requests
except ImportError:
    print("[AuthClient] Missing dependency: pip install requests")
    raise


class AuthClient:
    """Authorization client for SMSBOT scripts."""

    def __init__(self, server_url: str, config_path: str = None):
        self.server_url = server_url.rstrip("/")
        if config_path:
            self.config_path = config_path
        elif sys.platform == "win32":
            self.config_path = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                ".smsbot_auth", "config.json"
            )
        else:
            self.config_path = os.path.join(
                os.path.expanduser("~"), ".smsbot_auth", "config.json"
            )
        self.device_id = self._get_device_id()
        self.device_info = self._get_device_info()
        self.client_version = "1.0.0"
        self.heartbeat_interval = 300
        self.heartbeat_timeout = 600
        self.max_offline_seconds = 3600
        self.is_authorized = False
        self.expires_at = None
        self.remaining_seconds = 0
        self.is_trial = False
        self.last_error = None
        self.last_response = None
        self.last_server_contact_at = 0.0
        self.admin_contact = ""
        self.admin_telegram = ""
        self.announcement = ""
        self._lock = threading.Lock()
        self._heartbeat_thread = None
        self._stop_heartbeat = threading.Event()
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _get_device_id(self) -> str:
        """Generate unique device ID based on hardware."""
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    did = config.get("device_id", "")
                    if len(did) == 64:
                        return did
            except (IOError, json.JSONDecodeError, ValueError):
                pass

        # Generate new device_id from hardware info
        info_parts = []
        try:
            info_parts.append(platform.node())
            info_parts.append(platform.machine())
            info_parts.append(platform.processor())
            if sys.platform == "win32":
                try:
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Cryptography"
                    )
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                    info_parts.append(machine_guid)
                    winreg.CloseKey(key)
                except Exception:
                    info_parts.append(str(uuid.getnode()))
            else:
                found = False
                for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                    if os.path.exists(path):
                        with open(path) as f:
                            info_parts.append(f.read().strip())
                        found = True
                        break
                if not found:
                    info_parts.append(str(uuid.getnode()))
        except Exception:
            info_parts.append(str(uuid.getnode()))

        raw = "|".join(info_parts)
        device_id = hashlib.sha256(raw.encode()).hexdigest()

        # Save device_id with restrictive permissions
        try:
            tmp_path = self.config_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump({"device_id": device_id}, f)
            os.replace(tmp_path, self.config_path)
            if sys.platform != "win32":
                os.chmod(self.config_path, 0o600)
        except (IOError, OSError):
            pass

        return device_id

    def _get_device_info(self) -> str:
        """Get human-readable device info."""
        return f"{platform.node()} | {platform.system()} {platform.release()} | {platform.machine()}"

    def _update_extra(self, data: dict):
        """Update contact/announcement fields from server response."""
        self.admin_contact = data.get("admin_contact", self.admin_contact)
        self.admin_telegram = data.get("admin_telegram", self.admin_telegram)
        self.announcement = data.get("announcement", self.announcement)
        self.heartbeat_interval = self._coerce_positive_int(data.get("heartbeat_interval"), self.heartbeat_interval)
        self.heartbeat_timeout = self._coerce_positive_int(data.get("heartbeat_timeout"), self.heartbeat_timeout)
        self.max_offline_seconds = self._coerce_positive_int(data.get("max_offline_seconds"), self.max_offline_seconds)

    @staticmethod
    def _coerce_positive_int(value, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def _mark_server_contact(self):
        with self._lock:
            self.last_server_contact_at = time.time()

    def _within_offline_grace(self) -> bool:
        with self._lock:
            if not self.is_authorized or self.last_server_contact_at <= 0:
                return False
            return (time.time() - self.last_server_contact_at) <= self.max_offline_seconds

    def verify(self) -> bool:
        """Verify device authorization. Call on startup."""
        try:
            resp = self._session.post(
                f"{self.server_url}/api/client/verify",
                json={
                    "device_id": self.device_id,
                    "device_info": self.device_info,
                    "client_version": self.client_version
                },
                timeout=10
            )
            if resp.status_code != 200:
                message = f"Server error: HTTP {resp.status_code}"
                if self._within_offline_grace():
                    self.last_error = message + "; using offline grace period"
                    self.last_response = {
                        "status": "ok",
                        "is_trial": self.is_trial,
                        "expires_at": self.expires_at,
                        "remaining_seconds": self.remaining_seconds,
                        "message": self.last_error,
                        "admin_contact": self.admin_contact,
                        "admin_telegram": self.admin_telegram,
                        "announcement": self.announcement,
                    }
                    return True
                with self._lock:
                    self.is_authorized = False
                self.last_error = message
                self.last_response = {"status": "error", "message": message}
                return False

            data = resp.json()
            self.last_response = data
            self._update_extra(data)

            if data.get("status") == "ok":
                with self._lock:
                    self.is_authorized = True
                    self.expires_at = data.get("expires_at")
                    self.remaining_seconds = data.get("remaining_seconds", 0)
                    self.is_trial = data.get("is_trial", False)
                self._mark_server_contact()
                self.last_error = None
                return True
            else:
                with self._lock:
                    self.is_authorized = False
                self.last_error = data.get("message", "Verification failed")
                return False

        except (requests.RequestException, ValueError) as e:
            message = f"Network error: {type(e).__name__}"
            if self._within_offline_grace():
                self.last_error = message + "; using offline grace period"
                self.last_response = {
                    "status": "ok",
                    "is_trial": self.is_trial,
                    "expires_at": self.expires_at,
                    "remaining_seconds": self.remaining_seconds,
                    "message": self.last_error,
                    "admin_contact": self.admin_contact,
                    "admin_telegram": self.admin_telegram,
                    "announcement": self.announcement,
                }
                return True
            with self._lock:
                self.is_authorized = False
            self.last_error = message
            self.last_response = {"status": "error", "message": message}
            return False

    def activate(self, license_key: str) -> bool:
        """Activate a license key."""
        try:
            resp = self._session.post(
                f"{self.server_url}/api/client/activate",
                json={
                    "device_id": self.device_id,
                    "license_key": license_key
                },
                timeout=10
            )
            if resp.status_code != 200:
                message = f"Server error: HTTP {resp.status_code}"
                self.last_error = message
                self.last_response = {"status": "error", "message": message}
                return False

            data = resp.json()
            self.last_response = data
            self._update_extra(data)

            if data.get("status") == "ok":
                with self._lock:
                    self.is_authorized = True
                    self.expires_at = data.get("expires_at")
                    self.remaining_seconds = data.get("remaining_seconds", 0)
                    self.is_trial = False
                self._mark_server_contact()
                self.last_error = None
                return True
            else:
                self.last_error = data.get("message", "Activation failed")
                self.last_response = data
                return False

        except (requests.RequestException, ValueError) as e:
            message = f"Network error: {type(e).__name__}"
            self.last_error = message
            self.last_response = {"status": "error", "message": message}
            return False

    def heartbeat(self) -> bool:
        """Send single heartbeat."""
        try:
            resp = self._session.post(
                f"{self.server_url}/api/client/heartbeat",
                json={
                    "device_id": self.device_id,
                    "client_version": self.client_version
                },
                timeout=10
            )
            if resp.status_code != 200:
                if self._within_offline_grace():
                    self.last_error = "Heartbeat temporarily unavailable, using offline grace period"
                    return True
                with self._lock:
                    self.is_authorized = False
                self.last_error = f"Server error: HTTP {resp.status_code}"
                return False

            data = resp.json()
            self.last_response = data
            self._update_extra(data)

            if data.get("status") == "ok":
                with self._lock:
                    self.remaining_seconds = data.get("remaining_seconds", 0)
                self._mark_server_contact()
                self.last_error = None
                return True
            elif data.get("status") in ("expired", "banned", "disabled"):
                with self._lock:
                    self.is_authorized = False
                self.last_error = data.get("message")
                return False
            if self._within_offline_grace():
                self.last_error = data.get("message", "Heartbeat temporarily unavailable, using offline grace period")
                return True
            with self._lock:
                self.is_authorized = False
            self.last_error = data.get("message", "Heartbeat failed")
            return False

        except (requests.RequestException, ValueError) as e:
            if self._within_offline_grace():
                self.last_error = f"Network error: {type(e).__name__}; using offline grace period"
                return True
            with self._lock:
                self.is_authorized = False
            self.last_error = f"Network error: {type(e).__name__}"
            return False

    def start_heartbeat(self):
        """Start background heartbeat thread."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._stop_heartbeat.clear()

        def _loop():
            while not self._stop_heartbeat.is_set():
                self._stop_heartbeat.wait(self.heartbeat_interval)
                if self._stop_heartbeat.is_set():
                    break
                if not self.heartbeat():
                    with self._lock:
                        if not self.is_authorized:
                            break

        self._heartbeat_thread = threading.Thread(target=_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        """Stop heartbeat thread."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)


# === Quick integration example ===
if __name__ == "__main__":
    SERVER = os.environ.get("AUTH_SERVER", "http://localhost:8000")
    auth = AuthClient(SERVER)

    print(f"Device ID: {auth.device_id}")
    print(f"Device Info: {auth.device_info}")
    print(f"Verifying with {SERVER}...")

    if auth.verify():
        print(f"Authorized! Trial: {auth.is_trial}")
        print(f"Expires: {auth.expires_at}")
        print(f"Remaining: {auth.remaining_seconds}s")
        if auth.announcement:
            print(f"Announcement: {auth.announcement}")
        if auth.admin_telegram:
            print(f"Contact: {auth.admin_telegram}")

        if len(sys.argv) > 1:
            key = sys.argv[1]
            print(f"\nActivating key: {key}")
            if auth.activate(key):
                print(f"Activated! Expires: {auth.expires_at}")
            else:
                print(f"Failed: {auth.last_error}")

        auth.start_heartbeat()
        print("\nHeartbeat running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            auth.stop_heartbeat()
    else:
        print(f"FAILED: {auth.last_error}")
