#!/usr/bin/env python3
"""immortal-skill 统一 CLI 入口。

整合数据采集、目录管理、版本管理的所有操作。

用法：
  python3 immortal_cli.py collect --platform feishu [选项]
  python3 immortal_cli.py collect --platform wechat --db ~/wechat.db [选项]
  python3 immortal_cli.py collect --platform imessage [选项]
  python3 immortal_cli.py setup <platform>
  python3 immortal_cli.py init --slug <slug> --persona <角色>
  python3 immortal_cli.py stamp --slug <slug>
  python3 immortal_cli.py snapshot --slug <slug>
  python3 immortal_cli.py rollback --slug <slug> --tag <tag>
  python3 immortal_cli.py list-snapshots --slug <slug>
  python3 immortal_cli.py platforms
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

PLATFORM_MAP = {
    "feishu": ("collectors.feishu", "FeishuCollector"),
    "dingtalk": ("collectors.dingtalk", "DingtalkCollector"),
    "wechat": ("collectors.wechat", "WechatCollector"),
    "imessage": ("collectors.imessage", "IMessageCollector"),
    "telegram": ("collectors.telegram", "TelegramCollector"),
    "whatsapp": ("collectors.whatsapp", "WhatsAppCollector"),
    "slack": ("collectors.slack", "SlackCollector"),
    "discord": ("collectors.discord", "DiscordCollector"),
    "email": ("collectors.email_collector", "EmailCollector"),
    "twitter": ("collectors.twitter", "TwitterCollector"),
    "social": ("collectors.social_archive", "SocialArchiveCollector"),
    "manual": ("collectors.manual", "ManualCollector"),
}


def _get_collector(platform: str, config: dict = None):
    if platform not in PLATFORM_MAP:
        print(f"错误：未知平台 '{platform}'。可用平台：{', '.join(PLATFORM_MAP.keys())}", file=sys.stderr)
        sys.exit(1)
    mod_name, cls_name = PLATFORM_MAP[platform]
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls(config or {})


def cmd_platforms(args: argparse.Namespace) -> None:
    """列出支持的平台。"""
    categories = {
        "API 实时拉取": ["feishu", "dingtalk", "slack", "discord", "telegram", "email"],
        "本地数据库": ["wechat", "imessage"],
        "归档文件": ["whatsapp", "twitter", "social"],
        "手动导入": ["manual"],
    }
    print("支持的数据平台：\n")
    for cat, platforms in categories.items():
        print(f"  {cat}:")
        for p in platforms:
            mod_name, cls_name = PLATFORM_MAP[p]
            print(f"    {p:12s} → {cls_name}")
        print()


def cmd_setup(args: argparse.Namespace) -> None:
    """配置平台凭证。"""
    platform = args.platform
    collector = _get_collector(platform)
    if hasattr(collector, "setup_interactive"):
        collector.setup_interactive()
    else:
        print(f"平台 {platform} 不需要交互式配置。")


def cmd_collect(args: argparse.Namespace) -> None:
    """采集数据。"""
    config: dict = {}
    if args.db:
        config["db_path"] = args.db
    if args.archive:
        config["archive_path"] = args.archive
    if args.mbox:
        config["mbox_path"] = args.mbox
    if args.token:
        config["token"] = args.token

    collector = _get_collector(args.platform, config)

    if not collector.authenticate():
        print(f"错误：{args.platform} 认证失败。请先运行 setup 或检查配置。", file=sys.stderr)
        sys.exit(1)

    if args.scan:
        channels = collector.scan(keyword=args.keyword or "")
        if not channels:
            print("未找到频道/会话。")
            return
        print(f"共 {len(channels)} 个频道/会话：\n")
        for ch in channels:
            extra = f" ({ch.member_count} 条)" if ch.member_count else ""
            print(f"  {ch.channel_id}  {ch.name}{extra}")
        return

    if not args.channel:
        print("错误：需要指定 --channel 或使用 --scan 查看可用频道", file=sys.stderr)
        sys.exit(1)

    print(f"正在从 {args.platform} 采集...")
    messages = collector.collect(args.channel, limit=args.limit)
    if not messages:
        print("未采集到消息。")
        return

    output = Path(args.output)
    collector.save_corpus(messages, output, channel_name=args.channel)
    print(f"已保存 {len(messages)} 条消息到 {output}")

    if args.json:
        json_path = output.with_suffix(".json")
        collector.save_json(messages, json_path)
        print(f"JSON 格式已保存到 {json_path}")


def cmd_import(args: argparse.Namespace) -> None:
    """导入本地文件。"""
    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        sys.exit(1)

    from collectors.manual import ManualCollector
    messages = ManualCollector.from_file(file_path)
    if not messages:
        print("未解析到内容。")
        return

    collector = ManualCollector()
    output = Path(args.output)
    collector.save_corpus(messages, output, channel_name=file_path.name)
    print(f"已导入 {len(messages)} 条内容到 {output}")


def cmd_init(args: argparse.Namespace) -> None:
    """初始化 skill 目录。"""
    from kit.manifest_tool import cmd_init as _init
    _init(args)


def cmd_stamp(args: argparse.Namespace) -> None:
    """封包登记。"""
    from kit.manifest_tool import cmd_stamp as _stamp
    _stamp(args)


def cmd_snapshot(args: argparse.Namespace) -> None:
    """创建快照。"""
    from kit.version_tool import cmd_snapshot as _snapshot
    _snapshot(args)


def cmd_rollback(args: argparse.Namespace) -> None:
    """回滚。"""
    from kit.version_tool import cmd_rollback as _rb
    _rb(args)


def cmd_list_snapshots(args: argparse.Namespace) -> None:
    """列出快照。"""
    from kit.version_tool import cmd_list as _list
    _list(args)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="immortal-skill 统一 CLI —— 数字永生蒸馏工具",
        epilog="详见 README.md 与 docs/PLATFORM-GUIDE.md",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # platforms
    p_plat = sub.add_parser("platforms", help="列出支持的数据平台")
    p_plat.set_defaults(func=cmd_platforms)

    # setup
    p_setup = sub.add_parser("setup", help="配置平台凭证")
    p_setup.add_argument("platform", choices=list(PLATFORM_MAP.keys()))
    p_setup.set_defaults(func=cmd_setup)

    # collect
    p_col = sub.add_parser("collect", help="采集数据")
    p_col.add_argument("--platform", required=True, choices=list(PLATFORM_MAP.keys()))
    p_col.add_argument("--channel", help="频道/会话 ID")
    p_col.add_argument("--scan", action="store_true", help="扫描可用频道")
    p_col.add_argument("--keyword", help="按名称筛选频道")
    p_col.add_argument("--limit", type=int, default=500, help="最大消息条数")
    p_col.add_argument("--output", default="corpus/collected.md", help="输出文件路径")
    p_col.add_argument("--json", action="store_true", help="同时输出 JSON 格式")
    p_col.add_argument("--db", help="本地数据库路径（微信/iMessage）")
    p_col.add_argument("--archive", help="归档目录路径（Twitter/社交媒体）")
    p_col.add_argument("--mbox", help="mbox 文件路径（Email）")
    p_col.add_argument("--token", help="API Token（Slack/Discord）")
    p_col.set_defaults(func=cmd_collect)

    # import
    p_imp = sub.add_parser("import", help="导入本地文件")
    p_imp.add_argument("file", help="文件路径（.txt/.md/.json/.csv）")
    p_imp.add_argument("--output", default="corpus/imported.md", help="输出路径")
    p_imp.set_defaults(func=cmd_import)

    # init
    p_init = sub.add_parser("init", help="初始化 skill 目录")
    p_init.add_argument("--slug", required=True)
    p_init.add_argument("--base", default="./skills/immortals")
    p_init.add_argument("--persona", default="self",
                        choices=["self", "colleague", "mentor", "family", "partner", "friend", "public-figure"])
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    # stamp
    p_stamp = sub.add_parser("stamp", help="封包登记")
    p_stamp.add_argument("--slug", required=True)
    p_stamp.add_argument("--base", default="./skills/immortals")
    p_stamp.add_argument("--sources", help="来源简述")
    p_stamp.add_argument("--note", help="备注")
    p_stamp.set_defaults(func=cmd_stamp)

    # snapshot
    p_snap = sub.add_parser("snapshot", help="创建快照")
    p_snap.add_argument("--slug", required=True)
    p_snap.add_argument("--base", default="./skills/immortals")
    p_snap.add_argument("--tag", help="快照名")
    p_snap.add_argument("--note", help="备注")
    p_snap.add_argument("--force", action="store_true")
    p_snap.set_defaults(func=cmd_snapshot)

    # rollback
    p_rb = sub.add_parser("rollback", help="回滚到指定快照")
    p_rb.add_argument("--slug", required=True)
    p_rb.add_argument("--tag", required=True)
    p_rb.add_argument("--base", default="./skills/immortals")
    p_rb.set_defaults(func=cmd_rollback)

    # list-snapshots
    p_ls = sub.add_parser("list-snapshots", help="列出所有快照")
    p_ls.add_argument("--slug", required=True)
    p_ls.add_argument("--base", default="./skills/immortals")
    p_ls.set_defaults(func=cmd_list_snapshots)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
