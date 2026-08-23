"""WhatsApp 聊天记录采集器（导出文件解析）。

WhatsApp 没有公开的消息拉取 API。本采集器解析两种格式：
  1. WhatsApp 内置的「导出聊天」功能生成的 TXT 文件
  2. 第三方工具（如 KnugiHK/WhatsApp-Chat-Exporter）生成的 HTML/JSON

使用方式：
  1. 在 WhatsApp 中选择对话 → 更多 → 导出聊天 → 不含媒体
  2. 将导出的 .txt 文件路径传入 parse_exported_txt()
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel

# WhatsApp 导出格式常见模式（兼容多种日期格式）
LINE_PATTERNS = [
    # [DD/MM/YYYY, HH:MM:SS] Sender: Message
    re.compile(r"^\[?(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]?\s*-?\s*([^:]+):\s*(.+)$"),
    # DD/MM/YYYY, HH:MM - Sender: Message
    re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\s*-\s*([^:]+):\s*(.+)$"),
    # YYYY-MM-DD HH:MM:SS Sender: Message
    re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)\s*-?\s*([^:]+):\s*(.+)$"),
]


class WhatsAppCollector(BaseCollector):
    platform_name = "whatsapp"
    platform_name_zh = "WhatsApp"

    def authenticate(self) -> bool:
        self._authenticated = True
        return True

    def scan(self, keyword: str = "") -> list[Channel]:
        return []

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        return []

    @classmethod
    def parse_exported_txt(cls, txt_path: Path, encoding: str = "utf-8") -> list[Message]:
        """解析 WhatsApp 内置导出的 TXT 文件。"""
        messages: list[Message] = []
        content = txt_path.read_text(encoding=encoding)
        current_sender = ""
        current_ts: Optional[datetime] = None
        current_lines: list[str] = []

        for line in content.splitlines():
            matched = False
            for pattern in LINE_PATTERNS:
                m = pattern.match(line)
                if m:
                    if current_lines and current_sender:
                        messages.append(Message(
                            sender=current_sender,
                            text="\n".join(current_lines),
                            timestamp=current_ts,
                            platform="whatsapp",
                        ))
                    date_str, time_str = m.group(1), m.group(2)
                    current_sender = m.group(3).strip()
                    current_lines = [m.group(4)]
                    current_ts = cls._parse_datetime(date_str, time_str)
                    matched = True
                    break

            if not matched:
                stripped = line.strip()
                if stripped:
                    current_lines.append(stripped)

        if current_lines and current_sender:
            messages.append(Message(
                sender=current_sender,
                text="\n".join(current_lines),
                timestamp=current_ts,
                platform="whatsapp",
            ))

        return messages

    @classmethod
    def parse_exported_json(cls, json_path: Path) -> list[Message]:
        """解析第三方工具导出的 JSON 格式。"""
        messages: list[Message] = []
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("messages", [])
        for item in items:
            text = item.get("body") or item.get("text") or item.get("message", "")
            if not text:
                continue
            ts = None
            ts_val = item.get("timestamp") or item.get("date")
            if isinstance(ts_val, (int, float)):
                try:
                    ts = datetime.fromtimestamp(ts_val, tz=timezone.utc)
                except (ValueError, OSError):
                    pass
            messages.append(Message(
                sender=item.get("sender", item.get("from", "")),
                text=text,
                timestamp=ts,
                platform="whatsapp",
            ))
        return messages

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> Optional[datetime]:
        time_str = time_str.strip()
        for fmt in (
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
            "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M",
            "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
            "%m/%d/%y %I:%M %p", "%m/%d/%y %I:%M:%S %p",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        ):
            try:
                return datetime.strptime(f"{date_str} {time_str}", fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
