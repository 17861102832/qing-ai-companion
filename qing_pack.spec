# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# 小青 · PyInstaller 打包配置（免 Python 预装的一键分发包）
# 构建：在 open-llm-vtuber 根目录执行
#   .venv\Scripts\python -m PyInstaller qing_pack.spec --noconfirm
# 产物：dist\小青\ 内含 小青.exe + 数据文件夹（frontend/live2d-models/models/...）
# 分发：把整个 dist\小青\ 目录打包成 zip，别人解压双击 小青.exe 即用。
# ============================================================
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

proj = os.path.abspath('.')
# 需要打进 asr/tts/vad 等运行时可选模块（onnxruntime/sherpa 等由 import 触发）
hidden = collect_submodules('open_llm_vtuber')
hidden += ['onnxruntime', 'sherpa_onnx', 'uvicorn', 'loguru', 'dotenv', 'pydantic', 'numpy', 'pysbd', 'edge_tts']

# 数据目录：随分发包一起，位于 exe 同级（PyInstaller 6.x 会放进 _internal/）
datas = []
for d in ['frontend', 'live2d-models', 'backgrounds', 'avatars', 'characters', 'memory_knowledge', 'distill_tool', 'config_templates', 'prompts', 'web_tool']:
    src = os.path.join(proj, d)
    if os.path.isdir(src):
        datas.append((src, d))
# 首次运行模板 + 根级配置（.env 含真实 key，绝不打包）
for f in ('.env.example', 'conf.yaml', 'model_dict.json', 'pyproject.toml'):
    src = os.path.join(proj, f)
    if os.path.isfile(src):
        datas.append((src, '.'))
# ASR/TTS 本地模型（conf.yaml 用相对路径引用，需在解包根保持结构）
models_dir = os.path.join(proj, 'models')
if os.path.isdir(models_dir):
    datas.append((models_dir, 'models'))

a = Analysis(
    ['run_qing.py'],
    pathex=[proj],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'torch', 'PIL'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='小青',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name='小青',
)
