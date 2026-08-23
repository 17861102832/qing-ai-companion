"""Email 采集器。

支持两种数据源：
  1. mbox 文件（Gmail Takeout / Thunderbird 导出）
  2. Gmail API（OAuth2 认证）

对于大多数用户，推荐先通过 Google Takeout (https://takeout.google.com/) 导出
Gmail 的 mbox 文件，然后用 parse_mbox() 方法解析。
"""

from __future__ import annotations

import email
import email.header
import email.policy
import mailbox
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel


class EmailCollector(BaseCollector):
    platform_name = "email"
    platform_name_zh = "邮件"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._mbox_path: Optional[Path] = None
        if config and config.get("mbox_path"):
            self._mbox_path = Path(config["mbox_path"])

    def authenticate(self) -> bool:
        if self._mbox_path and self._mbox_path.is_file():
            self._authenticated = True
            return True
        return False

    def scan(self, keyword: str = "") -> list[Channel]:
        """扫描 mbox 文件中的通信对象列表。"""
        if not self._mbox_path:
            return []

        senders: dict[str, int] = {}
        try:
            mbox = mailbox.mbox(str(self._mbox_path))
            for msg in mbox:
                from_addr = self._decode_header(msg.get("From", ""))
                addr = self._extract_email(from_addr)
                if addr:
                    if keyword and keyword.lower() not in addr.lower():
                        continue
                    senders[addr] = senders.get(addr, 0) + 1
        except Exception:
            pass

        return [
            Channel(
                channel_id=addr,
                name=addr,
                platform="email",
                member_count=count,
            )
            for addr, count in sorted(senders.items(), key=lambda x: -x[1])
        ]

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        """采集与指定邮箱地址的往来邮件。"""
        if not self._mbox_path:
            return []

        messages: list[Message] = []
        try:
            mbox = mailbox.mbox(str(self._mbox_path))
            for msg in mbox:
                from_addr = self._extract_email(self._decode_header(msg.get("From", "")))
                to_addr = self._extract_email(self._decode_header(msg.get("To", "")))

                if channel_id not in (from_addr, to_addr):
                    continue

                body = self._get_body(msg)
                if not body.strip():
                    continue

                ts = self._parse_date(msg.get("Date"))
                if since and ts and ts < since:
                    continue
                if until and ts and ts > until:
                    continue

                subject = self._decode_header(msg.get("Subject", ""))
                text = f"**{subject}**\n\n{body}" if subject else body

                messages.append(Message(
                    sender=from_addr or "",
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="email",
                ))

                if len(messages) >= limit:
                    break
        except Exception:
            pass

        return messages

    @classmethod
    def parse_mbox(cls, mbox_path: Path, target_email: str = "", limit: int = 1000) -> list[Message]:
        """直接解析 mbox 文件为 Message 列表。"""
        collector = cls({"mbox_path": str(mbox_path)})
        if target_email:
            return collector.collect(target_email, limit=limit)
        messages: list[Message] = []
        mbox = mailbox.mbox(str(mbox_path))
        for msg in mbox:
            body = cls._get_body(msg)
            if not body.strip():
                continue
            from_addr = cls._extract_email(cls._decode_header(msg.get("From", "")))
            subject = cls._decode_header(msg.get("Subject", ""))
            ts = cls._parse_date(msg.get("Date"))
            text = f"**{subject}**\n\n{body}" if subject else body
            messages.append(Message(
                sender=from_addr or "",
                text=text,
                timestamp=ts,
                platform="email",
            ))
            if len(messages) >= limit:
                break
        return messages

    @staticmethod
    def _decode_header(header_val: str) -> str:
        if not header_val:
            return ""
        decoded = email.header.decode_header(header_val)
        parts = []
        for part, charset in decoded:
            if isinstance(part, bytes):
                parts.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(part)
        return " ".join(parts)

    @staticmethod
    def _extract_email(text: str) -> str:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        return m.group(0).lower() if m else text.strip().lower()

    @staticmethod
    def _get_body(msg: email.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html = payload.decode(charset, errors="replace")
                        return re.sub(r"<[^>]+>", "", html)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
