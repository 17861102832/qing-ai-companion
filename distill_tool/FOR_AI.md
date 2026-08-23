# 给 AI / 给未来的自己：一键入口

克隆本仓库后，请把 **终端工作目录** 设为仓库根目录（文件夹名一般为 `immortal-skill/`；若你改名了，以根目录的 `SKILL.md` 与 `kit/` 为准）。

下面四段可 **整段复制** 到 Cursor / Claude / OpenClaw 对话里；每段对应一套能力，**互不影响**，按需选用。

---

## ① 数字永生（通用引擎）

**任务**：按「多角色、多平台、四维蒸馏」生成数字分身 Skill 包。

**请先完整阅读**（本仓库根目录）：

- [`SKILL.md`](SKILL.md)

**说明**：采集与封包 CLI 在 `kit/immortal_cli.py`；角色模板在 `personas/`。执行本文件中的 Phase 顺序即可。

---

## ② 蒸笼（叙事入口，同一套引擎）

**任务**：用「蒸笼」叙事带用户完成蒸馏；技术步骤与根目录 `SKILL.md` 一致，委托上级 `kit/`。

**请先完整阅读**：

- [`steamer-skill/SKILL.md`](steamer-skill/SKILL.md)

**人读故事**（可选）：[`steamer-skill/README.md`](steamer-skill/README.md)

**说明**：蒸馏时同时引用根目录 [`SKILL.md`](SKILL.md) 的 Phase 与 `python3 kit/immortal_cli.py ...`（路径均相对仓库根）。

---

## ③ Distill Shield（移交包加固）

**任务**：为有权处置的资料包生成 Canary 与清单，提高未授权蒸馏成本。

**请先完整阅读**：

- [`distill-shield-skill/SKILL.md`](distill-shield-skill/SKILL.md)

**从仓库根运行脚本**（推荐，路径无歧义）：

```bash
python3 distill-shield-skill/kit/shield_gen.py --output ./handover-bundle --label "我的移交包"
```

---

## ④ Distill Protocol（蒸馏协议 / 梗名「牛马保护法」）

**任务**：生成 `LICENSE-DISTILL.md` 与 `manifest.json`，声明资料包使用范围。

**请先完整阅读**：

- [`distill-protocol-skill/SKILL.md`](distill-protocol-skill/SKILL.md)

**从仓库根运行脚本**：

```bash
python3 distill-protocol-skill/kit/protocol_gen.py --owner "你的名字" --tier human_only --output ./my-protocol
```

`--tier` 可选：`human_only` | `no_commercial_distill` | `research_ok`

---

## 一句话总控（整仓）

```
工作目录在 immortal-skill 仓库根。请根据用户意图，只打开 FOR_AI.md 里对应段落指向的 SKILL.md 并严格执行；需要脚本时，使用本文件中「从仓库根运行」的 python 命令。
```
