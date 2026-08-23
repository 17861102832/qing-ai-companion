# 蒸笼流程 · 与主仓库对齐

本 Skill **不重复实现** 采集与蒸馏算法，一律 **委托** 仓库根目录的 `immortal-skill` 主体。

## 引擎位置

- 蒸馏器入口：`../SKILL.md`
- 角色模板：`../personas/<role>.md`（公众人物见 `../personas/public-figure.md`）
- 采集与 CLI：`../kit/immortal_cli.py`
-  intake：`../recipes/intake-protocol.md`

## 蒸笼的差异化

- **叙事**：面向国内用户，强调「蒸馒头」生活意象与「蒸馏任何人」一句话。
- **默认心智**：优先引导用户想清楚 **材料是否公开、是否可追溯**；公众人物场景必读 `public-figure` 模板。

## 产出物

与主仓库一致：生成 `./skills/immortals/<slug>/` 下的多维度 Markdown + `manifest.json`，详见根 `SKILL.md` Phase 5–6。
