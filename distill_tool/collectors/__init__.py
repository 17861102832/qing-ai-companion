"""immortal-skill 多平台数据采集器。

统一接口：所有采集器继承 BaseCollector，输出标准 Message 格式，
最终转为 intake-protocol 兼容的 Markdown corpus。

按数据获取方式分三类：
  API:      飞书、钉钉、Slack、Discord、Telegram、Email (Gmail)
  Local DB: 微信 (SQLite)、iMessage (chat.db)
  Archive:  WhatsApp (txt)、Twitter/X (archive zip)、社交媒体 (Takeout)、手动导入
"""

from .base import BaseCollector, Message, Channel  # noqa: F401
