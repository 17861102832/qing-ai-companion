# ============================================================
# 小青 · AI数字人伴侣启动脚本
# 基于 Open-LLM-VTuber + DeepSeek API + Live2D + 专属记忆库
# ============================================================
import sys
import os
from pathlib import Path
import tomli

# === PyInstaller 冻结运行与配置目录 ===
# 数据（frontend/models/live2d 等）在 PyInstaller 6.x onedir 下位于 _internal/，
# 代码用相对路径引用，需 chdir 到 _MEIPASS 才能正确定位；而 .env 是用户可改的配置，
# 应放 exe 所在目录（Setup.exe 安装后在安装根、开发时在项目根）。
_FROZEN = bool(getattr(sys, "frozen", False))
if _FROZEN:
    try:
        _MEIPASS = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        if _MEIPASS:
            os.chdir(_MEIPASS)
            if _MEIPASS not in sys.path:
                sys.path.insert(0, _MEIPASS)
        _CONFIG_DIR = os.path.dirname(os.path.abspath(sys.executable))  # exe 所在目录（用户可改 .env）
    except Exception as e:
        print("[打包] 切换工作目录失败(非阻塞):", e)
        _CONFIG_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 开发模式：工作目录与配置目录固定为项目根，确保相对路径稳定解析
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    _CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

# 统一暴露给面板写配置（改 key 等），保证"读"与"写"用的是同一个 .env
os.environ["QING_CONFIG_DIR"] = _CONFIG_DIR

os.environ["HF_HOME"] = str(Path(_CONFIG_DIR) / "models")
os.environ["MODELSCOPE_CACHE"] = str(Path(_CONFIG_DIR) / "models")

# 强制使用项目 venv 的 python（避免全局环境）。冻结运行时跳过。
if not _FROZEN:
    VE = Path(_CONFIG_DIR) / ".venv"
    if VE.exists():
        venv_py = VE / "Scripts" / "python.exe"
        if venv_py.exists() and sys.executable != str(venv_py):
            os.execv(str(venv_py), [str(venv_py)] + sys.argv)

import uvicorn
from loguru import logger
from src.open_llm_vtuber.server import WebSocketServer
from src.open_llm_vtuber.config_manager import Config, read_yaml, validate_config

# 关键：启动时加载 .env（含 key/记忆目录），供 read_yaml 的 ${VAR} 替换使用
# 配置目录统一为 _CONFIG_DIR（冻结=exe 目录，开发=项目根），面板改 key 也写这里，保证读写一致
try:
    from dotenv import load_dotenv
    env_path = Path(_CONFIG_DIR) / ".env"
    if not env_path.exists():
        # 模板优先找配置目录，其次找数据目录(_internal)里随包带的 .env.example
        example = Path(_CONFIG_DIR) / ".env.example"
        if not example.exists() and _FROZEN:
            example = Path(sys._MEIPASS) / ".env.example"
        if example.exists():
            import shutil
            if env_path.parent and not env_path.parent.exists():
                os.makedirs(env_path.parent, exist_ok=True)
            shutil.copy(str(example), str(env_path))
            logger.warning(f"已从模板生成 .env，请填写 DEEPSEEK_API_KEY 后重启: {env_path}")
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
        logger.info(f"已加载 .env: {env_path}")
    else:
        logger.warning(f".env 不存在: {env_path}")
except Exception as e:
    logger.warning(f"加载 .env 失败(非阻塞): {e}")

# 给可配置的模型/地址设置默认值（conf.yaml 用 ${VAR} 引用，若 .env 未写则用默认）
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")

# 注：不再写回 conf.yaml —— 保持其始终为 ${VAR} 模板，
# 让 read_yaml 用 .env 动态替换 key，用户改 .env 即可随便填 key。


def main():
    # 版本号：开发从 pyproject.toml 读；打包运行可能没有该文件，用兜底值
    try:
        with open("pyproject.toml", "rb") as f:
            version = tomli.load(f)["project"]["version"]
    except Exception:
        version = "1.2.1"
    logger.info(f"Open-LLM-VTuber (小青), version v{version}")

    # === 安全自检：关键文件完整性 + 依赖指纹 + 生成蒸馏盾 ===
    try:
        from src.open_llm_vtuber.security_guard import SecurityGuard
        guard = SecurityGuard("memory_knowledge")
        integrity = guard.check_integrity(str(Path(__file__).parent))
        missing = [k for k, v in integrity.items() if v == "MISSING"]
        if missing:
            logger.warning(f"[安全] 关键文件缺失: {missing}")
        else:
            logger.info("[安全] 关键文件自检通过")
        fp = guard.dep_fingerprint(str(Path(__file__).parent / "requirements.txt"))
        logger.info(f"[安全] 依赖指纹: sha256={fp.get('sha256','N/A')} 依赖数={fp.get('lines','N/A')}")
        try:
            guard.mint_canary()
        except Exception as e:
            logger.debug(f"[安全] 蒸馏盾生成跳过: {e}")
    except Exception as e:
        logger.warning(f"[安全] 自检异常(非阻塞): {e}")

    # 前端子模块检查
    frontend = Path(__file__).parent / "frontend" / "index.html"
    if not frontend.exists():
        logger.critical("前端子模块缺失，请运行 git submodule update --init")

    config: Config = validate_config(read_yaml("conf.yaml"))
    server_config = config.system_config
    server = WebSocketServer(config=config)
    import asyncio
    asyncio.run(server.initialize())

    logger.info(f"👉 公网访问: http://{server_config.host}:{server_config.port}")
    logger.info(f"👉 本机访问: http://localhost:{server_config.port}")

    # 自动打开浏览器（让"打包版"体验与网页版一致；服务就绪后自动弹出）
    def _open_browser_later(url: str):
        import time
        time.sleep(2.5)
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            logger.debug(f"自动打开浏览器失败(非阻塞): {e}")

    try:
        import threading
        _target = f"http://localhost:{server_config.port}"
        threading.Thread(target=_open_browser_later, args=(_target,), daemon=True).start()
    except Exception as e:
        logger.debug(f"启动自动开浏览器线程失败(非阻塞): {e}")

    uvicorn.run(app=server.app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()
