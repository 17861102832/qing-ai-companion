"""Twitter/X 归档解析器。

解析 X (Twitter) 官方数据归档中的推文。
获取归档：Settings > Your account > Download an archive of your data

归档结构：
  twitter-archive/
  ├── data/
  │   ├── tweets.js        # 推文
  │   ├── like.js          # 点赞
  │   ├── direct-messages.js # DM
  │   └── ...
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel


class TwitterCollector(BaseCollector):
    platform_name = "twitter"
    platform_name_zh = "Twitter/X"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._archive_path: Optional[Path] = None
        if config and config.get("archive_path"):
            self._archive_path = Path(config["archive_path"])

    def authenticate(self) -> bool:
        if self._archive_path and self._archive_path.is_dir():
            tweets_file = self._archive_path / "data" / "tweets.js"
            if not tweets_file.is_file():
                tweets_file = self._archive_path / "data" / "tweet.js"
            self._authenticated = tweets_file.is_file()
            return self._authenticated
        return False

    def scan(self, keyword: str = "") -> list[Channel]:
        if not self._archive_path:
            return []
        channels = []
        data_dir = self._archive_path / "data"
        if not data_dir.is_dir():
            return channels
        for f in ("tweets.js", "tweet.js"):
            if (data_dir / f).is_file():
                channels.append(Channel(
                    channel_id="tweets",
                    name="推文",
                    platform="twitter",
                ))
        if (data_dir / "direct-messages.js").is_file():
            channels.append(Channel(
                channel_id="dms",
                name="私信",
                platform="twitter",
            ))
        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        if not self._archive_path:
            return []
        if channel_id == "tweets":
            return self._parse_tweets(since, until, limit)
        if channel_id == "dms":
            return self._parse_dms(since, until, limit)
        return []

    def _parse_tweets(
        self,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[Message]:
        data_dir = self._archive_path / "data"  # type: ignore[union-attr]
        for fname in ("tweets.js", "tweet.js"):
            fpath = data_dir / fname
            if fpath.is_file():
                raw = self._load_js_data(fpath)
                break
        else:
            return []

        messages: list[Message] = []
        for item in raw:
            tweet = item.get("tweet", item)
            text = tweet.get("full_text", tweet.get("text", ""))
            if not text:
                continue
            ts = self._parse_twitter_date(tweet.get("created_at"))
            if since and ts and ts < since:
                continue
            if until and ts and ts > until:
                continue
            messages.append(Message(
                sender="@me",
                text=text,
                timestamp=ts,
                channel_name="tweets",
                platform="twitter",
            ))
            if len(messages) >= limit:
                break
        return messages

    def _parse_dms(
        self,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[Message]:
        fpath = self._archive_path / "data" / "direct-messages.js"  # type: ignore[union-attr]
        if not fpath.is_file():
            return []
        raw = self._load_js_data(fpath)
        messages: list[Message] = []
        for conv in raw:
            dm_conv = conv.get("dmConversation", conv)
            for msg_item in dm_conv.get("messages", []):
                msg_data = msg_item.get("messageCreate", {})
                text = msg_data.get("text", "")
                if not text:
                    continue
                ts = self._parse_twitter_date(msg_data.get("createdAt"))
                if since and ts and ts < since:
                    continue
                if until and ts and ts > until:
                    continue
                messages.append(Message(
                    sender=msg_data.get("senderId", ""),
                    text=text,
                    timestamp=ts,
                    channel_name="dms",
                    platform="twitter",
                ))
                if len(messages) >= limit:
                    return messages
        return messages

    @staticmethod
    def _load_js_data(path: Path) -> list:
        """加载 Twitter 归档的 .js 文件（去掉开头的变量赋值）。"""
        content = path.read_text(encoding="utf-8")
        content = re.sub(r"^window\.\w+\.\w+\s*=\s*", "", content, count=1)
        content = re.sub(r"^\w+\s*=\s*", "", content, count=1)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _parse_twitter_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in (
            "%a %b %d %H:%M:%S %z %Y",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
        ):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
