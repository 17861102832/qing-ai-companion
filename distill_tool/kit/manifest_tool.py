#!/usr/bin/env python3
"""轻量脚手架：为蒸馏产物建目录、写 manifest、计算文件指纹。

支持多角色模板，按角色类型生成不同的文件骨架。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

PERSONA_FILES = {
    "self": ("procedure.md", "interaction.md", "memory.md", "personality.md", "conflicts.md"),
    "colleague": ("procedure.md", "interaction.md", "conflicts.md"),
    "mentor": ("procedure.md", "interaction.md", "memory.md", "personality.md", "conflicts.md"),
    "family": ("interaction.md", "memory.md", "personality.md", "conflicts.md"),
    "partner": ("interaction.md", "memory.md", "personality.md", "conflicts.md"),
    "friend": ("interaction.md", "memory.md", "personality.md", "conflicts.md"),
    "public-figure": ("procedure.md", "interaction.md", "memory.md", "personality.md", "conflicts.md"),
}

FILE_HINTS = {
    "procedure.md": "# 程序性知识\n\n（待填充）\n",
    "interaction.md": "# 互动与态度\n\n（待填充）\n",
    "memory.md": "# 记忆与经历\n\n（待填充）\n",
    "personality.md": "# 性格与价值观\n\n（待填充）\n",
    "conflicts.md": "# 待决冲突\n\n（暂无；合并阶段由代理填写。）\n",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_slug(slug: str) -> None:
    if not SLUG_PATTERN.fullmatch(slug):
        print(
            "错误：slug 须为小写字母、数字与连字符，且不得以连字符开头或结尾。",
            file=sys.stderr,
        )
        sys.exit(2)


def cmd_init(args: argparse.Namespace) -> None:
    base = Path(args.base).expanduser().resolve()
    slug = args.slug
    validate_slug(slug)
    persona = args.persona or "self"
    root = base / slug

    if root.exists() and not args.force:
        print(f"错误：{root} 已存在。若需覆盖请加 --force", file=sys.stderr)
        sys.exit(1)

    root.mkdir(parents=True, exist_ok=True)

    files = PERSONA_FILES.get(persona, PERSONA_FILES["self"])
    for name in files:
        p = root / name
        if args.force or not p.exists():
            p.write_text(FILE_HINTS.get(name, f"# {name}\n"), encoding="utf-8")

    dimensions = [f.replace(".md", "") for f in files if f != "conflicts.md"]
    manifest = {
        "slug": slug,
        "persona": persona,
        "built_at": None,
        "sources_summarized": [],
        "platforms": [],
        "kit": "immortal-skill",
        "dimensions": dimensions,
        "fingerprints": {},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已初始化：{root}（角色：{persona}，维度：{', '.join(dimensions)}）")


def cmd_stamp(args: argparse.Namespace) -> None:
    base = Path(args.base).expanduser().resolve()
    slug = args.slug
    validate_slug(slug)
    root = base / slug

    if not root.is_dir():
        print(f"错误：找不到 {root}", file=sys.stderr)
        sys.exit(1)

    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        print("错误：缺少 manifest.json，请先 init", file=sys.stderr)
        sys.exit(1)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["built_at"] = utc_now_iso()
    if args.sources:
        data["sources_summarized"] = [s.strip() for s in args.sources.split(",") if s.strip()]
    if args.note:
        data["note"] = args.note

    fps: dict[str, str] = {}
    for f in root.iterdir():
        if f.suffix in (".md", ".json") and f.name != "manifest.json":
            fps[f.name] = file_sha256(f)
    data["fingerprints"] = fps

    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已更新 manifest：{manifest_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="immortal-skill 目录与 manifest 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="创建 <slug>/ 骨架")
    p_init.add_argument("--slug", required=True)
    p_init.add_argument("--base", default="./skills/immortals", help="生成根目录")
    p_init.add_argument("--persona", default="self", choices=list(PERSONA_FILES.keys()))
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_stamp = sub.add_parser("stamp", help="写入 built_at、指纹与来源")
    p_stamp.add_argument("--slug", required=True)
    p_stamp.add_argument("--base", default="./skills/immortals")
    p_stamp.add_argument("--sources", help="逗号分隔的来源简述")
    p_stamp.add_argument("--note", help="任意备注")
    p_stamp.set_defaults(func=cmd_stamp)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
