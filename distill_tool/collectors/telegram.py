"""Telegram 采集器。

通过 Telethon（MTProto 客户端库）采集消息。
需要 Telegram API 凭证（从 https://my.telegram.org 获取）。

依赖：pip3 install telethon

认证方式：
  - 环境变量 TELEGRAM_API_ID / TELEGRAM_API_HASH
  - 配置文件 ~/.immortal-skill/telegram.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel

CONFIG_DIR = Path.home() / ".immortal-skill"
CONFIG_FILE = CONFIG_DIR / "telegram.json"

try:
    from telethon import TelegramClient
    from telethon.tl.types import User, Chat, Channel as TGChannel
    HAS_TELETHON = True
except ImportError:
    HAS_TELETHON = False


class TelegramCollector(BaseCollector):
    platform_name = "telegram"
    platform_name_zh = "Telegram"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client: Optional[object] = None

    def _load_credentials(self) -> tuple[int, str]:
        api_id = os.environ.get("TELEGRAM_API_ID", "") or (self.config or {}).get("api_id", "")
        api_hash = os.environ.get("TELEGRAM_API_HASH", "") or (self.config or {}).get("api_hash", "")
        if api_id and api_hash:
            return int(api_id), api_hash
        if CONFIG_FILE.is_file():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return int(cfg.get("api_id", 0)), cfg.get("api_hash", "")
        return 0, ""

    def _get_client(self) -> "TelegramClient":
        if self._client is not None:
            return self._client
        if not HAS_TELETHON:
            raise ImportError("需要 telethon 库：pip3 install telethon")
        api_id, api_hash = self._load_credentials()
        if not api_id or not api_hash:
            raise RuntimeError("未配置 Telegram 凭证")
        session_path = str(CONFIG_DIR / "telegram_session")
        self._client = TelegramClient(session_path, api_id, api_hash)
        return self._client

    def authenticate(self) -> bool:
        try:
            client = self._get_client()
            client.start()  # type: ignore[attr-defined]
            self._authenticated = True
            return True
        except Exception:
            return False

    def scan(self, keyword: str = "") -> list[Channel]:
        if not HAS_TELETHON:
            return []
        channels: list[Channel] = []
        try:
            client = self._get_client()
            with client:
                for dialog in client.iter_dialogs():  # type: ignore[attr-defined]
                    name = dialog.name or str(dialog.id)
                    if keyword and keyword.lower() not in name.lower():
                        continue
                    channels.append(Channel(
                        channel_id=str(dialog.id),
                        name=name,
                        platform="telegram",
                        member_count=getattr(dialog.entity, "participants_count", 0) or 0,
                    ))
        except Exception:
            pass
        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        if not HAS_TELETHON:
            return []
        messages: list[Message] = []
        try:
            client = self._get_client()
            entity = int(channel_id) if channel_id.lstrip("-").isdigit() else channel_id
            with client:
                for msg in client.iter_messages(  # type: ignore[attr-defined]
                    entity, limit=limit, offset_date=until, reverse=False,
                ):
                    if not msg.text:
                        continue
                    ts = msg.date.replace(tzinfo=timezone.utc) if msg.date else None
                    if since and ts and ts < since:
                        break
                    sender_name = ""
                    if msg.sender:
                        if hasattr(msg.sender, "first_name"):
                            sender_name = (msg.sender.first_name or "") + " " + (msg.sender.last_name or "")
                            sender_name = sender_name.strip()
                        elif hasattr(msg.sender, "title"):
                            sender_name = msg.sender.title or ""
                    messages.append(Message(
                        sender=sender_name or str(msg.sender_id or ""),
                        text=msg.text,
                        timestamp=ts,
                        channel_name=str(channel_id),
                        platform="telegram",
                    ))
        except Exception:
            pass
        return messages

    @classmethod
    def setup_interactive(cls) -> None:
        """交互式配置 Telegram 凭证。"""
        print("Telegram API 配置")
        print("获取凭证：https://my.telegram.org -> API development tools\n")

        api_id = input("API ID: ").strip()
        api_hash = input("API Hash: ").strip()
        if not api_id or not api_hash:
            raise ValueError("API ID 和 API Hash 不能为空")

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps({"api_id": api_id, "api_hash": api_hash}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n凭证已保存到 {CONFIG_FILE}")
        print("首次连接时需要输入手机号和验证码。")
