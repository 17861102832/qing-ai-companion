"""飞书数据采集器。

通过飞书开放 API 采集群聊消息与文档内容。
需要飞书自建应用（已开启机器人能力）的 App ID / App Secret。

认证方式：
  - 环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET
  - 配置文件 ~/.immortal-skill/feishu.json
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Message, Channel

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

CONFIG_DIR = Path.home() / ".immortal-skill"
CONFIG_FILE = CONFIG_DIR / "feishu.json"
BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuCollector(BaseCollector):
    platform_name = "feishu"
    platform_name_zh = "飞书"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._token_cache: dict = {}

    def _require_requests(self) -> None:
        if requests is None:
            raise ImportError("需要 requests 库：pip3 install requests")

    def _load_credentials(self) -> tuple[str, str]:
        app_id = os.environ.get("FEISHU_APP_ID", "") or self.config.get("app_id", "")
        app_secret = os.environ.get("FEISHU_APP_SECRET", "") or self.config.get("app_secret", "")
        if app_id and app_secret:
            return app_id, app_secret
        if CONFIG_FILE.is_file():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return cfg.get("app_id", ""), cfg.get("app_secret", "")
        return "", ""

    def _get_tenant_token(self) -> str:
        if (
            self._token_cache.get("token")
            and self._token_cache.get("expires_at", 0) > time.time()
        ):
            return self._token_cache["token"]

        app_id, app_secret = self._load_credentials()
        if not app_id or not app_secret:
            raise RuntimeError("未配置飞书凭证。请设置环境变量或运行 immortal_cli.py setup feishu")

        resp = requests.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败：{data.get('msg', resp.text)}")

        token = data["tenant_access_token"]
        self._token_cache["token"] = token
        self._token_cache["expires_at"] = time.time() + data.get("expire", 7200) - 300
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_tenant_token()}"}

    def authenticate(self) -> bool:
        self._require_requests()
        try:
            self._get_tenant_token()
            self._authenticated = True
            return True
        except RuntimeError:
            return False

    def scan(self, keyword: str = "") -> list[Channel]:
        self._require_requests()
        channels: list[Channel] = []
        page_token = ""

        while True:
            params: dict = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(
                f"{BASE_URL}/im/v1/chats",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if data.get("code") != 0:
                break

            for chat in data.get("data", {}).get("items", []):
                name = chat.get("name", "(未命名)")
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=chat.get("chat_id", ""),
                    name=name,
                    platform="feishu",
                    member_count=chat.get("user_count", 0),
                ))

            page_token = data.get("data", {}).get("page_token", "")
            if not data.get("data", {}).get("has_more", False):
                break

        return channels

    def collect(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[Message]:
        self._require_requests()
        messages: list[Message] = []
        page_token = ""

        while len(messages) < limit:
            params: dict = {
                "container_id_type": "chat",
                "container_id": channel_id,
                "page_size": 50,
                "sort_type": "ByCreateTimeDesc",
            }
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(
                f"{BASE_URL}/im/v1/messages",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if data.get("code") != 0:
                break

            for item in data.get("data", {}).get("items", []):
                text = self._extract_text(item)
                if text is None:
                    continue

                ts = self._parse_timestamp(item.get("create_time", ""))
                sender = item.get("sender", {}).get("sender_id", {}).get("open_id", "")

                messages.append(Message(
                    sender=sender,
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="feishu",
                ))

                if len(messages) >= limit:
                    break

            page_token = data.get("data", {}).get("page_token", "")
            if not data.get("data", {}).get("has_more", False):
                break

        return messages

    def collect_document(self, doc_token: str) -> str:
        """导出飞书文档为 Markdown 文本。"""
        self._require_requests()
        blocks: list[dict] = []
        page_token = ""

        while True:
            params: dict = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(
                f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"飞书文档 API 错误：{data.get('msg', resp.text)}")

            blocks.extend(data.get("data", {}).get("items", []))
            page_token = data.get("data", {}).get("page_token", "")
            if not data.get("data", {}).get("has_more", False):
                break

        return self._blocks_to_markdown(blocks)

    @staticmethod
    def _extract_text(item: dict) -> Optional[str]:
        msg_type = item.get("msg_type", "")
        body = item.get("body", {})
        content_str = body.get("content", "")
        if not content_str:
            return None

        try:
            content = json.loads(content_str)
        except (json.JSONDecodeError, TypeError):
            return content_str if isinstance(content_str, str) else None

        if msg_type == "text":
            return content.get("text", "")
        if msg_type == "post":
            lines = []
            for lang_content in content.values():
                if isinstance(lang_content, dict):
                    title = lang_content.get("title", "")
                    if title:
                        lines.append(f"**{title}**")
                    for para in lang_content.get("content", []):
                        if isinstance(para, list):
                            parts = [
                                e.get("text", "")
                                for e in para
                                if isinstance(e, dict) and e.get("tag") == "text"
                            ]
                            if parts:
                                lines.append("".join(parts))
            return "\n".join(lines) if lines else None

        return f"[{msg_type} 消息]"

    @staticmethod
    def _parse_timestamp(ts_str: str) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            ts = int(ts_str) // 1000 if len(ts_str) > 10 else int(ts_str)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    @staticmethod
    def _blocks_to_markdown(blocks: list[dict]) -> str:
        heading_prefix = {3: "# ", 4: "## ", 5: "### ", 9: "- ", 10: "1. "}
        lines = []
        for block in blocks:
            bt = block.get("block_type", 0)
            text_run = (
                block.get("text", {})
                or block.get("heading1", {})
                or block.get("heading2", {})
                or block.get("heading3", {})
            )
            if isinstance(text_run, dict):
                elements = text_run.get("elements", [])
                text = "".join(
                    e.get("text_run", {}).get("content", "") for e in elements
                )
                if text:
                    lines.append(heading_prefix.get(bt, "") + text)
            elif bt == 14:
                lines.append("---")
        return "\n".join(lines)

    @classmethod
    def setup_interactive(cls) -> None:
        """交互式配置飞书凭证。"""
        print("飞书凭证配置")
        print("需要一个飞书自建应用，且已开启机器人能力。")
        print("开放平台：https://open.feishu.cn/app\n")

        app_id = input("App ID: ").strip()
        app_secret = input("App Secret: ").strip()
        if not app_id or not app_secret:
            raise ValueError("App ID 和 App Secret 不能为空")

        collector = cls({"app_id": app_id, "app_secret": app_secret})
        if not collector.authenticate():
            raise RuntimeError("凭证验证失败")

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps({"app_id": app_id, "app_secret": app_secret}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n凭证已保存到 {CONFIG_FILE}")
