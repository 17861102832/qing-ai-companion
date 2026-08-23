"""钉钉数据采集器。

通过钉钉开放 API 采集群聊消息。
需要钉钉企业内部应用的 AppKey / AppSecret。

认证方式：
  - 环境变量 DINGTALK_APP_KEY / DINGTALK_APP_SECRET
  - 配置文件 ~/.immortal-skill/dingtalk.json

API 文档：https://open.dingtalk.com/
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
CONFIG_FILE = CONFIG_DIR / "dingtalk.json"
BASE_URL = "https://oapi.dingtalk.com"
API_NEW = "https://api.dingtalk.com"


class DingtalkCollector(BaseCollector):
    platform_name = "dingtalk"
    platform_name_zh = "钉钉"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._token_cache: dict = {}

    def _require_requests(self) -> None:
        if requests is None:
            raise ImportError("需要 requests 库：pip3 install requests")

    def _load_credentials(self) -> tuple[str, str]:
        key = os.environ.get("DINGTALK_APP_KEY", "") or self.config.get("app_key", "")
        secret = os.environ.get("DINGTALK_APP_SECRET", "") or self.config.get("app_secret", "")
        if key and secret:
            return key, secret
        if CONFIG_FILE.is_file():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return cfg.get("app_key", ""), cfg.get("app_secret", "")
        return "", ""

    def _get_access_token(self) -> str:
        if (
            self._token_cache.get("token")
            and self._token_cache.get("expires_at", 0) > time.time()
        ):
            return self._token_cache["token"]

        key, secret = self._load_credentials()
        if not key or not secret:
            raise RuntimeError("未配置钉钉凭证。请设置环境变量或运行 immortal_cli.py setup dingtalk")

        resp = requests.post(
            f"{API_NEW}/v1.0/oauth2/accessToken",
            json={"appKey": key, "appSecret": secret},
            timeout=10,
        )
        data = resp.json()
        token = data.get("accessToken")
        if not token:
            raise RuntimeError(f"获取钉钉 token 失败：{data}")

        self._token_cache["token"] = token
        self._token_cache["expires_at"] = time.time() + data.get("expireIn", 7200) - 300
        return token

    def _headers(self) -> dict:
        return {"x-acs-dingtalk-access-token": self._get_access_token()}

    def authenticate(self) -> bool:
        self._require_requests()
        try:
            self._get_access_token()
            self._authenticated = True
            return True
        except RuntimeError:
            return False

    def scan(self, keyword: str = "") -> list[Channel]:
        self._require_requests()
        channels: list[Channel] = []
        page_token = ""

        while True:
            params: dict = {"maxResults": 100}
            if page_token:
                params["nextToken"] = page_token

            resp = requests.get(
                f"{API_NEW}/v1.0/im/privilegedAccess/groupInfos",
                headers=self._headers(), params=params, timeout=15,
            )
            data = resp.json()
            if not data.get("success", True):
                break

            for group in data.get("result", {}).get("records", []):
                name = group.get("title", "(未命名)")
                if keyword and keyword.lower() not in name.lower():
                    continue
                channels.append(Channel(
                    channel_id=group.get("openConversationId", ""),
                    name=name,
                    platform="dingtalk",
                    member_count=group.get("memberCount", 0),
                ))

            page_token = data.get("result", {}).get("nextToken", "")
            if not page_token:
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
        next_token: Optional[str] = None

        while len(messages) < limit:
            body: dict = {
                "openConversationId": channel_id,
                "maxResults": min(50, limit - len(messages)),
            }
            if next_token:
                body["nextToken"] = next_token

            resp = requests.post(
                f"{API_NEW}/v1.0/im/privilegedAccess/messages",
                headers=self._headers(), json=body, timeout=15,
            )
            data = resp.json()
            if not data.get("success", True):
                break

            for msg in data.get("result", {}).get("records", []):
                text = msg.get("text", "")
                if not text:
                    continue

                ts = self._parse_timestamp(msg.get("createAt"))
                messages.append(Message(
                    sender=msg.get("senderNick", msg.get("senderId", "")),
                    text=text,
                    timestamp=ts,
                    channel_name=channel_id,
                    platform="dingtalk",
                ))

            next_token = data.get("result", {}).get("nextToken")
            if not next_token:
                break

        return messages

    @staticmethod
    def _parse_timestamp(ts_ms: Optional[int]) -> Optional[datetime]:
        if not ts_ms:
            return None
        try:
            return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            return None

    @classmethod
    def setup_interactive(cls) -> None:
        """交互式配置钉钉凭证。"""
        print("钉钉凭证配置")
        print("需要钉钉企业内部应用。")
        print("开放平台：https://open.dingtalk.com/\n")

        app_key = input("AppKey: ").strip()
        app_secret = input("AppSecret: ").strip()
        if not app_key or not app_secret:
            raise ValueError("AppKey 和 AppSecret 不能为空")

        collector = cls({"app_key": app_key, "app_secret": app_secret})
        if not collector.authenticate():
            raise RuntimeError("凭证验证失败")

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps({"app_key": app_key, "app_secret": app_secret}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n凭证已保存到 {CONFIG_FILE}")
