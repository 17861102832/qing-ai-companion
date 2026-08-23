"""Slack 采集器。

通过 Slack Web API 采集频道消息。
需要 Slack Bot Token（xoxb-）或 User Token（xoxp-）。

依赖：pip3 install requests

认证方式：
  - 环境变量 SLACK_TOKEN
  - 配置 dict 中的 token 字段
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from .base import BaseCollector, Message, Channel

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

API_BASE = "https://slack.com/api"


class SlackCollector(BaseCollector):
    platform_name = "slack"
    platform_name_zh = "Slack"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._token = ""

    def _get_token(self) -> str:
        if self._token:
            return self._token
        self._token = (
            os.environ.get("SLACK_TOKEN", "")
            or (self.config or {}).get("token", "")
        )
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def authenticate(self) -> bool:
        if requests is None:
            return False
        token = self._get_token()
        if not token:
            return False
        resp = requests.get(f"{API_BASE}/auth.test", headers=self._headers(), timeout=10)
        ok = resp.json().get("ok", False)
        self._authenticated = ok
        return ok

    def scan(self, keyword: str = "") -> list[Channel]:
        if requests is None:
            return []
        channels: list[Channel] = []
        cursor = ""

        while True:
            params: dict = {"limit": 200, "types": "public_channel,private_channel,im,mpim"}
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(
                f"{API_BASE}/conversations.list",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if not data.get("ok"):
                break
            for ch in data.get("channels", []):
                name = ch.get("name") or ch.get("user") or ch.get("id", "")
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=ch["id"],
                    name=name,
                    platform="slack",
                    member_count=ch.get("num_members", 0),
                ))
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break

        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        if requests is None:
            return []
        messages: list[Message] = []
        cursor = ""

        while len(messages) < limit:
            params: dict = {"channel": channel_id, "limit": min(200, limit - len(messages))}
            if cursor:
                params["cursor"] = cursor
            if since:
                params["oldest"] = str(since.timestamp())
            if until:
                params["latest"] = str(until.timestamp())

            resp = requests.get(
                f"{API_BASE}/conversations.history",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if not data.get("ok"):
                break
            for msg in data.get("messages", []):
                text = msg.get("text", "")
                if not text or msg.get("subtype") in ("channel_join", "channel_leave"):
                    continue
                ts = self._parse_ts(msg.get("ts"))
                messages.append(Message(
                    sender=msg.get("user", ""),
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="slack",
                ))
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not data.get("has_more") or not cursor:
                break

        return messages

    @staticmethod
    def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        except (ValueError, OSError):
            return None
