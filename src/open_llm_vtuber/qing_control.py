# -*- coding: utf-8 -*-
"""
QingControl —— 小青「一键蒸馏 + 人格设定 + 记忆 + 隐私」控制面板后端

给前端浮层控制面板提供的 REST 接口：
  GET  /qing/status            → 记忆目录、各层条数、可用人格预设、当前人格
  GET  /qing/persona           → 当前 6 维人格卡 + 记忆概览
  POST /qing/persona/apply     → 应用某个预置人格（MBTI 反差人格），实时生效
  POST /qing/distill           → 一键蒸馏：把已沉淀记忆/历史整合成更丰富的人格卡
  POST /qing/reset             → 隐私清空：移除用户个人信息，恢复干净默认档案

纯本地、零外部依赖，接口不写入任何密钥，安全。
"""
import os
import json
import glob
import shutil
from datetime import datetime
from fastapi import APIRouter
from starlette.responses import JSONResponse
from loguru import logger
from .service_context import ServiceContext
from .config_manager import read_yaml

# 隐私清空后的「干净默认」记忆/人格档案（不包含任何真实用户信息）
CLEAN_DAO = [
    {"id": "dao-gen", "category": "综合", "text": "用户尚未表达长期偏好，正在相处中", "source": "system", "ts": "2026-08-22T00:00:00"},
]
CLEAN_FA = [
    {"id": "fa-gen", "rule": "默认使用简洁、接地气、有温度的中文陪伴", "source": "system", "ts": "2026-08-22T00:00:00"},
]
CLEAN_SHU = [
    {"id": "shu-gen", "text": "已开始与用户建立新一段交流", "source": "system", "ts": "2026-08-22T00:00:00"},
]
CLEAN_PERSONA = {
    "schema": "persona/1",
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "version": 1,
    "core_values": [], "catchphrases": [], "emotion_patterns": [],
    "social_prefs": [], "interests": [], "self_vs_image": [],
    "evidence_count": {"verbatim": 0, "artifact": 0, "impression": 0},
}

# 明显非用户语句 / Markdown 元信息，不应被喂进人格蒸馏
_META_MARKERS = (
    "决策哲学", "借鉴", "以下是", "用户画像", "用户档案", "道/法/术", "铁律", "护栏",
    "##", "###", "> ", "**", "对话本质", "目标：", "已开始与用户", "尚未建立", "注意：",
    "人格理解", "深度人格", "核心价值", "口头禅", "兴趣审美", "社交偏好",
)


def _is_meta(t: str) -> bool:
    return any(m in t for m in _META_MARKERS)


def init_qing_control_routes(ctx: ServiceContext) -> APIRouter:
    router = APIRouter()

    def _mem_dir() -> str:
        try:
            return ctx._project_root_memory_dir()
        except Exception as e:
            logger.error(f"记忆目录获取失败: {e}")
            return "memory_knowledge"

    def _persona() -> dict:
        try:
            if hasattr(ctx, "persona_distiller") and ctx.persona_distiller:
                return ctx.persona_distiller.persona
        except Exception as e:
            logger.error(f"读取人格失败: {e}")
        return CLEAN_PERSONA.copy()

    def _presets() -> list:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chars_dir = os.path.join(project_root, "characters")
        out = [{"name": "默认小青（无预设）", "uid": "default", "desc": "恢复默认小青人格"}]
        for y in sorted(glob.glob(os.path.join(chars_dir, "*.yaml"))):
            try:
                data = read_yaml(y)
                cc = data.get("character_config", {}) if isinstance(data, dict) else {}
                uid = cc.get("conf_uid", "")
                # 只展示 MBTI 反差预设备（其余开发者预设备不下发）
                if not uid.startswith("mbti_"):
                    continue
                name = cc.get("conf_name", os.path.basename(y)[:-5])
                prompt = cc.get("persona_prompt", "")
                lines = [l.strip() for l in prompt.splitlines() if l.strip()]
                desc = lines[1][:60] if len(lines) > 1 else ""
                out.append({"name": name, "uid": uid, "desc": desc})
            except Exception as e:
                logger.debug(f"跳过人格预设 {y}: {e}")
        return out

    def _disk_counts() -> dict:
        """直接从磁盘统计各层条数（避免用进程内可能过期的缓存）。"""
        mem_dir = _mem_dir()
        out = {"dao": 0, "fa": 0, "shu": 0, "story": 0}
        for layer, key in (("dao", "principles"), ("fa", "strategies"), ("shu", "facts"), ("story", "narratives")):
            p = os.path.join(mem_dir, f"{layer}.json")
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    out[layer] = len(data.get(key, []))
                except Exception:
                    pass
        return out

    @router.get("/qing/status")
    async def qing_status():
        mem_dir = _mem_dir()
        counts = _disk_counts()
        active = None
        try:
            active = ctx._load_active_persona()
        except Exception:
            active = None
        has_key = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()) and \
            not os.environ.get("DEEPSEEK_API_KEY", "").strip().lower().startswith("sk-please")
        return JSONResponse({
            "mem_dir": os.path.basename(mem_dir) or "memory_knowledge",
            "counts": counts,
            "presets": _presets(),
            "active_persona": (active.get("name") if active else None),
            "has_api_key": has_key,
        })

    @router.get("/qing/persona")
    async def qing_persona():
        return JSONResponse({"persona": _persona(), "counts": _disk_counts()})

    @router.post("/qing/persona/apply")
    async def qing_apply(payload: dict):
        name = (payload or {}).get("name", "")
        if not name:
            return JSONResponse({"ok": False, "error": "缺少 name"}, status_code=400)
        try:
            res = ctx.apply_persona(name)
            # 应用后刷新 system prompt，使新人格实时生效
            try:
                if hasattr(ctx, "refresh_system_prompt"):
                    await ctx.refresh_system_prompt()
            except Exception as e:
                logger.debug(f"刷新系统提示失败(非阻塞): {e}")
            return JSONResponse({"ok": True, **res})
        except Exception as e:
            logger.error(f"应用人格失败: {e}")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    @router.post("/qing/distill")
    async def qing_distill():
        """一键蒸馏：把已沉淀到各层的「干净用户语句」再喂一遍给人格蒸馏器，
        让 6 维人格卡更完整。纯规则、去重、零成本。

        注意：只喂记忆层的 text/rule（这些是真实用户句子），
        跳过 source==system 的元信息条目，也不读 user_profile.md（避免 Markdown 污染人格）。
        """
        added_total = {"values": 0, "catchphrases": 0, "emotions": 0, "social": 0, "interests": 0, "self": 0}
        mem_dir = _mem_dir()
        collected = []
        for layer, key in (("dao", "principles"), ("fa", "strategies"), ("shu", "facts"), ("story", "narratives")):
            path = os.path.join(mem_dir, f"{layer}.json")
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for it in data.get(key, []):
                        t = (it.get("text") or it.get("rule") or "").strip()
                        if not t:
                            continue
                        # 跳过系统级元信息（source==system 或明显非用户语句）
                        if it.get("source") == "system":
                            continue
                        if _is_meta(t):
                            continue
                        collected.append(t)
                except Exception:
                    continue
        if hasattr(ctx, "persona_distiller") and ctx.persona_distiller:
            for t in collected:
                try:
                    added = ctx.persona_distiller.distill(t)
                    for k, v in added.items():
                        added_total[k] = added_total.get(k, 0) + v
                except Exception:
                    continue
        return JSONResponse({"ok": True, "added": added_total, "persona": _persona(), "fed_count": len(collected)})

    # 常见模型清单（vision=True 表示支持图像理解的视觉/多模态模型）
    # 说明：DeepSeek-V4-Flash / V4-Pro 是纯文本模型，不是多模态；只有 -Vision-Exp 是视觉模型。
    KNOWN_MODELS = [
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash（文本·快）", "vision": False, "desc": "纯文本非思考模式，响应最快，适合日常对话（非多模态）"},
        {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro（文本·深度思考）", "vision": False, "desc": "纯文本带推理链，适合复杂问题/策略分析（非多模态）"},
        {"id": "deepseek-v4-flash-vision-exp", "label": "DeepSeek V4 Flash Vision Exp（多模态·可看图）", "vision": True, "desc": "DeepSeek 首个多模态视觉模型 (2026-08-21 发布)，支持图像理解，纯文本能力与 V4-Flash 持平"},
        {"id": "deepseek-chat", "label": "DeepSeek Chat（文本·通用）", "vision": False, "desc": "经典通用对话模型（非多模态）"},
        {"id": "deepseek-reasoner", "label": "DeepSeek Reasoner（文本·推理）", "vision": False, "desc": "专注推理，输出附带思考过程（非多模态）"},
    ]

    def _is_vision_model(model: str) -> bool:
        """判断当前模型是否支持图像理解（按名称关键词），允许自定义模型名命中。"""
        m = (model or "").lower()
        return any(k in m for k in ("vision", "vl", "4v", "omni", "gemini", "multimodal", "image", "-exp"))

    def _mask_key(k: str) -> str:
        return (k[:6] + "…" + k[-4:]) if k and len(k) > 12 else ("已配置" if k else "")

    @router.get("/qing/config")
    async def qing_config():
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        try:
            from openai import AsyncOpenAI
            test_ok, balance = False, None
        except Exception:
            test_ok, balance = False, None
        return JSONResponse({
            "ok": True,
            "key": _mask_key(key),
            "has_api_key": bool(key.strip()),
            "base_url": base,
            "model": model,
            "vision_capable": _is_vision_model(model),
            "models": KNOWN_MODELS,
            "connected": bool(key.strip() and key.strip().startswith("sk-")),
        })

    def _config_dir() -> str:
        """统一配置目录：优先用启动脚本写入的 QING_CONFIG_DIR（冻结=exe 目录，开发=项目根）。"""
        return os.environ.get("QING_CONFIG_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _write_env(pairs):
        """写入/覆盖 .env 中指定 KEY=VALUE 行；不存在则追加。"""
        env_path = os.path.join(_config_dir(), ".env")
        keys = [k for k, _ in pairs]
        try:
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                out, seen = [], set()
                for ln in lines:
                    stripped = ln.strip()
                    hit = None
                    for k in keys:
                        if stripped.startswith(k + "="):
                            hit = k; break
                    if hit:
                        val = dict(pairs)[hit]
                        out.append(f"{hit}={val}")
                        seen.add(hit)
                    else:
                        out.append(ln)
                for k, v in pairs:
                    if k not in seen:
                        out.append(f"{k}={v}")
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(out) + "\n")
            else:
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(f"{k}={v}" for k, v in pairs) + "\n")
        except Exception as e:
            logger.error(f"写入 .env 失败: {e}")

    def _hot_update_llm(base_url=None, model=None, key=None):
        """热更新运行中的 LLM client + 模型名（当前会话立即生效）。"""
        hot = False
        try:
            from openai import AsyncOpenAI
            agent = getattr(ctx, "agent_engine", None)
            llm = getattr(agent, "llm", None) or getattr(agent, "_llm", None)
            if llm is not None and hasattr(llm, "client"):
                base = base_url or getattr(llm, "base_url", "https://api.deepseek.com")
                k = key or os.environ.get("DEEPSEEK_API_KEY", "")
                llm.client = AsyncOpenAI(base_url=base, api_key=k)
                if model:
                    llm.model = model
                if base_url:
                    llm.base_url = base_url
                hot = True
        except Exception as e:
            logger.debug(f"热更新 LLM 失败(非阻塞): {e}")
        return hot

    @router.post("/qing/config")
    async def qing_config_save(payload: dict):
        """保存 API 接入配置（key / model / base_url），校验并热更新。"""
        p = payload or {}
        key = (p.get("key") or "").strip()
        model = (p.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")).strip()
        base_url = (p.get("base_url") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).strip()

        # 若传了新 key 则格式化校验；仅当 base_url 指向 DeepSeek 时才联网校验余额（自定义地址跳过）
        if key:
            if not key.startswith("sk-") or not key.isascii():
                return JSONResponse({"ok": False, "error": "格式不对：API key 以 sk- 开头且为 ASCII"}, status_code=400)
            if "deepseek" in base_url.lower():
                try:
                    import httpx
                    r = httpx.get("https://api.deepseek.com/user/balance",
                                  headers={"Authorization": f"Bearer {key}"}, timeout=10)
                    if r.status_code != 200:
                        return JSONResponse({"ok": False, "error": f"DeepSeek 校验失败：HTTP {r.status_code}，key 可能无效"}, status_code=400)
                except Exception as e:
                    logger.warning(f"key 联网校验跳过(非阻塞): {e}")

        # 写入 .env + 环境变量
        pairs = []
        if key:
            pairs.append(("DEEPSEEK_API_KEY", key))
        if model and model != "auto":
            pairs.append(("DEEPSEEK_MODEL", model))
        if base_url and base_url != "auto":
            pairs.append(("DEEPSEEK_BASE_URL", base_url))
        if pairs:
            _write_env(pairs)
        if key:
            os.environ["DEEPSEEK_API_KEY"] = key
        if model and model != "auto":
            os.environ["DEEPSEEK_MODEL"] = model
        if base_url and base_url != "auto":
            os.environ["DEEPSEEK_BASE_URL"] = base_url

        hot = _hot_update_llm(base_url=(None if base_url == "auto" else base_url),
                              model=(None if model == "auto" else model),
                              key=key or None)

        # 刷新 system prompt（模型切换后提示词可能变化）
        try:
            if hasattr(ctx, "refresh_system_prompt"):
                await ctx.refresh_system_prompt()
        except Exception as e:
            logger.debug(f"刷新系统提示失败(非阻塞): {e}")

        logger.info(f"已更新 API 配置：model={model} base={base_url} 热更新={'成功' if hot else '需重启'}")
        return JSONResponse({"ok": True, "hot_updated": hot,
                             "note": "已保存并生效" if hot else "已保存，重启后生效",
                             "model": model, "base_url": base_url,
                             "vision_capable": _is_vision_model(model)})

    @router.post("/qing/set-key")
    async def qing_set_key(payload: dict):
        """兼容接口：仅更新 key（旧调用），复用 config 保存逻辑。"""
        return await qing_config_save({"key": (payload or {}).get("key", "")})

    @router.get("/qing/memory")
    async def qing_memory():
        """返回 道/法/术/经历 + 人格 的完整内容，供控制台展示。"""
        mem_dir = _mem_dir()
        out = {"dao": [], "fa": [], "shu": [], "story": [], "persona": _persona()}
        for layer, key in (("dao", "principles"), ("fa", "strategies"), ("shu", "facts"), ("story", "narratives")):
            p = os.path.join(mem_dir, f"{layer}.json")
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    items = data.get(key, [])
                    out[layer] = [{k: it.get(k) for k in ("text", "rule", "category", "ts") if it.get(k) is not None} for it in items][:30]
                except Exception:
                    pass
        return JSONResponse({"ok": True, **out})

    @router.post("/qing/apply-voice")
    async def qing_apply_voice(payload: dict):
        """应用某个音色到当前 TTS（edge-tts），立即生效。"""
        voice_id = ((payload or {}).get("voice_id") or "").strip()
        if not voice_id:
            return JSONResponse({"ok": False, "error": "缺少 voice_id"}, status_code=400)
        # 热更新 tts_engine
        applied = False
        try:
            eng = getattr(ctx, "tts_engine", None)
            if eng is not None and hasattr(eng, "voice"):
                eng.voice = voice_id
                applied = True
        except Exception as e:
            logger.debug(f"热更新音色失败: {e}")
        # 持久化到 conf.yaml 的 edge_tts.voice（仅匹配行首的 voice: 键，绝不误伤 sense_voice: 等含 voice 子串的键）
        try:
            conf_path = os.path.join(_config_dir(), "conf.yaml")
            with open(conf_path, "r", encoding="utf-8") as f:
                txt = f.read()
            import re
            # 行首（允许缩进）+ voice: 键，后跟非空非注释值；re.MULTILINE 保证只匹配独立一行的 voice: 键
            new_txt, n = re.subn(r"(^[ \t]*voice:)[ \t]*[^\s#]+", rf"\g<1> {voice_id}", txt, count=1, flags=re.MULTILINE)
            if new_txt != txt:
                with open(conf_path, "w", encoding="utf-8") as f:
                    f.write(new_txt)
        except Exception as e:
            logger.debug(f"写 conf.yaml 音色失败(非阻塞): {e}")
        logger.info(f"已应用音色={voice_id}（热更新={'成功' if applied else '需重启'}）")
        return JSONResponse({"ok": True, "applied": applied, "note": "音色已生效" if applied else "音色已保存，重启后生效", "voice_id": voice_id})

    @router.post("/qing/reset")
    async def qing_reset():
        """隐私清空：移除用户个人信息，恢复干净默认档案。

        彻底性：
        1) 清理磁盘记忆层 + 人格 + 当前人格设定
        2) 清空聊天历史库（chat_history/{conf_uid}）
        3) 重建进程级共享记忆单例（所有会话即时拿到干净数据，杜绝旧缓存复活）
        4) 清空 agent 会话记忆缓冲（避免 LLM 上下文残留）
        5) 刷新系统提示
        """
        mem_dir = _mem_dir()
        try:
            # 1) 恢复干净默认记忆层 + 人格 + 个人档案
            for layer, key, default in (
                ("dao", "principles", CLEAN_DAO),
                ("fa", "strategies", CLEAN_FA),
                ("shu", "facts", CLEAN_SHU),
                ("story", "narratives", []),
            ):
                data = {"version": 1, "updated_at": datetime.now().isoformat(timespec="seconds"),
                        "layers": layer, key: default}
                with open(os.path.join(mem_dir, f"{layer}.json"), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            with open(os.path.join(mem_dir, "persona.json"), "w", encoding="utf-8") as f:
                json.dump(CLEAN_PERSONA, f, ensure_ascii=False, indent=2)
            ap = os.path.join(mem_dir, ".active_persona.json")
            if os.path.isfile(ap):
                os.remove(ap)
            with open(os.path.join(mem_dir, "user_profile.md"), "w", encoding="utf-8") as f:
                f.write("# 用户画像\n\n> 尚未建立。隐私模式已重置，对话将重新沉淀。\n\n## 已验证的交易模式（L3 原则层）\n（无——等待对话沉淀）\n")

            # 2) 清空聊天历史库
            try:
                from .chat_history_manager import get_history_list, delete_history
                conf_uid = (ctx.character_config.conf_uid if ctx and ctx.character_config else "mao_pro_001")
                for h in get_history_list(conf_uid):
                    delete_history(conf_uid, h.get("history_uid") if isinstance(h, dict) else "")
            except Exception as e:
                logger.debug(f"清聊天历史失败(非阻塞): {e}")

            # 3) 重建共享记忆单例（所有会话即时生效，杜绝旧缓存复活写回）
            from .service_context import _reset_shared_memory, _get_shared_memory_hub, _get_shared_persona_distiller
            _reset_shared_memory(mem_dir)
            ctx.memory_hub = _get_shared_memory_hub(mem_dir)
            ctx.persona_distiller = _get_shared_persona_distiller(mem_dir)

            # 4) 清空 agent 会话记忆缓冲
            try:
                if hasattr(ctx, "agent_engine") and ctx.agent_engine and hasattr(ctx.agent_engine, "clear_memory"):
                    ctx.agent_engine.clear_memory()
            except Exception as e:
                logger.debug(f"清 agent 缓冲失败(非阻塞): {e}")

            # 5) 刷新系统提示
            try:
                if hasattr(ctx, "refresh_system_prompt"):
                    await ctx.refresh_system_prompt()
            except Exception as e:
                logger.debug(f"刷新系统提示失败(非阻塞): {e}")

            logger.info("已执行隐私重置（移除个人信息）")
            return JSONResponse({"ok": True})
        except Exception as e:
            logger.error(f"隐私重置失败: {e}")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    return router
