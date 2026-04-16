import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyAuthClient:
    def __init__(self, server_url: str, config_path: str = None):
        self.server_url = server_url
        self.config_path = config_path
        self.device_id = "DEVICE-123"
        self.device_info = "Windows 11"
        self.client_version = "1.0.0"
        self.is_authorized = False
        self.expires_at = None
        self.remaining_seconds = 0
        self.is_trial = False
        self.last_error = None
        self.admin_contact = "客服"
        self.admin_telegram = "@shopadmin"
        self.announcement = ""
        self.heartbeat_started = False
        self.last_response = None

    def verify(self) -> bool:
        self.is_authorized = True
        self.is_trial = True
        self.expires_at = "2026-04-17 12:00:00"
        self.remaining_seconds = 2 * 3600
        self.last_response = {
            "status": "ok",
            "is_trial": True,
            "expires_at": self.expires_at,
            "remaining_seconds": self.remaining_seconds,
            "message": "Trial activated: 24 hours",
            "admin_contact": self.admin_contact,
            "admin_telegram": self.admin_telegram,
            "announcement": self.announcement,
        }
        return True

    def activate(self, license_key: str) -> bool:
        assert license_key == "CARD-001"
        self.is_authorized = True
        self.is_trial = False
        self.expires_at = "2026-04-20 12:00:00"
        self.remaining_seconds = 3 * 24 * 3600
        self.last_response = {
            "status": "ok",
            "is_trial": False,
            "expires_at": self.expires_at,
            "remaining_seconds": self.remaining_seconds,
            "duration_hours": 72,
            "message": "License activated: 72 hours",
            "admin_contact": self.admin_contact,
            "admin_telegram": self.admin_telegram,
            "announcement": self.announcement,
        }
        return True

    def start_heartbeat(self):
        self.heartbeat_started = True

    def stop_heartbeat(self):
        self.heartbeat_started = False


def _load_module(monkeypatch):
    mod = importlib.import_module("bot.services.license")
    monkeypatch.setattr(mod, "AuthClient", DummyAuthClient, raising=False)

    def _legacy_verify(*args, **kwargs):
        raise AssertionError("legacy verify_online should not be called after auth-server alignment")

    monkeypatch.setattr(mod, "verify_online", _legacy_verify, raising=False)
    return mod


def test_full_verify_uses_auth_server_client_and_maps_trial_state(monkeypatch):
    mod = _load_module(monkeypatch)
    mgr = mod.LicenseManager("https://license.example.com")

    ok, msg = mgr.full_verify()

    assert ok is True
    assert "Trial activated" in msg
    assert mgr.machine_id == "DEVICE-123"
    assert mgr.admin_mention == "@shopadmin"
    assert mgr.last_verify_result["trial"] is True
    assert mgr.last_verify_result["trial_hours_left"] == 2
    assert mgr.last_verify_result["message"] == "Trial activated: 24 hours"
    assert mgr._auth.heartbeat_started is True


def test_activate_uses_auth_server_client_and_maps_license_state(monkeypatch):
    mod = _load_module(monkeypatch)
    mgr = mod.LicenseManager("https://license.example.com")

    ok, msg = mgr.activate("CARD-001")

    assert ok is True
    assert "License activated" in msg
    assert mgr.expires == "2026-04-20 12:00:00"
    assert mgr.last_verify_result["trial"] is False
    assert mgr.last_verify_result["days_left"] == 3
    assert mgr.light_check() is True
