"""Discord 采集器。

通过 Discord Bot API 采集频道消息。
需要 Discord Bot Token。

依赖：pip3 install requests

认证方式：
  - 环境变量 DISCORD_TOKEN
  - 配置 dict 中的 token 字段

注意：Discord ToS 禁止用户 token 自动化，推荐使用 Bot token。
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

API_BASE = "https://discord.com/api/v10"


class DiscordCollector(BaseCollector):
    platform_name = "discord"
    platform_name_zh = "Discord"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._token = ""

    def _get_token(self) -> str:
        if self._token:
            return self._token
        self._token = (
            os.environ.get("DISCORD_TOKEN", "")
            or (self.config or {}).get("token", "")
        )
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bot {self._get_token()}"}

    def authenticate(self) -> bool:
        if requests is None:
            return False
        token = self._get_token()
        if not token:
            return False
        resp = requests.get(f"{API_BASE}/users/@me", headers=self._headers(), timeout=10)
        ok = resp.status_code == 200
        self._authenticated = ok
        return ok

    def scan(self, keyword: str = "") -> list[Channel]:
        if requests is None:
            return []
        channels: list[Channel] = []
        guilds_resp = requests.get(
            f"{API_BASE}/users/@me/guilds", headers=self._headers(), timeout=10,
        )
        if guilds_resp.status_code != 200:
            return channels

        for guild in guilds_resp.json():
            guild_id = guild["id"]
            ch_resp = requests.get(
                f"{API_BASE}/guilds/{guild_id}/channels",
                headers=self._headers(), timeout=10,
            )
            if ch_resp.status_code != 200:
                continue
            for ch in ch_resp.json():
                if ch.get("type") not in (0, 5):
                    continue
                name = ch.get("name", "")
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=ch["id"],
                    name=f"{guild.get('name', '')}#{name}",
                    platform="discord",
                    extra={"guild_id": guild_id},
                ))

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
        before: Optional[str] = None

        while len(messages) < limit:
            params: dict = {"limit": min(100, limit - len(messages))}
            if before:
                params["before"] = before

            resp = requests.get(
                f"{API_BASE}/channels/{channel_id}/messages",
                headers=self._headers(), params=params, timeout=15,
            )
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break

            for msg in items:
                text = msg.get("content", "")
                if not text:
                    continue
                ts = self._parse_iso(msg.get("timestamp"))
                if since and ts and ts < since:
                    continue
                if until and ts and ts > until:
                    continue
                author = msg.get("author", {})
                sender = author.get("global_name") or author.get("username", "")
                messages.append(Message(
                    sender=sender,
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="discord",
                ))

            before = items[-1]["id"]
            if len(items) < 100:
                break

        return messages

    @staticmethod
    def _parse_iso(ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("+00:00", "+00:00"))
        except ValueError:
            return None
