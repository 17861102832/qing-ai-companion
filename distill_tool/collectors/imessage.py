"""iMessage 采集器（macOS 本地 SQLite）。

直接读取 macOS 的 Messages 数据库 ~/Library/Messages/chat.db。
需要「完全磁盘访问权限」（System Settings > Privacy & Security > Full Disk Access）。

仅在 macOS 上可用。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel

CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


class IMessageCollector(BaseCollector):
    platform_name = "imessage"
    platform_name_zh = "iMessage"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._db_path = Path(config.get("db_path", str(CHAT_DB))) if config else CHAT_DB

    def authenticate(self) -> bool:
        if self._db_path.is_file():
            try:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute("SELECT COUNT(*) FROM message LIMIT 1")
                conn.close()
                self._authenticated = True
                return True
            except sqlite3.Error:
                pass
        return False

    def scan(self, keyword: str = "") -> list[Channel]:
        if not self._db_path.is_file():
            return []

        channels: list[Channel] = []
        try:
            conn = sqlite3.connect(str(self._db_path))
            query = """
                SELECT c.ROWID, c.chat_identifier, c.display_name,
                       COUNT(cm.message_id) as msg_count
                FROM chat c
                LEFT JOIN chat_message_join cm ON c.ROWID = cm.chat_id
                GROUP BY c.ROWID
                ORDER BY msg_count DESC
            """
            for row in conn.execute(query):
                name = row[2] or row[1] or str(row[0])
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=str(row[0]),
                    name=name,
                    platform="imessage",
                    member_count=row[3],
                ))
            conn.close()
        except sqlite3.Error:
            pass
        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        if not self._db_path.is_file():
            return []

        messages: list[Message] = []
        try:
            conn = sqlite3.connect(str(self._db_path))
            query = """
                SELECT m.text, m.date, m.is_from_me,
                       COALESCE(h.id, '') as sender_id
                FROM message m
                JOIN chat_message_join cm ON m.ROWID = cm.message_id
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                WHERE cm.chat_id = ?
                  AND m.text IS NOT NULL AND m.text != ''
                ORDER BY m.date DESC
                LIMIT ?
            """
            for row in conn.execute(query, (int(channel_id), limit)):
                text = row[0]
                if not text or not text.strip():
                    continue
                ts = self._apple_ts_to_datetime(row[1])
                if since and ts and ts < since:
                    continue
                if until and ts and ts > until:
                    continue
                sender = "我" if row[2] == 1 else (row[3] or "对方")
                messages.append(Message(
                    sender=sender,
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="imessage",
                ))
            conn.close()
        except sqlite3.Error:
            pass
        return messages

    @staticmethod
    def _apple_ts_to_datetime(ts: Optional[int]) -> Optional[datetime]:
        """Apple Core Data 时间戳转 datetime（纳秒自 2001-01-01）。"""
        if ts is None:
            return None
        try:
            seconds = ts / 1_000_000_000
            return APPLE_EPOCH + timedelta(seconds=seconds)
        except (ValueError, OverflowError):
            return None
