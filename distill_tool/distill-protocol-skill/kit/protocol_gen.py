#!/usr/bin/env python3
"""Generate LICENSE-DISTILL.md and manifest.json for distill-protocol."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TIERS = {
    "human_only": (
        "本资料包**仅允许人类阅读**。禁止用于任何机器学习模型的训练、微调或蒸馏；"
        "禁止用于生成自动化人格副本或冒充他人。"
    ),
    "no_commercial_distill": (
        "允许个人非商业场景下学习与参考；**禁止**将基于本资料包蒸馏出的数字分身"
        "用于商业用途或对外提供付费服务（除非另有书面授权）。"
    ),
    "research_ok": (
        "允许学术与独立研究者在非商业前提下引用与复现；**禁止**商用；须署名来源。"
    ),
}


def main() -> int:
    p = argparse.ArgumentParser(description="Distill Protocol generator")
    p.add_argument("--owner", required=True, help="Owner display name")
    p.add_argument(
        "--tier",
        choices=list(TIERS.keys()),
        default="human_only",
        help="Policy tier",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("./protocol-bundle"),
        help="Output directory",
    )
    args = p.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    created = datetime.now(timezone.utc).isoformat()
    schema = "distill-protocol-manifest/1"

    body = TIERS[args.tier]

    md = f"""# 蒸馏协议 · Distill Protocol

**所有者**：{args.owner}
**档位**：{args.tier}
**生成时间（UTC）**：{created}
**schema**：{schema}

> **不是法律意见**；争议解决取决于适用法律与合同约定。
> 中文圈戏称「牛马保护法」仅为梗，**不具立法效力**。

## 许可范围

{body}

## 机器可读

同目录 `manifest.json` 为结构化声明，便于工具解析。
"""

    (out / "LICENSE-DISTILL.md").write_text(md, encoding="utf-8")

    manifest = {
        "schema": schema,
        "owner": args.owner,
        "tier": args.tier,
        "created_utc": created,
        "allow_distillation": args.tier != "human_only",
        "allow_training": args.tier != "human_only",
        "commercial": False,
        "attribution_required": True,
        "nickname_cn": "牛马保护法",
        "disclaimer": "Not legal advice; for signaling and documentation only.",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out / 'LICENSE-DISTILL.md'} and {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
