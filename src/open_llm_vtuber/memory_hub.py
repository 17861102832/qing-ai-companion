# -*- coding: utf-8 -*-
"""
MemoryHub —— 小青专属记忆中枢（借鉴万忆中枢「道/法/术」三层皮毛）

三层结构：
  道(dao)  : 长期偏好 / 铁律 / 哲学        —— 稳定，永不轻易变
  法(fa)   : 策略 / 操作规则 / 方法论       —— 中期
  术(shu)  : 具体事实 / 近期信息 / 观察记录  —— 短期

所有记忆持久化到项目根 memory_knowledge/*.json，
启动时由 service_context 渲染进 persona（让 AI 懂用户），
每轮对话后由 single_conversation 调用 sediment() 自动沉淀。

零外部依赖：不依赖 LLM / 向量库 / 网络，纯规则抽取 + JSON 持久化，
可离线、可审计、可 diff，贴合"全量自沉淀、越聊越懂你"的诉求。
"""
import os
import re
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from loguru import logger


# 层名 → (注册表键, 单条上限)
LAYER_SPECS = {
    "dao": ("principles", 50),
    "fa": ("strategies", 80),
    "shu": ("facts", 120),
    "story": ("narratives", 60),   # 叙事性记忆：人生转折/反复讲的故事/情感印记
}

# 规则抽取正则（零成本、稳定、可审计）
DAO_RX = re.compile(
    r"(我喜欢|我偏好|我始终|铁律|我的哲学|我的原则|必须记住|绝对不能|永远不要|"
    r"我只用|我从不用|我坚信|我的宗旨|我追求)",
    re.I,
)
FA_RX = re.compile(
    r"(务必|绝不|一定要|当.{0,10}就|策略是|规则是|先.{0,8}再|"
    r"步骤是|记住这个|每次都要|总要先|惯用|我一般)",
    re.I,
)
SHU_RX = re.compile(
    r"(今天我|我买了|我卖了|浮亏|浮盈|仓位|我在做|我用了|账户|参考|"
    r"场外基金|番茄|写作|止盈|止损|持有|定投|补仓|减仓)",
    re.I,
)

# 叙事性记忆：人生转折 / 反复讲的故事 / 情感印记（对标 immortal-skill 「记忆与经历」维度）
STORY_RX = re.compile(
    r"(我经历(?:过)?|当初|曾经|那时(?:候)?|当年|从前|后来我|"
    r"记得(?:有|那)?次|之前我|有一次|我(?:放弃|坚持|换过|搬过|离开|"
    r"改行|裸辞|转行)了|从那次之后|我(?:花了|用了|熬了|打了|坚持)\s*\d+\s*(?:年|个月|天)|"
    r"我们(?:经常|总|每次)(?:说|聊|讲)|你(?:总|一直|老是)说|我一直记得|"
    r"(?:这|那)是我(?:人生|最|第一次|唯一)的|我(?:出生|长大)在|为了(?:生活|理想|家人)|"
    r"那(?:年|时)我(?:刚|才|还)在)",
    re.I,
)


class MemoryHub:
    """道/法/术 三层持久化记忆中枢。"""

    def __init__(self, base_dir: str = "memory_knowledge"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        # 预加载三层，避免频繁读盘
        self._cache: dict = {name: self.load_layer(name) for name in LAYER_SPECS}

    def _path(self, name: str) -> str:
        return os.path.join(self.base_dir, f"{name}.json")

    def _default_layer(self, name: str) -> dict:
        registry_key = LAYER_SPECS[name][0]
        return {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "layers": name,
            registry_key: [],
        }

    def load_layer(self, name: str) -> dict:
        """读取一层记忆；不存在则返回默认空结构。"""
        p = self._path(name)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"读取记忆层 {name} 失败: {e}")
        return self._default_layer(name)

    def save_layer(self, name: str, data: dict) -> None:
        """写回一层记忆。"""
        data.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))
        try:
            with open(self._path(name), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._cache[name] = data
        except Exception as e:
            logger.error(f"写入记忆层 {name} 失败: {e}")

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()[:12]

    def _dedup(self, name: str, items: List[Dict], key_field: str, cap: int) -> List[Dict]:
        """按内容 hash 去重 + 语义包含合并 + 层上限裁剪。

        包含式去重：若两条片段互为包含（一条是另一条的子串），保留更长的一条，
        避免同一句话因多个关键词命中而产生多条近似/截断噪音（如「F了，习惯每周一...」）。
        """
        seen = set()
        result: List[Dict] = []
        for it in items:
            text = (it.get("text") or it.get("rule") or "").strip()
            if not text:
                continue
            h = self._hash(text)
            # 与已保留条目做包含式合并
            merged = False
            for idx, r in enumerate(result):
                rtext = (r.get("text") or r.get("rule") or "").strip()
                if len(text) >= 6 and len(rtext) >= 6 and (text in rtext or rtext in text):
                    if len(text) > len(rtext):
                        it["_hash"] = h
                        result[idx] = it
                    merged = True
                    break
            if merged:
                continue
            if h in seen:
                continue
            seen.add(h)
            it["_hash"] = h
            result.append(it)
        # 超过上限则丢弃最旧的
        if len(result) > cap:
            result = result[-cap:]
        return result

    def _add(self, name: str, entry: Dict) -> bool:
        """向某一层新增一条记忆（先去重）。返回是否真的新增。"""
        registry_key, cap = LAYER_SPECS[name]
        data = self._cache.get(name) or self.load_layer(name)
        items = data.setdefault(registry_key, [])
        h = self._hash(entry.get(registry_key[:-1], entry.get("text", entry.get("rule", ""))))
        if any(self._hash(it.get(registry_key[:-1], it.get("text", it.get("rule", "")))) == h for it in items):
            return False
        items = self._dedup(name, items + [entry], registry_key, cap)
        data[registry_key] = items
        self.save_layer(name, data)
        return True

    # ---------- 自动沉淀：规则抽取 ----------
    def sediment(self, user_text: str, assistant_text: str = "", conf_uid: Optional[str] = None) -> Dict[str, int]:
        """从一轮对话中抽取值得沉淀的偏好/规则/事实。

        Returns:
            dict: 实际新增条数，如 {"dao": 0, "fa": 1, "shu": 0}
        """
        now = datetime.now().isoformat(timespec="seconds")
        added = {"dao": 0, "fa": 0, "shu": 0, "story": 0}
        text = (user_text or "").strip()
        if not text:
            return added

        # 道：偏好 / 铁律 / 哲学
        for m in DAO_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if _is_meaningful(snippet):
                if self._add("dao", {"id": f"dao-{int(datetime.now().timestamp()*1000)}",
                                     "category": _category(snippet), "text": snippet,
                                     "source": "auto", "ts": now}):
                    added["dao"] += 1

        # 法：策略 / 操作规则
        for m in FA_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if _is_meaningful(snippet):
                if self._add("fa", {"id": f"fa-{int(datetime.now().timestamp()*1000)}",
                                    "category": _category(snippet), "rule": snippet,
                                    "ts": now}):
                    added["fa"] += 1

        # 术：具体事实 / 近期信息
        for m in SHU_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end())
            if _is_meaningful(snippet):
                if self._add("shu", {"id": f"shu-{int(datetime.now().timestamp()*1000)}",
                                     "text": snippet, "ts": now}):
                    added["shu"] += 1

        # 经历/故事：人生转折、反复讲的故事、情感印记（对标 immortal-skill 记忆维度）
        for m in STORY_RX.finditer(text):
            snippet = _excerpt(text, m.start(), m.end(), radius=34)
            if _is_meaningful(snippet):
                if self._add("story", {"id": f"story-{int(datetime.now().timestamp()*1000)}",
                                       "text": snippet, "ts": now}):
                    added["story"] += 1

        if any(added.values()):
            logger.info(f"记忆自动沉淀: {added}")

        # 记忆触达个人偏好档案（更新 user_profile.md 的简单同步）
        self._sync_user_profile()
        return added

    def _sync_user_profile(self) -> None:
        """把 dao 层追加到 user_profile.md 的「已验证的交易模式」区。"""
        try:
            dao_data = self._cache.get("dao") or self.load_layer("dao")
            principles = dao_data.get("principles", [])
            if not principles:
                return
            md_path = os.path.join(self.base_dir, "user_profile.md")
            if not os.path.isfile(md_path):
                return
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            marker = "## 已验证的交易模式（L3 原则层）"
            lines = [f"- {p['text']}" for p in principles if "text" in p]
            if marker in content and lines:
                block = marker + "\n\n" + "\n".join(lines) + "\n"
                if block not in content:
                    content = content.split(marker)[0] + block
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(content)
        except Exception as e:
            logger.debug(f"同步 user_profile.md 失败(非阻塞): {e}")

    # ---------- 渲染进 persona ----------
    def render_for_prompt(self) -> str:
        """把四层记忆渲染成紧凑的 persona 块，供 system prompt 注入。"""
        parts = ["", "[你的专属记忆：以下是你对用户的长期理解，请融入你的回答]"]
        layer_order = ("dao", "fa", "shu", "story")
        labels = {
            "dao": "长期偏好/铁律",
            "fa": "策略/规则",
            "shu": "近期事实",
            "story": "经历/故事",
        }
        for name in layer_order:
            data = self._cache.get(name) or self.load_layer(name)
            registry_key = LAYER_SPECS[name][0]
            items = data.get(registry_key, [])
            if not items:
                continue
            parts.append(f"【{labels[name]}】")
            for it in items[-8:]:  # 每层最多渲染最近8条，避免 persona 过长
                content = it.get("text") or it.get("rule") or ""
                if content:
                    parts.append(f"- {content}")
        return "\n".join(parts)

    def counts(self) -> dict:
        """返回各层记忆条数（用于审计/日志）。"""
        out = {}
        for name in LAYER_SPECS:
            data = self._cache.get(name) or self.load_layer(name)
            out[name] = len(data.get(LAYER_SPECS[name][0], []))
        return out


# ---------- 辅助函数 ----------
def _excerpt(text: str, start: int, end: int, radius: int = 24) -> str:
    """以命中点为中心截取一小段，确保是完整语义。"""
    low = max(0, start - radius)
    high = min(len(text), end + radius)
    # 在边界处尽量找标点/逗号作为句边界
    s = text[low:high].strip("，。；！？、,.!?; ")
    return s[:90] if s else ""

def _is_meaningful(snippet: str) -> bool:
    return snippet is not None and len(snippet) >= 4

def _category(snippet: str) -> str:
    for kw, cat in (("基金", "交易"), ("期权", "交易"), ("仓位", "交易"),
                    ("止盈", "交易"), ("止损", "交易"), ("买", "交易"), ("卖", "交易"),
                    ("写", "创作"), ("小说", "创作"), ("番茄", "创作"), ("爽文", "创作"),
                    ("AI", "创作"), ("文案", "创作")):
        if kw in snippet:
            return cat
    return "综合"
