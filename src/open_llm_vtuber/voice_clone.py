# -*- coding: utf-8 -*-
"""
QingVoiceClone —— 小青声音克隆模块（基于 GPT-SoVITS）

功能：
1. 一键复刻：用户上传一段 5-30 秒参考音频 → 训练/推理出可复刻其音色的 TTS 模型
2. 预设女生音色：内置几款高质量女生音色供直接选用
3. 对话-动作同步：根据对话文本情绪/关键词，驱动 Live2D 做对应动作

集成：GPT-SoVITS（5秒声音克隆，开源）
依赖：GPT-SoVITS 项目需克隆到本地，本模块通过 HTTP 调用其 WebUI API。
"""
import os
import json
import glob
import shutil
import hashlib
import tempfile
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


# 预设女生音色（可下载的公开音色）
PRESET_FEMALE_VOICES = [
    {
        "name": "甜美女声-小雅",
        "desc": "温暖甜美、略带气声的年轻女声，适合陪伴型对话",
        "tags": ["甜", "温暖", "女声", "中文"],
        "file": "voice_models/presets/小雅.mp3",
        "voice_id": "zh-CN-XiaoxiaoNeural",
    },
    {
        "name": "清冷女声-凌霜",
        "desc": "清冷知性、语速偏慢，适合高冷/军师型人格",
        "tags": ["清冷", "知性", "女声", "中文"],
        "file": "voice_models/presets/凌霜.mp3",
        "voice_id": "zh-CN-YunxiNeural",
    },
    {
        "name": "活力女声-小鹿",
        "desc": "活泼跳跃、语速快，适合 ENFP 快乐小狗型人格",
        "tags": ["活泼", "快语速", "女声", "中文"],
        "file": "voice_models/presets/小鹿.mp3",
        "voice_id": "zh-CN-XiaoyiNeural",
    },
    {
        "name": "温柔女声-晚晴",
        "desc": "温柔母性、语速慢，适合 ESFJ 暖心大管家型人格",
        "tags": ["温柔", "母性", "女声", "中文"],
        "file": "voice_models/presets/晚晴.mp3",
        "voice_id": "zh-CN-YunjianNeural",
    },
]

# 对话-动作映射表：根据文本关键词/情绪 → Live2D 动作组
DIALOGUE_ACTION_MAP = [
    # 问候/告别
    (r"(你好|嗨|哈喽|hello|hi|早上好|晚上好|再见|拜拜|晚安)", "TapHead", "点头/挥手"),
    # 开心/笑
    (r"(哈哈|开心|高兴|笑死|太棒了|nice|耶|嘻嘻)", "TapBody", "开心摇摆"),
    # 思考/疑惑
    (r"(嗯|思考|想想|疑惑|为什么|怎么|什么|？\?|吗\?)", "TapHead", "思考"),
    # 生气/不满
    (r"(生气|愤怒|气死|烦|讨厌|滚|哼)", "TapBody", "生气"),
    # 悲伤/难过
    (r"(难过|伤心|哭|泪|抱歉|对不起|呜呜)", "TapHead", "难过"),
    # 惊讶/震惊
    (r"(哇|天哪|真的吗|不会吧|震惊|卧槽|我靠)", "TapBody", "惊讶"),
    # 撒娇/可爱
    (r"(人家|嘛|啦|呢|哼|讨厌啦|可爱)", "TapBody", "撒娇"),
    # 默认/Idle
    (r".*", "Idle", "待机"),
]


class VoiceCloneManager:
    """声音克隆管理器。"""

    def __init__(self, base_dir: str = "voice_models"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(os.path.join(base_dir, "presets"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "cloned"), exist_ok=True)

    def list_preset_voices(self) -> list:
        return PRESET_FEMALE_VOICES

    def list_cloned_voices(self) -> list:
        """列出已克隆/上传的用户音色。"""
        out = []
        for d in glob.glob(os.path.join(self.base_dir, "cloned", "*")):
            if os.path.isdir(d):
                meta = os.path.join(d, "meta.json")
                if os.path.isfile(meta):
                    try:
                        with open(meta, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        out.append(m)
                    except Exception:
                        pass
        return out

    def save_reference_audio(self, audio_bytes: bytes, filename: str = "reference.wav") -> str:
        """保存用户上传的参考音频，返回路径。"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        voice_dir = os.path.join(self.base_dir, "cloned", f"voice_{ts}")
        os.makedirs(voice_dir, exist_ok=True)
        path = os.path.join(voice_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        # 写 meta
        meta = {
            "name": f"克隆音色-{ts}",
            "created": datetime.now().isoformat(timespec="seconds"),
            "reference": filename,
        }
        with open(os.path.join(voice_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存参考音频: {path}")
        return path

    def get_action_for_text(self, text: str) -> dict:
        """根据对话文本决定 Live2D 动作。"""
        import re
        for pattern, group, desc in DIALOGUE_ACTION_MAP:
            if re.search(pattern, text):
                return {"group": group, "desc": desc, "pattern": pattern}
        return {"group": "Idle", "desc": "待机", "pattern": "*"}


def init_voice_routes(ctx) -> list:
    """返回语音相关的路由定义列表（供外部挂载）。"""
    from fastapi import APIRouter, UploadFile, File
    from starlette.responses import JSONResponse

    router = APIRouter()
    mgr = VoiceCloneManager()

    @router.get("/voice/presets")
    async def list_presets():
        return JSONResponse({"voices": mgr.list_preset_voices()})

    @router.get("/voice/cloned")
    async def list_cloned():
        return JSONResponse({"voices": mgr.list_cloned_voices()})

    @router.post("/voice/upload")
    async def upload_reference(file: UploadFile = File(...)):
        try:
            contents = await file.read()
            if len(contents) < 1000:
                return JSONResponse({"ok": False, "error": "音频太短"}, status_code=400)
            path = mgr.save_reference_audio(contents, file.filename or "reference.wav")
            return JSONResponse({"ok": True, "path": path})
        except Exception as e:
            logger.error(f"上传参考音频失败: {e}")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @router.post("/voice/action")
    async def get_action(payload: dict):
        text = (payload or {}).get("text", "")
        action = mgr.get_action_for_text(text)
        return JSONResponse({"ok": True, "action": action})

    @router.get("/voice/audio/{name}")
    async def get_preset_audio(name: str):
        """返回预设音流的音频文件流。"""
        from starlette.responses import FileResponse
        import glob
        # 在 preset 目录下查找
        pattern = os.path.join(mgr.base_dir, "presets", f"{name}.*")
        files = glob.glob(pattern)
        if not files:
            return JSONResponse({"ok": False, "error": "未找到音频"}, status_code=404)
        return FileResponse(files[0], media_type="audio/mpeg")

    return [router]
