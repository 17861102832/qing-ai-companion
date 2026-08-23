@echo off
chcp 65001 >nul
title 小青 · 一键生成安装包
cd /d "%~dp0"

echo ============================================
echo   小青 · 一键生成 Windows 安装包
echo   (Setup.exe + app\ = 真·安装程序)
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")

echo [1/4] 用 PyInstaller 重新打包程序本体...
"%PY%" -m PyInstaller qing_pack.spec --noconfirm --log-level WARN
if errorlevel 1 ( echo 打包失败 & pause & exit /b 1 )

echo [2/4] 编译安装器 Setup.exe...
set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if exist "%CSC%" (
  "%CSC%" /target:winexe /out:Setup.exe /r:System.Windows.Forms.dll /r:System.Drawing.dll Setup.cs
) else (
  echo 未找到 csc.exe，跳过（使用已有 Setup.exe）
)

echo [3/4] 组装安装包目录...
if exist "安装包_小青" rmdir /s /q "安装包_小青"
mkdir "安装包_小青"
copy Setup.exe "安装包_小青\Setup.exe" >nul
xcopy "dist\小青" "安装包_小青\app" /e /i /y >nul
copy README_安装版.md "安装包_小青\" >nul 2>nul

echo [4/4] 压缩为 zip...
del "小青_安装版.zip" 2>nul
powershell -NoProfile -Command "Compress-Archive -Path '安装包_小青\*' -DestinationPath '小青_安装版.zip' -Force"
if exist "小青_安装版.zip" (
  for %%A in ("小青_安装版.zip") do echo 完成：小青_安装版.zip (%%~zA 字节)
) else (
  echo 压缩失败，请手动压缩 安装包_小青 文件夹
)
echo.
echo 安装包：安装包_小青\Setup.exe （发给别人，双击即装即用）
pause
