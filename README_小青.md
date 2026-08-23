# 小青 · AI 数字人伴侣

> 基于 Open-LLM-VTuber + DeepSeek API + Live2D，可本地离线运行的 AI 数字人伴侣。
> 支持：点击互动、表情动作、人格蒸馏、三层记忆中枢、跨机器持久记忆、安全防护、一键运行。

---

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| 🎭 虚拟人 | Live2D 形象（Mao Pro 魔法猫娘），点击头/身播不同动作，30 种表情关键词 |
| 🧠 人格蒸馏 | 自动从你聊的话中提取核心价值观/口头禅/兴趣/情绪模式，越聊越像你 |
| 📦 三层记忆 | 道（偏好）/法（策略）/术（事实）持久化，换电脑也能记住你 |
| 🗣️ 真实对话 | DeepSeek 大模型，结合你的记忆与人格画像和你交流 |
| 🎙️ 音色切换 | 内置 4 款女声预设（可自由切换）；上传参考音频，经 GPT-SoVITS 可复刻你自己的音色 |
| 🛡️ 安全防护 | 启动自检、依赖指纹、危险动作拦截、记忆包蒸馏盾(CANARY) |
| 🚀 一键运行 | 下载后双击 `一键运行_小青.bat` 即可使用 |

---

## 🚀 快速开始（别人拿到后）

### 前置：只需装好 Python 3.10~3.12（带 pip）
下载: https://www.python.org/downloads/  安装时勾选 "Add python.exe to PATH"

### 一键启动
1. 解压本项目
2. 修改 `.env`（第一次运行会自动生成模板）：
   ```
   DEEPSEEK_API_KEY=sk-你的key         ← 必填，去 platform.deepseek.com 申请
   #QING_MEM_DIR=                       ← 可选，填外部文件夹则记忆存那里
   ```
3. 双击 `一键运行_小青.bat`（将自动建虚拟环境 + 装依赖 + 启动）
4. 浏览器自动打开 http://localhost:12393

### 换你自己的 DeepSeek Key
**两种方式，任选其一：**
- **界面改（推荐）**：打开 http://localhost:12393 → 左下角「🧬 小青控制台」→ 顶部「DeepSeek API Key」粘贴你的 `sk-xxx` → 点「保存并生效」。会联网校验有效性，有效期立即热更新，无需重启。
- **改文件**：编辑 `.env` → 把 `DEEPSEEK_API_KEY` 换成你的 `sk-xxx` → 重启。
**Key 在本地 .env，不会上传，随便填都能用。**

---

## 📂 记忆保存到哪里（产品化关键）

- 默认：项目内 `memory_knowledge/`（含 `dao.json`/`fa.json`/`shu.json`/`persona.json`）
- **跨机器持久**：在 `.env` 填 `QING_MEM_DIR=C:\你的路径\小青记忆`，记忆就存到那个外部文件夹。
  换电脑/重装系统，只需把这个文件夹拷走即可。

---

## 🎭 人格蒸馏是怎么做的

借鉴 `distill_tool/`（immortal-skill 引擎）四维提取机制：
- 核心价值观、口头禅、情绪模式、兴趣审美
- **行为证据优先**（记录"做了什么"而非"是什么人"）、禁止心理标签
- 证据分级：`verbatim`（原话）/`artifact`（客观推断）/`impression`（主观印象）
- 每次对话后自动沉淀到 `persona.json`，并在下次回复时注入你的人格画像

---

## 🛡️ 安全防护

- **启动自检**：关键模块完整性与依赖指纹校验
- **危险拦截**：检测"删库/rm -rf/全仓/梭哈"类高风险描述时给出二次确认提示
- **蒸馏盾**：为记忆包生成 `CANARY.txt` 唯一标记，用于检测记忆是否被未授权复制进自动化管线

---

## 🎙️ 声音克隆（复刻你的音色）

- **上传参考音频是真实可用的**：控制台「🎙 声音克隆」选一段 5～30 秒清晰人声 → 点「上传复刻」→ 音频会保存到 `voice_models/cloned/克隆音色-时间/`。
- **把上传的音色真正用于说话**：需要本地运行 **GPT-SoVITS**（开源 5 秒声音克隆，约需 GPU）。配置里已预留好接入点：
  `conf.yaml` 的 `tts_config.tts_model: "gpt_sovits_tts"` 指向 `http://127.0.0.1:9880`。跑起 GPT-SoVITS 后，把参考音频指向克隆文件夹即可让「小青」用你的声音说话。
- **不跑 GPT-SoVITS 也能直接用音色**：内置 4 款女声（甜美女声-小雅 / 清冷女声-凌霜 / 活力女声-小鹿 / 温柔女声-晚晴），点击即切换，走 edge-tts，无需任何额外服务。

---

## 🐞 常见问题

| 问题 | 处理 |
|------|------|
| 双击 bat 报 Python 未找到 | 安装 Python 3.10~3.12 并勾选 PATH |
| 依赖安装慢/失败 | 脚本已用清华镜像，若失败会自动改 PyPI；或手动 `pip install -r requirements.txt` |
| 打开页面但模型空白 | 确认 `frontend/index.html` 存在；不存在则 `git submodule update --init --recursive` |
| 对话没声音 | 浏览器需授权麦克风；本地 TTS(edge-tts) 需联网 |
| 换电脑记忆不见了 | 检查 `QING_MEM_DIR` 是否指向你迁移的记忆文件夹 |

---

## 🔧 文件结构

```
open-llm-vtuber/
├── run_qing.py                 # 启动入口（含安全自检/记忆/人格注入）
├── 一键运行_小青.bat           # 一键运行（自动装依赖/启动）
├── conf.yaml                   # 配置（DeepSeek/ASR/TTS/Live2D）
├── .env                        # 你的 Key + 记忆目录（不入库）
├── .env.example                # 模板
├── memory_knowledge/           # 记忆库（dao/fa/shu/persona + 蒸馏盾）
├── src/open_llm_vtuber/
│   ├── memory_hub.py           # 三层记忆中枢
│   ├── persona_distiller.py    # 人格蒸馏器
│   └── security_guard.py       # 安全防护
└── distill_tool/               # 蒸馏引擎（immortal-skill 迁移）
```

---

*小青会越聊越懂你。记忆全在你手里，永不上传。*
