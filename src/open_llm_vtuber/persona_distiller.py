# -*- coding: utf-8 -*-
"""
PersonaDistiller —— 用户人格蒸馏器（融合 immortal-skill 的「性格四维提取」机制）

借鉴 immortal-skill 的 personality-extractor 设计原则：
- 行为证据优先于标签判定（记录「做了什么」而非「是什么人」）
- 禁止心理学诊断标签（不输 INTJ/回避型 等）
- 允许记录矛盾面
- 证据分级：verbatim(原话) / artifact(行为客观推断) / impression(主观印象)
- 跨时间变化标注

职责：
1. 从对话中提取用户的核心价值观 / 口头禅 / 情绪模式 / 社交偏好 / 兴趣审美 / 自我认知
2. 蒸馏结果持久化到 persona.json（人格画像）+ 写入 memory_hub 的道/法/术三层
3. 渲染成 persona 块注入 system prompt（让小青更像用户、更懂用户）

纯本地、零外部依赖、零 LLM 成本（规则抽取），离线可审计。
"""
import os
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


# 证据分级
VERBATIM = "verbatim"
ARTIFACT = "artifact"
IMPRESSION = "impression"

# 模糊匹配：行为证据优先，抓取「我在/我习惯/我经常/我喜欢/我总觉得/我讨厌...」这类自述
SELF_STATEMENT_RX = re.compile(
    r"(我(?:觉得|认为|喜欢|讨厌|习惯|经常|总是|从不|坚持|追求|"
    r"在乎|看重|希望|想要|害怕|最看重|最讨厌|始终)|技术分析是术|"
    r"信息差|人性|舆论)[^\n]{4,120}",
    re.I,
)

# 口头禅 / 高频语气词
PET_PHRASE_RX = re.compile(
    r"(兄弟|妈的|卧槽|我靠|确实|绝了|牛逼|无语|哈哈哈|呃|嗯嗯|真的假的|说实话|讲真|说白了)",
    re.I,
)

# 价值观信号词
VALUE_RX = re.compile(
    r"(技术分析是术|信息差|人性|舆论|道|极致收益率|复利|长期|纪律|"
    r"不追热点|场外基金|自信|克制|专注|价值|共赢|尊重)",
    re.I,
)

# 社交偏好
SOCIAL_RX = re.compile(
    r"(我偏向|我在群里|我习惯一个人|我更喜欢(?:独处|安静)|我不爱(?:社交|热闹)|"
    r"我主动|我被动|我倾向于|我跟人(?:相处|打交道)|我朋友(?:少|多)|"
    r"我(?:性格|比较)(?:外向|内向)|我更喜欢(?:一对一|小圈子)|"
    r"我不喜欢(?:多人|热闹|应酬)|我(?:社交|聊天)频率)",
    re.I,
)

# 自我认知 vs 他人印象
SELF_IMAGE_RX = re.compile(
    r"(我这个人|我认为我(?:是|自己)|我觉得我(?:是|自己)|我其实是|我性格(?:是)?|"
    r"(?:别人|大家|他(?:们)?)(?:都)?(?:觉得|说|认为|评价)我|"
    r"我不是(?:那种|一个)|我更像|我骨子里|我本质上|"
    r"(?:他们|别人)眼里的我|我的(?:标签|标签是|人设)|"
    r"我(?:给|给人的)(?:感觉|印象))",
    re.I,
)


class PersonaDistiller:
    """用户人格蒸馏器。"""

    def __init__(self, base_dir: str = "memory_knowledge"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.persona_path = os.path.join(base_dir, "persona.json")
        self.persona = self._load_persona()

    def _load_persona(self) -> dict:
        if os.path.isfile(self.persona_path):
            try:
                with open(self.persona_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "schema": "persona/1",
            "updated_at": None,
            "version": 1,
            "core_values": [],      # 核心价值观
            "catchphrases": [],     # 口头禅/表达习惯
            "emotion_patterns": [], # 情绪模式
            "social_prefs": [],     # 社交偏好
            "interests": [],        # 兴趣与审美
            "self_vs_image": [],    # 自我认知 vs 他人印象
            "evidence_count": {"verbatim": 0, "artifact": 0, "impression": 0},
        }

    def _save(self):
        self.persona["updated_at"] = datetime.now().isoformat(timespec="seconds")
        with open(self.persona_path, "w", encoding="utf-8") as f:
            json.dump(self.persona, f, ensure_ascii=False, indent=2)

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()[:10]

    def _push_unique(self, key: str, item: dict, max_n: int = 30) -> bool:
        """去重后加入专属维度。语义去重：去掉句首称呼前缀后判包含，互为包含视为重复。"""

        def _norm(s: str) -> str:
            s = s.strip()
            # 去掉句首称呼/语气前缀，归一化后再判重
            for pref in ("兄弟，", "兄弟,", "兄弟", "弟，", "弟", "妈的", "卧槽"):
                if s.startswith(pref):
                    s = s[len(pref):].lstrip("，, ")
                    break
            return s

        text = item.get("text", "").strip()
        if not text:
            return False
        h = self._hash(_norm(text))
        for existing in self.persona[key]:
            e_text = existing.get("text", "").strip()
            if not e_text:
                continue
            e_norm = _norm(e_text)
            if self._hash(e_norm) == h:
                return False
            if len(e_norm) >= 4 and len(_norm(text)) >= 4:
                if _norm(text) in e_norm or e_norm in _norm(text):
                    if len(text) > len(e_text):
                        existing["text"] = text
                        existing["evidence"] = item.get("evidence", ARTIFACT)
                        existing["ts"] = item.get("ts", existing.get("ts"))
                        self._save()
                    return False
        self.persona[key].append(item)
        if len(self.persona[key]) > max_n:
            self.persona[key] = self.persona[key][-max_n:]
        ev = item.get("evidence", ARTIFACT)
        self.persona["evidence_count"][ev] = self.persona["evidence_count"].get(ev, 0) + 1
        return True

    def distill(self, user_text: str) -> Dict[str, int]:
        """从一条用户消息中蒸馏人格特征。返回新增计数。"""
        text = (user_text or "").strip()
        if not text:
            return {"values": 0, "catchphrases": 0, "emotions": 0, "social": 0, "interests": 0, "self": 0}
        added = {"values": 0, "catchphrases": 0, "emotions": 0, "social": 0, "interests": 0, "self": 0}

        # 1) 核心价值观（行为证据→自述）
        for m in VALUE_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if len(snippet) >= 4 and self._push_unique("core_values", {
                "text": snippet, "evidence": ARTIFACT,
                "evidence_note": "用户自述/高频强调的价值观",
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["values"] += 1

        # 2) 自述性句子 → 兴趣/偏好/核心价值观
        # 取重叠区间中最长的匹配（避免同一句因正则多重起点产生近似重复）
        self_matches = sorted(SELF_STATEMENT_RX.finditer(text), key=lambda m: m.start())
        kept: List[re.Match] = []
        for m in self_matches:
            if kept and m.start() < kept[-1].end():
                if m.end() - m.start() > kept[-1].end() - kept[-1].start():
                    kept[-1] = m
                continue
            kept.append(m)
        for m in kept:
            snippet = _excerpt(text, m.start(), m.end())
            if len(snippet) < 4:
                continue
            target = "interests" if re.search(r"(喜欢|感兴趣|爱|喜欢研究|常逛|收藏)", snippet) else "core_values"
            if self._push_unique(target, {
                "text": snippet, "evidence": VERBATIM,
                "evidence_note": "用户原话/自述",
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["values" if target == "core_values" else "interests"] += 1

        # 3) 口头禅
        for m in PET_PHRASE_RX.finditer(text):
            if self._push_unique("catchphrases", {
                "text": m.group(1), "evidence": VERBATIM,
                "evidence_note": "高频语气词/口头禅",
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["catchphrases"] += 1

        # 4) 情绪信号 → 情绪模式
        if re.search(r"(生气|愤怒|气死|烦|讨厌|毛了|火大)", text):
            if self._push_unique("emotion_patterns", {
                "text": "触发因素包含愤怒/不满类词", "evidence": ARTIFACT,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["emotions"] += 1
        if re.search(r"(开心|高兴|爽|哈哈|笑死|太好了|舒服)", text):
            if self._push_unique("emotion_patterns", {
                "text": "触发因素包含愉悦/兴奋类词", "evidence": ARTIFACT,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["emotions"] += 1

        # 5) 社交偏好
        for m in SOCIAL_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if len(snippet) >= 4 and self._push_unique("social_prefs", {
                "text": snippet, "evidence": ARTIFACT,
                "evidence_note": "用户自述/高频强调的社交偏好",
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["social"] += 1

        # 6) 自我认知 vs 他人印象
        for m in SELF_IMAGE_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if len(snippet) >= 4 and self._push_unique("self_vs_image", {
                "text": snippet, "evidence": VERBATIM,
                "evidence_note": "用户对自我的描述/他人对用户的评价",
                "ts": datetime.now().isoformat(timespec="seconds"),
            }):
                added["self"] += 1

        if any(added.values()):
            self._save()
            logger.info(f"人格蒸馏新增: {added}")
        return added

    def render_for_prompt(self) -> str:
        """把 6 维人格画像渲染成 persona 块，供 system prompt 注入。"""
        p = self.persona
        parts = ["", "[你对用户的深度人格理解（蒸馏自历史对话，请据此贴近TA）]"]
        dims = [
            ("core_values", "核心价值观"),
            ("catchphrases", "口头禅"),
            ("emotion_patterns", "情绪模式"),
            ("social_prefs", "社交偏好"),
            ("interests", "兴趣审美"),
            ("self_vs_image", "自我认知/他人印象"),
        ]
        for key, label in dims:
            items = p.get(key, [])
            if items:
                parts.append(f"【{label}】")
                parts += [f"- {i['text']}" for i in items[-6:]]
        return "\n".join(parts)


def _excerpt(text: str, start: int, end: int, radius: int = 30) -> str:
    low = max(0, start - radius)
    high = min(len(text), end + radius)
    s = text[low:high].strip("，。；！？、,.!?; ")
    return s[:120] if s else ""
