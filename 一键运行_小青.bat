@echo off
chcp 65001 >nul
title 小青 · AI数字人伴侣 · 一键启动
cd /d "%~dp0"

echo ============================================
echo   小青 · AI数字人伴侣  一键启动
echo   (Open-LLM-VTuber + DeepSeek + Live2D)
echo ============================================
echo.

REM ===== 0) 安全提示 =====
echo [安全] 首次启动将检查环境并自动安装依赖，请勿关闭本窗口。
echo [安全] 本程序只在本机运行，记忆默认保存在 memory_knowledge/。
echo       如删改前建议备份，勿直接删除记忆文件夹。
echo.

REM ===== 1) 检查 Python =====
set "PYTHON="
python --version >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON (
  py --version >nul 2>&1 && set "PYTHON=py"
)
if not defined PYTHON (
  echo [错误] 未检测到 Python。请安装 Python 3.10 ~ 3.12：
  echo        https://www.python.org/downloads/
  echo        安装时勾选 "Add python.exe to PATH"
  pause
  exit /b 1
)
echo [OK] 找到 Python: %PYTHON%
%PYTHON% --version

REM ===== 2) 检查/创建 .env =====
if not exist ".env" (
  echo [提示] 未找到 .env（API Key 配置），已为你生成模板，请填写。
  echo.
  echo   DeepSeek API Key 获取：https://platform.deepseek.com
  echo   ^(左侧"API Keys" - "创建" - 复制 sk-xxx^)
  echo.
  copy ".env.example" ".env" >nul
  notepad ".env"
  echo [提示] 填完 .env 后请重新运行本脚本。
  pause
  exit /b 0
)

REM ===== 3) 检查依赖与虚拟环境 =====
if exist ".venv\Scripts\python.exe" (
  echo [OK] 检测到虚拟环境 .venv
) else (
  echo [初次启动] 正在创建虚拟环境并安装依赖（约需数十秒，请耐心等待）...
  %PYTHON% -m venv .venv
  if errorlevel 1 (
     echo [错误] 创建虚拟环境失败
     pause
     exit /b 1
  )
  echo [安装依赖] 正在用清华镜像安装... 若无镜像网络可删掉 --index-url 重试
  ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q --index-url https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 (
     echo [警告] 部分依赖安装可能失败，尝试直接从 PyPI 安装...
     ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
  )
)

REM ===== 4) 前端子模块检查 =====
if not exist "frontend\index.html" (
  echo [提示] 前端文件缺失，尝试初始化...
  git submodule update --init --recursive >nul 2>&1
)

REM ===== 5) 安全自检：关键文件完整性 =====
echo.
echo [自检] 检查关键模块...
if exist "src\open_llm_vtuber\memory_hub.py" ( echo   [OK] memory_hub 记忆中枢 ) else ( echo   [!] memory_hub 缺失 )
if exist "src\open_llm_vtuber\persona_distiller.py" ( echo   [OK] persona_distiller 人格蒸馏 ) else ( echo   [!] persona_distiller 缺失 )
if exist "live2d-models\mao_pro\runtime\mao_pro.model3.json" ( echo   [OK] Live2D 模型 ) else ( echo   [!] Live2D 模型缺失 )

echo.
echo ============================================
echo   启动服务中... 完成后浏览器自动打开
echo   http://localhost:12393
echo   关闭本窗口即停止服务
echo ============================================
echo.
start "" http://localhost:12393
".venv\Scripts\python.exe" run_qing.py

pause
