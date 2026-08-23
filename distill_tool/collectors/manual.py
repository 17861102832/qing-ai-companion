"""手动导入采集器。

支持从文件或剪贴板粘贴导入数据：
  - 纯文本文件 (.txt, .md)
  - JSON 文件
  - CSV 文件
  - 剪贴板粘贴的文本

这是最通用的采集方式，适用于所有无法自动采集的数据源。
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel


class ManualCollector(BaseCollector):
    platform_name = "manual"
    platform_name_zh = "手动导入"

    def authenticate(self) -> bool:
        self._authenticated = True
        return True

    def scan(self, keyword: str = "") -> list[Channel]:
        return [Channel(
            channel_id="manual",
            name="手动导入",
            platform="manual",
        )]

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        return []

    @classmethod
    def from_text(cls, text: str, source_label: str = "paste") -> list[Message]:
        """从粘贴的文本创建消息列表。按空行分段。"""
        messages: list[Message] = []
        paragraphs = re.split(r"\n\s*\n", text.strip())
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            messages.append(Message(
                sender="",
                text=para,
                timestamp=datetime.now(timezone.utc),
                channel_name=source_label,
                platform="manual",
            ))
        return messages

    @classmethod
    def from_file(cls, file_path: Path) -> list[Message]:
        """根据文件后缀自动选择解析方式。"""
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return cls._from_json(file_path)
        if suffix == ".csv":
            return cls._from_csv(file_path)
        return cls._from_text_file(file_path)

    @classmethod
    def _from_text_file(cls, path: Path) -> list[Message]:
        """按空行分段解析纯文本/Markdown。"""
        content = path.read_text(encoding="utf-8")
        return cls.from_text(content, source_label=path.name)

    @classmethod
    def _from_json(cls, path: Path) -> list[Message]:
        """解析 JSON 文件（支持数组或带 messages 字段的对象）。"""
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("messages", [])
        messages: list[Message] = []
        for item in items:
            if isinstance(item, str):
                messages.append(Message(
                    sender="", text=item,
                    timestamp=datetime.now(timezone.utc),
                    platform="manual",
                ))
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("content") or item.get("message", "")
            if not text:
                continue
            ts = None
            ts_val = item.get("timestamp") or item.get("date") or item.get("time")
            if isinstance(ts_val, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M"):
                    try:
                        ts = datetime.strptime(ts_val, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
            messages.append(Message(
                sender=item.get("sender", item.get("from", "")),
                text=text,
                timestamp=ts,
                channel_name=path.name,
                platform="manual",
            ))
        return messages

    @classmethod
    def _from_csv(cls, path: Path) -> list[Message]:
        """解析 CSV 文件（预期列: sender, text, time）。"""
        messages: list[Message] = []
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("text") or row.get("content") or row.get("message", "")
                if not text:
                    continue
                ts = None
                time_str = row.get("time") or row.get("date") or row.get("timestamp", "")
                if time_str:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            ts = datetime.strptime(time_str.strip(), fmt).replace(tzinfo=timezone.utc)
                            break
                        except ValueError:
                            continue
                messages.append(Message(
                    sender=row.get("sender", row.get("from", "")),
                    text=text,
                    timestamp=ts,
                    channel_name=path.name,
                    platform="manual",
                ))
        return messages
