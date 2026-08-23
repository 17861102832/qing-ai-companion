@echo off
chcp 65001 >nul
title 小青 · 一键打包为免Python分发包
cd /d "%~dp0"

echo ============================================
echo   小青 · 打包成「免 Python 预装」分发包
echo   （PyInstaller 单目录模式，产物在 dist\小青\）
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo [1/3] 安装打包工具 PyInstaller...
"%PY%" -m pip install pyinstaller -q --index-url https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 ( "%PY%" -m pip install pyinstaller -q )

echo [2/3] 开始打包（约几分钟，请勿关闭）...
"%PY%" -m PyInstaller qing_pack.spec --noconfirm
if errorlevel 1 (
  echo [错误] 打包失败，请查看上方日志。
  pause
  exit /b 1
)

echo [3/3] 打包完成。
echo 产物：dist\小青\小青.exe
echo 把 dist\小青\ 整个文件夹打包成 zip 发给别人，对方解压双击 小青.exe 即可运行（无需装 Python）。
echo.
pause
