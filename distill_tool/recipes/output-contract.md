# 生成物目录约定

> 每个被蒸馏的对象对应一个子目录。
> `slug` 遵循 Agent Skills 规范：仅小写字母、数字、连字符，与 `SKILL.md` 的 `name` 一致。

## 按角色的文件结构

### 全量角色（自己）

```
<slug>/
├── SKILL.md          # 入口 (< 100 行)
├── procedure.md      # 程序性知识
├── interaction.md    # 互动风格
├── memory.md         # 记忆与经历
├── personality.md    # 性格与价值观
├── conflicts.md      # 矛盾裁定
└── manifest.json     # 元数据
```

### 职场角色（同事）

```
<slug>/
├── SKILL.md
├── procedure.md
├── interaction.md
├── conflicts.md
└── manifest.json
```

### 关系角色（亲人/伴侣/朋友）

```
<slug>/
├── SKILL.md
├── interaction.md
├── memory.md
├── personality.md
├── conflicts.md
└── manifest.json
```

### 导师 / 公众人物

```
<slug>/
├── SKILL.md
├── procedure.md      # 教学/公开方法论
├── interaction.md    # 教学/公开互动风格
├── memory.md         # 分享的经历/公开故事
├── personality.md    # 教学理念/公众形象
├── conflicts.md
└── manifest.json
```

## `SKILL.md` frontmatter

```yaml
---
name: <slug>
description: "<description from persona template>"
license: MIT
metadata: {"ethics_note": "<ethical_status>", "kit": "immortal-skill", "persona": "<persona_type>", "evidence": "<evidence_stats>", "platforms": ["<source_platforms>"]}
---
```

- `name` 必须与目录名一致
- `metadata` 须为**单行 JSON**（OpenClaw 解析器要求）
- `ethics_note` 取值：
  - `assistive-simulation-only`（同事/导师）
  - `personal-memorial`（亲人/伴侣/朋友）
  - `self-backup`（自己）
  - `public-research-only`（公众人物）
- `persona` 标明角色类型
- `evidence` 简要记录各维度的证据分布
- `platforms` 列出数据来源平台

## `manifest.json` 字段

```json
{
  "slug": "<slug>",
  "persona": "<persona_type>",
  "built_at": "<ISO 8601>",
  "sources_summarized": ["<source_labels>"],
  "platforms": ["feishu", "wechat", "..."],
  "kit": "immortal-skill",
  "dimensions": ["procedure", "interaction", "memory", "personality"],
  "fingerprints": {
    "SKILL.md": "<sha256>",
    "procedure.md": "<sha256>",
    "...": "..."
  }
}
```

## 质量自检

- [ ] `name` 与目录名一致且符合命名规则？
- [ ] 必需文件是否齐全（按角色检查）？
- [ ] `metadata` 确实是单行 JSON？
- [ ] `ethical_status` 与角色匹配？
