"""采集器基类与统一消息格式。

所有平台采集器继承 BaseCollector，实现 authenticate / scan / collect 三个方法，
并使用 to_corpus() 将消息列表转为 intake-protocol 兼容的 Markdown。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Message:
    """统一消息格式——各采集器输出此结构。"""
    sender: str
    text: str
    timestamp: Optional[datetime] = None
    channel_name: str = ""
    msg_type: str = "text"
    platform: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def date_str(self) -> str:
        if self.timestamp:
            return self.timestamp.strftime("%Y-%m-%d %H:%M")
        return ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class Channel:
    """统一频道/会话格式。"""
    channel_id: str
    name: str
    platform: str
    member_count: int = 0
    extra: dict = field(default_factory=dict)


class BaseCollector(ABC):
    """采集器基类。"""

    platform_name: str = "unknown"
    platform_name_zh: str = "未知平台"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._authenticated = False

    @abstractmethod
    def authenticate(self) -> bool:
        """验证凭证，成功返回 True。"""
        ...

    @abstractmethod
    def scan(self, keyword: str = "") -> list[Channel]:
        """扫描可用的频道/会话列表。"""
        ...

    @abstractmethod
    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        """采集指定频道的消息。"""
        ...

    def to_corpus(
        self,
        messages: list[Message],
        channel_name: str = "",
        target: str = "",
    ) -> str:
        """将消息列表转为 intake-protocol 兼容的 Markdown 格式。"""
        meta_channel = f"{self.platform_name}_api"
        header = (
            f"<!-- channel: {meta_channel} | confidence: verbatim | scope: both -->\n"
            f"# {self.platform_name_zh}消息采集"
        )
        if channel_name:
            header += f"：{channel_name}"
        if target:
            header += f"（目标：{target}）"
        header += f"\n\n共 {len(messages)} 条消息\n\n---\n"

        lines = [header]
        for msg in messages:
            prefix = f"[{msg.date_str}]" if msg.date_str else "[]"
            sender_tag = f" **{msg.sender}**:" if msg.sender else ""
            lines.append(f"{prefix}{sender_tag} {msg.text}")

        return "\n".join(lines) + "\n"

    def save_corpus(
        self,
        messages: list[Message],
        output: Path,
        channel_name: str = "",
        target: str = "",
    ) -> Path:
        """将 corpus 写入文件。"""
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_corpus(messages, channel_name, target)
        output.write_text(content, encoding="utf-8")
        return output

    def save_json(self, messages: list[Message], output: Path) -> Path:
        """将消息列表保存为 JSON（便于后续处理）。"""
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        data = [msg.to_dict() for msg in messages]
        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output
