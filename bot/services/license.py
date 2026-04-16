# -*- coding: utf-8 -*-
"""SMS Bot v6 — SMSBOT-Auth-Server 授权适配层。"""

from __future__ import annotations

import logging
import math
from typing import Optional

from bot.services.auth_client import AuthClient

log = logging.getLogger(__name__)


class LicenseError(Exception):
    """授权相关异常。"""


class LicenseManager:
    """兼容旧调用面的新授权管理器。"""

    def __init__(self, api_url: str):
        self._api_url = (api_url or "").strip().rstrip("/")
        self._auth: Optional[AuthClient] = AuthClient(self._api_url) if self._api_url else None
        self.last_verify_result: Optional[dict] = None

    @property
    def machine_id(self) -> str:
        return self._auth.device_id if self._auth else ""

    @property
    def is_valid(self) -> bool:
        return bool(self._auth and self._auth.is_authorized)

    @property
    def expires(self) -> str:
        if not self._auth:
            return ""
        return self._auth.expires_at or ""

    @property
    def admin_contact(self) -> str:
        if not self._auth:
            return ""
        return (self._auth.admin_telegram or self._auth.admin_contact or "").strip()

    @property
    def admin_link(self) -> str:
        name = self.admin_contact.lstrip("@")
        if name:
            return f"[@{name}](https://t.me/{name})"
        return "管理员"

    @property
    def admin_mention(self) -> str:
        name = self.admin_contact.lstrip("@")
        return f"@{name}" if name else "管理员"

    def _ensure_auth(self) -> AuthClient:
        if not self._auth:
            raise LicenseError("授权服务器地址未配置")
        return self._auth

    @staticmethod
    def _ceil_units(seconds: int, unit_seconds: int) -> int:
        if seconds <= 0:
            return 0
        return max(1, math.ceil(seconds / unit_seconds))

    def _snapshot(self) -> dict:
        if not self._auth:
            return {
                "valid": False,
                "status": "error",
                "message": "授权服务器地址未配置",
                "msg": "授权服务器地址未配置",
                "trial": False,
                "is_trial": False,
                "trial_hours_left": 0,
                "days_left": 0,
                "expires": "",
                "expires_at": "",
                "remaining_seconds": 0,
                "admin_contact": "",
                "admin_telegram": "",
                "announcement": "",
            }

        auth = self._auth
        response = dict(auth.last_response or {})
        message = (
            response.get("message")
            or auth.last_error
            or ("License valid" if auth.is_authorized else "Authorization failed")
        )
        response_remaining = response.get("remaining_seconds")
        if response_remaining is None:
            remaining_seconds = int(auth.remaining_seconds or 0) if auth.is_authorized else 0
        else:
            remaining_seconds = int(response_remaining or 0)
        is_trial = bool(response.get("is_trial", auth.is_trial))
        expires_at = response.get("expires_at") or auth.expires_at or ""
        status = response.get("status") or ("ok" if auth.is_authorized else "error")

        snapshot = {
            "valid": bool(auth.is_authorized),
            "status": status,
            "message": message,
            "msg": message,
            "trial": is_trial,
            "is_trial": is_trial,
            "trial_hours_left": self._ceil_units(remaining_seconds, 3600) if is_trial else 0,
            "days_left": self._ceil_units(remaining_seconds, 86400) if not is_trial else 0,
            "expires": expires_at,
            "expires_at": expires_at,
            "remaining_seconds": remaining_seconds,
            "admin_contact": auth.admin_contact,
            "admin_telegram": auth.admin_telegram,
            "announcement": auth.announcement,
        }
        return snapshot

    def _sync_state(self) -> dict:
        self.last_verify_result = self._snapshot()
        return self.last_verify_result

    def full_verify(self) -> tuple[bool, str]:
        """完整验证，成功后启动心跳。"""
        try:
            auth = self._ensure_auth()
        except LicenseError as exc:
            self.last_verify_result = self._snapshot()
            return False, str(exc)

        ok = auth.verify()
        offline_grace = bool(getattr(auth, "_within_offline_grace", lambda: False)())
        if ok or (auth.is_authorized and offline_grace):
            auth.start_heartbeat()
            snapshot = self._sync_state()
            return True, snapshot["message"]

        snapshot = self._sync_state()
        return False, snapshot["message"]

    def activate(self, license_key: str) -> tuple[bool, str]:
        """使用卡密激活。"""
        try:
            auth = self._ensure_auth()
        except LicenseError as exc:
            self.last_verify_result = self._snapshot()
            return False, str(exc)

        key = (license_key or "").strip()
        if not key:
            snapshot = self._sync_state()
            msg = "请在 /activate 后面输入卡密，例如 /activate ABCD-1234"
            snapshot["message"] = msg
            snapshot["msg"] = msg
            return False, msg

        ok = auth.activate(key)
        if ok:
            auth.start_heartbeat()
            snapshot = self._sync_state()
            return True, snapshot["message"]

        snapshot = self._sync_state()
        return False, snapshot["message"]

    def light_check(self) -> bool:
        """发送前轻量检查。"""
        return bool(self._auth and self._auth.is_authorized)

    def stop(self) -> None:
        if self._auth:
            self._auth.stop_heartbeat()
