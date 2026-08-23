"""通用社交媒体归档解析器。

支持解析 Google Takeout、Facebook/Instagram 数据下载等标准归档格式。
每个平台的归档格式不同，本模块提供统一的入口和多种解析策略。

支持的归档类型：
  - Google Takeout (YouTube 评论、Google+ 等)
  - Facebook/Instagram 数据下载 (JSON 格式)
  - 微博导出
  - 知乎导出
  - 通用 JSON 数组格式
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel


class SocialArchiveCollector(BaseCollector):
    platform_name = "social_archive"
    platform_name_zh = "社交媒体归档"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._archive_path: Optional[Path] = None
        if config and config.get("archive_path"):
            self._archive_path = Path(config["archive_path"])

    def authenticate(self) -> bool:
        if self._archive_path and self._archive_path.exists():
            self._authenticated = True
            return True
        return False

    def scan(self, keyword: str = "") -> list[Channel]:
        if not self._archive_path:
            return []
        channels: list[Channel] = []
        if self._archive_path.is_dir():
            for f in self._archive_path.rglob("*.json"):
                name = f.stem
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=str(f),
                    name=name,
                    platform="social_archive",
                ))
        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        path = Path(channel_id)
        if not path.is_file():
            return []
        return self.parse_json_file(path, since, until, limit)

    @classmethod
    def parse_json_file(
        cls,
        json_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[Message]:
        """通用 JSON 解析——自动检测格式。"""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return cls._parse_array(data, since, until, limit)
        if isinstance(data, dict):
            for key in ("messages", "posts", "comments", "items", "data", "statuses"):
                if key in data and isinstance(data[key], list):
                    return cls._parse_array(data[key], since, until, limit)
        return []

    @classmethod
    def parse_facebook_json(cls, json_path: Path, limit: int = 1000) -> list[Message]:
        """解析 Facebook/Instagram 数据下载的 JSON。"""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data.get("messages", data.get("posts", []))
        messages: list[Message] = []
        for item in items:
            content = item.get("content") or item.get("data", [{}])[0].get("post", "")
            if not content:
                continue
            ts = None
            ts_val = item.get("timestamp_ms") or item.get("timestamp")
            if ts_val:
                try:
                    if isinstance(ts_val, int) and ts_val > 1e12:
                        ts = datetime.fromtimestamp(ts_val / 1000, tz=timezone.utc)
                    elif isinstance(ts_val, (int, float)):
                        ts = datetime.fromtimestamp(ts_val, tz=timezone.utc)
                except (ValueError, OSError):
                    pass
            messages.append(Message(
                sender=item.get("sender_name", item.get("name", "")),
                text=content,
                timestamp=ts,
                platform="facebook",
            ))
            if len(messages) >= limit:
                break
        return messages

    @classmethod
    def _parse_array(
        cls,
        items: list,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[Message]:
        messages: list[Message] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = (
                item.get("text")
                or item.get("content")
                or item.get("body")
                or item.get("message")
                or item.get("post")
                or ""
            )
            if not text:
                continue
            ts = cls._extract_timestamp(item)
            if since and ts and ts < since:
                continue
            if until and ts and ts > until:
                continue
            sender = (
                item.get("sender")
                or item.get("sender_name")
                or item.get("author")
                or item.get("user")
                or item.get("from")
                or ""
            )
            if isinstance(sender, dict):
                sender = sender.get("name", sender.get("username", ""))
            messages.append(Message(
                sender=str(sender),
                text=text,
                timestamp=ts,
                platform="social_archive",
            ))
            if len(messages) >= limit:
                break
        return messages

    @staticmethod
    def _extract_timestamp(item: dict) -> Optional[datetime]:
        for key in ("timestamp", "timestamp_ms", "created_at", "date", "time", "createdAt"):
            val = item.get(key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                try:
                    if val > 1e12:
                        return datetime.fromtimestamp(val / 1000, tz=timezone.utc)
                    return datetime.fromtimestamp(val, tz=timezone.utc)
                except (ValueError, OSError):
                    continue
            if isinstance(val, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        return None
