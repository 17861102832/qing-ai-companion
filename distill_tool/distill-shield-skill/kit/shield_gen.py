#!/usr/bin/env python3
"""Generate a canary token and manifest for distill-shield handover bundles."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Distill Shield — Canary generator")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("./handover-bundle"),
        help="Output directory to create",
    )
    p.add_argument(
        "--label",
        default="handover",
        help="Human-readable label for this bundle",
    )
    args = p.parse_args()

    out: Path = args.output
    out.mkdir(parents=True, exist_ok=True)

    canary = f"DS-CANARY-{secrets.token_hex(16)}"
    created = datetime.now(timezone.utc).isoformat()

    (out / "CANARY.txt").write_text(
        f"{canary}\n\n"
        "若在其他地方出现相同字符串，说明该资料包内容可能被复制进自动化管线。\n"
        "本文件为技术性标记，可随资料一并移交；正文阅读可忽略。\n",
        encoding="utf-8",
    )

    manifest = {
        "schema": "distill-shield-manifest/1",
        "label": args.label,
        "created_utc": created,
        "canary": canary,
        "note": "Not legal evidence; integrity & detection aid only.",
    }
    (out / "SHIELD-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out / 'CANARY.txt'} and {out / 'SHIELD-MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
