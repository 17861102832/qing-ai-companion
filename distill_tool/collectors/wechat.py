"""微信聊天记录采集器（本地 SQLite 解析）。

微信没有公开的消息导出 API，本采集器通过读取本地 SQLite 数据库实现。
支持两种数据来源：
  1. Windows 版微信的本地数据库（EnMicroMsg.db，需解密）
  2. iOS 备份中的微信数据库（通过 iTunes/Finder 备份后解析）

对于大多数用户，推荐使用 WeChatMsg/PyWxDump 等工具先导出为 CSV/HTML/TXT，
然后用本采集器的 parse_exported() 方法解析导出文件。

参考工具：
  - LC044/WeChatMsg (Windows): https://github.com/LC044/WeChatMsg
  - BlueMatthew/WechatExporter (iOS): https://github.com/BlueMatthew/WechatExporter
"""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel


class WechatCollector(BaseCollector):
    platform_name = "wechat"
    platform_name_zh = "微信"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._db_path: Optional[Path] = None
        if config and config.get("db_path"):
            self._db_path = Path(config["db_path"])

    def authenticate(self) -> bool:
        if self._db_path and self._db_path.is_file():
            self._authenticated = True
            return True
        return False

    def scan(self, keyword: str = "") -> list[Channel]:
        if not self._db_path or not self._db_path.is_file():
            return []

        channels: list[Channel] = []
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.execute(
                "SELECT DISTINCT StrTalker, COUNT(*) as cnt FROM MSG "
                "GROUP BY StrTalker ORDER BY cnt DESC"
            )
            for row in cursor:
                name = row[0] or ""
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=name,
                    name=name,
                    platform="wechat",
                    member_count=row[1],
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
        if not self._db_path or not self._db_path.is_file():
            return []

        messages: list[Message] = []
        try:
            conn = sqlite3.connect(str(self._db_path))
            query = (
                "SELECT StrContent, CreateTime, IsSender, StrTalker "
                "FROM MSG WHERE StrTalker = ? AND Type = 1 "
                "ORDER BY CreateTime DESC LIMIT ?"
            )
            cursor = conn.execute(query, (channel_id, limit))
            for row in cursor:
                text = row[0] or ""
                if not text.strip():
                    continue
                ts = self._parse_timestamp(row[1])
                sender = "我" if row[2] == 1 else channel_id
                messages.append(Message(
                    sender=sender,
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="wechat",
                ))
            conn.close()
        except sqlite3.Error:
            pass

        return messages

    @staticmethod
    def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    @classmethod
    def parse_exported_csv(cls, csv_path: Path, encoding: str = "utf-8") -> list[Message]:
        """解析第三方工具导出的 CSV 格式（WeChatMsg 格式）。
        预期列: 发送者, 内容, 时间
        """
        messages: list[Message] = []
        with open(csv_path, encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return messages
            for row in reader:
                if len(row) < 3:
                    continue
                sender, text, time_str = row[0], row[1], row[2]
                if not text.strip():
                    continue
                ts = None
                try:
                    ts = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M:%S")
                    ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                messages.append(Message(
                    sender=sender.strip(),
                    text=text.strip(),
                    timestamp=ts,
                    platform="wechat",
                ))
        return messages

    @classmethod
    def parse_exported_txt(cls, txt_path: Path, encoding: str = "utf-8") -> list[Message]:
        """解析微信原生导出的 TXT 格式或 WechatExporter 的文本输出。
        常见格式: 2025-01-15 14:30:00 张三\n消息内容
        """
        messages: list[Message] = []
        pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s+(.+)$"
        )
        content = txt_path.read_text(encoding=encoding)
        current_sender = ""
        current_ts: Optional[datetime] = None
        current_lines: list[str] = []

        for line in content.splitlines():
            m = pattern.match(line)
            if m:
                if current_lines and current_sender:
                    messages.append(Message(
                        sender=current_sender,
                        text="\n".join(current_lines),
                        timestamp=current_ts,
                        platform="wechat",
                    ))
                time_str, current_sender = m.group(1), m.group(2)
                current_lines = []
                try:
                    fmt = "%Y-%m-%d %H:%M:%S" if len(time_str) > 16 else "%Y-%m-%d %H:%M"
                    current_ts = datetime.strptime(time_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    current_ts = None
            else:
                stripped = line.strip()
                if stripped:
                    current_lines.append(stripped)

        if current_lines and current_sender:
            messages.append(Message(
                sender=current_sender,
                text="\n".join(current_lines),
                timestamp=current_ts,
                platform="wechat",
            ))

        return messages
