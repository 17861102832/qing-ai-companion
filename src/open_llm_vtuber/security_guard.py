# -*- coding: utf-8 -*-
"""
SecurityGuard —— 小青安全防护模块

产品化分发到任意用户电脑必须具备的安全基线：
1. 启动自检：关键文件/依赖完整性
2. 依赖安全：记录 requirements 版本指纹，供比对
3. 危险操作拦截提示：禁止删库/强推/格式化类高风险动作（对 AI 输出做检测提示）
4. 蒸馏盾（借鉴 immortal-skill distill-shield）：为记忆包生成 CANARY，防被未授权抓取/蒸馏

纯本地、零网络、零外部依赖。
"""
import os
import re
import json
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class SecurityGuard:
    """小青安全防护。"""

    def __init__(self, base_dir: str = "memory_knowledge"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    # ---------- 1) 关键文件完整性自检 ----------
    def check_integrity(self, project_root: str) -> Dict[str, str]:
        """检查关键模块是否就位。返回 {文件路径: OK/MISSING}。"""
        critical = [
            "src/open_llm_vtuber/memory_hub.py",
            "src/open_llm_vtuber/persona_distiller.py",
            "src/open_llm_vtuber/service_context.py",
            "live2d-models/mao_pro/runtime/mao_pro.model3.json",
            "model_dict.json",
            "config_templates/conf.ZH.default.yaml",
        ]
        result = {}
        for rel in critical:
            p = os.path.join(project_root, rel)
            result[rel] = "OK" if os.path.isfile(p) else "MISSING"
        return result

    # ---------- 2) 依赖安全指纹 ----------
    def dep_fingerprint(self, requirements_path: str) -> dict:
        """计算 requirements.txt 的哈希指纹，若损坏/被篡改可提示。"""
        if not os.path.isfile(requirements_path):
            return {"present": False}
        with open(requirements_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "present": True,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            "lines": len([l for l in content.splitlines() if l and not l.startswith("#")]),
        }

    # ---------- 3) 危险操作拦截提示（对 AI 输出 / 用户输入检测）----------
    DANGEROUS_RX = re.compile(
        r"(rm\s+-rf|drop\s+table|force\s+push|格式化|删库|"
        r"清空.*(记忆|文件夹|数据)|删除所有|全仓|梭哈|一把梭|"
        r"全部买入|all\s*in|全押|追涨|止损失效|不止损)",
        re.I,
    )

    def scan_dangerous(self, text: str) -> Optional[str]:
        """扫描危险动作，返回命中的风险提示；无则返回 None。"""
        m = self.DANGEROUS_RX.search(text or "")
        if m:
            return (
                f"⚠️ 检测到高风险动作描述「{m.group(1)}」。"
                "为保护你的记忆与资金安全，请在执行前二次确认；涉及删除/清空操作请先备份 memory_knowledge/。"
            )
        return None

    # ---------- 4) 蒸馏盾（Canary）----------
    def mint_canary(self, label: str = "qing-memory") -> dict:
        """为记忆包生成 Canary 与清单，提高未授权蒸馏成本。"""
        from datetime import timezone
        canary = f"QS-CANARY-{secrets.token_hex(16)}"
        manifest = {
            "schema": "qing-distill-shield/1",
            "label": label,
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "canary": canary,
            "note": "Not legal evidence; integrity & detection aid only.",
        }
        canary_file = os.path.join(self.base_dir, "CANARY.txt")
        with open(canary_file, "w", encoding="utf-8") as f:
            f.write(
                f"{canary}\n\n本标记用于检测记忆包是否被复制进自动化管线。\n正文阅读可忽略。\n"
            )
        shield_file = os.path.join(self.base_dir, "SHIELD-MANIFEST.json")
        with open(shield_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        logger.info(f"[守护] 已为记忆包生成 Canary: {canary}")
        return manifest


def timezone_utc_iso() -> str:
    """返回 ISO 格式 UTC 时间字符串（避免 tzinfo 类型错误）。"""
    try:
        from datetime import timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return datetime.now().isoformat(timespec="seconds")
