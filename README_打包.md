# 小青 · 打包成「免 Python 预装」分发包

## 这是什么
用 **PyInstaller** 把「小青」整个服务 + 依赖 + 数据（前端/Live2D/ASR 模型）打包成一个分发包，让对方**不用装 Python**，解压后双击 `小青.exe` 就能跑。

## 两种运行方式对比
| 方式 | 别人需要装什么 | 适配 |
|------|--------------|------|
| `一键运行_小青.bat` | 需装 Python 3.10~3.12 + 联网装依赖 | 开发/灵活 |
| **PyInstaller 分发包（本文件）** | **什么都不用装**，双击 exe 即用 | 给外行/快速分发（推荐） |

## ✅ 打包已验证（2026-08-22）
已在本机实跑构建，产物：
- `dist\小青\小青.exe`（约 17MB，含全部 Python 依赖）
- 数据在 `dist\小青\_internal\`（frontend / live2d-models / models(ASR) / characters / memory_knowledge / distill_tool / config_templates / prompts / web_tool / avatars / backgrounds / conf.yaml / model_dict.json / .env.example）
- **实测启动成功**：`Uvicorn running on http://localhost:12393`，`/` HTTP 200，`/qing/status` 返回记忆、MBTI 人格预设、控制台数据齐全。
- 已封装成可分发 zip：`小青_免装版_20260822.zip`（约 280MB）。

## 打包步骤（你在自己电脑上做一次）
1. 双击 `一键打包.bat`（或手动执行 `一键打包.bat`）。
2. 等待完成，产物在 `dist\小青\`。
3. 把 **`dist\小青\` 整个文件夹** 压缩成 zip，发给别人。
4. 对方解压 → 双击 `小青.exe` → 浏览器自动打开 http://localhost:12393。

## 重要：隐私与 Key
- 打包产物**不包含**你的 `.env`（不会带你的 DeepSeek key）。
- 产品用 `memory_knowledge/`（干净默认档案，无个人信息）做初始记忆。
- 对方首次运行前需在 `.env`（会用模板生成）里填自己的 key；也可以在 `http://localhost:12393` 左下角控制台点「隐私清空」重置。

## 注意
- 首次启动 PyInstaller 会慢（解压/加载 onnxruntime 等），属正常。
- 若打包报 `onnxruntime`/`sherpa_onnx` 缺失，确认它们已装进 `.venv`（`pip install sherpa-onnx onnxruntime`）。
- 分发包体积较大（含本地 ASR 模型 + Live2D 素材），介意体积可在打包前删掉 `models/` 下不用的语音模型。

## 相关文件
- `qing_pack.spec` —— PyInstaller 配置（含数据收集）
- `一键打包.bat` —— 一键构建脚本
