#!/usr/bin/env python3
"""版本管理：快照、回滚、列表、清理。

支持多维度文件跟踪，自动检测角色类型。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ALL_TRACKED = ("SKILL.md", "procedure.md", "interaction.md", "memory.md", "personality.md", "conflicts.md")
MAX_SNAPSHOTS = 20


def utc_now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _snapshots_dir(skill_dir: Path) -> Path:
    return skill_dir / ".snapshots"


def _read_manifest(skill_dir: Path) -> dict:
    p = skill_dir / "manifest.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _write_manifest(skill_dir: Path, data: dict) -> None:
    p = skill_dir / "manifest.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tracked_files(skill_dir: Path) -> tuple[str, ...]:
    return tuple(name for name in ALL_TRACKED if (skill_dir / name).is_file())


def cmd_snapshot(args: argparse.Namespace) -> None:
    skill_dir = Path(args.base).expanduser().resolve() / args.slug
    if not skill_dir.is_dir():
        print(f"错误：{skill_dir} 不存在", file=sys.stderr)
        sys.exit(1)

    tag = args.tag or utc_now_tag()
    snap_dir = _snapshots_dir(skill_dir) / tag
    if snap_dir.exists() and not args.force:
        print(f"错误：快照 {tag} 已存在。加 --force 覆盖", file=sys.stderr)
        sys.exit(1)

    snap_dir.mkdir(parents=True, exist_ok=True)
    tracked = _tracked_files(skill_dir)
    copied = []
    for name in tracked:
        src = skill_dir / name
        shutil.copy2(src, snap_dir / name)
        copied.append(name)

    meta = {
        "tag": tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": copied,
        "note": args.note or "",
    }
    (snap_dir / "_snapshot.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = _read_manifest(skill_dir)
    manifest["latest_snapshot"] = tag
    _write_manifest(skill_dir, manifest)
    print(f"快照已保存：{snap_dir}（{len(copied)} 个文件）")


def cmd_rollback(args: argparse.Namespace) -> None:
    skill_dir = Path(args.base).expanduser().resolve() / args.slug
    target_dir = _snapshots_dir(skill_dir) / args.tag

    if not target_dir.is_dir():
        print(f"错误：快照 {args.tag} 不存在", file=sys.stderr)
        sys.exit(1)

    safety_tag = f"pre-rollback-{utc_now_tag()}"
    safety_dir = _snapshots_dir(skill_dir) / safety_tag
    safety_dir.mkdir(parents=True, exist_ok=True)
    tracked = _tracked_files(skill_dir)
    for name in tracked:
        src = skill_dir / name
        if src.is_file():
            shutil.copy2(src, safety_dir / name)
    safety_meta = {
        "tag": safety_tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": list(tracked),
        "note": f"auto-saved before rollback to {args.tag}",
    }
    (safety_dir / "_snapshot.json").write_text(
        json.dumps(safety_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    restored = []
    for name in ALL_TRACKED:
        src = target_dir / name
        if src.is_file():
            shutil.copy2(src, skill_dir / name)
            restored.append(name)

    manifest = _read_manifest(skill_dir)
    manifest["latest_snapshot"] = safety_tag
    manifest["rolled_back_to"] = args.tag
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(skill_dir, manifest)

    print(f"已回滚到 {args.tag}（恢复 {len(restored)} 个文件）")
    print(f"回滚前状态已保存至 {safety_tag}")


def cmd_list(args: argparse.Namespace) -> None:
    skill_dir = Path(args.base).expanduser().resolve() / args.slug
    snaps_root = _snapshots_dir(skill_dir)

    if not snaps_root.is_dir():
        print("暂无快照")
        return

    entries = []
    for d in sorted(snaps_root.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "_snapshot.json"
        if meta_file.is_file():
            entries.append(json.loads(meta_file.read_text(encoding="utf-8")))
        else:
            entries.append({"tag": d.name, "created_at": "?", "files": [], "note": ""})

    if not entries:
        print("暂无快照")
        return

    print(f"共 {len(entries)} 个快照：\n")
    for e in entries:
        note_str = f"  备注: {e['note']}" if e.get("note") else ""
        print(f"  [{e['tag']}]  {e.get('created_at', '?')}  文件: {', '.join(e.get('files', []))}{note_str}")


def cmd_clean(args: argparse.Namespace) -> None:
    skill_dir = Path(args.base).expanduser().resolve() / args.slug
    snaps_root = _snapshots_dir(skill_dir)
    if not snaps_root.is_dir():
        return

    dirs = sorted(
        [d for d in snaps_root.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
    )
    keep = args.keep or MAX_SNAPSHOTS
    to_remove = dirs[:-keep] if len(dirs) > keep else []

    for old in to_remove:
        shutil.rmtree(old)
        print(f"已删除旧快照：{old.name}")

    if not to_remove:
        print(f"快照数 ({len(dirs)}) 未超过上限 ({keep})，无需清理")


def main() -> None:
    ap = argparse.ArgumentParser(description="immortal-skill 版本管理工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="保存当前状态为快照")
    p_snap.add_argument("--slug", required=True)
    p_snap.add_argument("--base", default="./skills/immortals")
    p_snap.add_argument("--tag", help="自定义快照名")
    p_snap.add_argument("--note", help="备注")
    p_snap.add_argument("--force", action="store_true")
    p_snap.set_defaults(func=cmd_snapshot)

    p_rb = sub.add_parser("rollback", help="回滚到指定快照")
    p_rb.add_argument("--slug", required=True)
    p_rb.add_argument("--tag", required=True)
    p_rb.add_argument("--base", default="./skills/immortals")
    p_rb.set_defaults(func=cmd_rollback)

    p_ls = sub.add_parser("list", help="列出所有快照")
    p_ls.add_argument("--slug", required=True)
    p_ls.add_argument("--base", default="./skills/immortals")
    p_ls.set_defaults(func=cmd_list)

    p_cl = sub.add_parser("clean", help="清理旧快照")
    p_cl.add_argument("--slug", required=True)
    p_cl.add_argument("--base", default="./skills/immortals")
    p_cl.add_argument("--keep", type=int, default=MAX_SNAPSHOTS)
    p_cl.set_defaults(func=cmd_clean)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
