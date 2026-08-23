# 调研综述：从同事蒸馏到数字永生

> 本文档整理了 immortal-skill 项目的理论依据和调研来源。

## 一、被蒸馏成 Token 的现象

2026 年初，「被蒸馏成 Token」已从段子变成现实。离职员工的文档、代码注释、评审意见被切片向量化后，以隐匿的方式继续在组织里被调用。

**核心问题**：
- 无法区分事实依据和主观印象
- 冲突未处理——同一人不同时期的矛盾说法共存
- 伦理边界模糊——辅助对齐 vs 冒充真人

来源：[搜狐报道](https://it.sohu.com/a/1001511472_122535154)

## 二、知识蒸馏框架

### 2.1 Trace2Skill

从执行轨迹中蒸馏可迁移技能。核心思路：
- 多条轨迹并行分析优于逐条追踪
- 层次化合并消解冲突
- 声明式技能输出

本项目借鉴其「并行分析 + 层次合并」思路。

来源：[arXiv:2603.25158](https://arxiv.org/abs/2603.25158)

### 2.2 DPRF（动态人格精炼框架）

迭代式行为分析和人格精炼循环：
- 聚焦可观测行为而非性格标签
- 每轮精炼保留上一轮状态便于比较

本项目的纠正处理器和版本快照机制受此启发。

### 2.3 Five Questions 专家访谈法

结构化提取隐性知识：
1. 成功案例 → 做得好的模式
2. 失败案例 → 纠正过的错误
3. 决策依据 → 判断信号
4. Escalation 条件 → 边界意识
5. 新人易踩的坑 → Gotchas

本项目的程序性知识提取器直接基于此框架。

## 三、数字永生方案

### 3.1 Preserver

本地问卷（990+ 题）→ 汇总导出 JSONL 供模型训练。

启发：**主动采集结构化自我知识**弥补聊天记录的稀疏与噪声。

来源：[github.com/Gogolian/preserver](https://github.com/Gogolian/preserver)

### 3.2 Hexis

为 LLM 提供持久记忆与身份，多层记忆（情景/语义/程序性）。

启发：**记忆分层**比「只放一个长上下文」更可扩展。

来源：[github.com/QuixiAI/hexis](https://github.com/QuixiAI/hexis)

### 3.3 AI Persona Clone 流水线

社区共识流水线：
1. 导出聊天记录 → 清洗、脱敏、合并连续消息
2. 转为指令格式（user/assistant 对话轮次）
3. QLoRA/LoRA 微调或 RAG

本项目选择 RAG + 结构化提取路线（而非微调），因为：
- 数据量通常不足以支撑高质量微调
- 结构化提取的可解释性和可编辑性更好
- Agent Skill 格式天然支持按需加载

### 3.4 数字员工与知识永生

企业场景的孪生数字员工概念：
- 将员工的经验和技能建模为 AI 资产
- 提示词和 AI 配置也是公司财产，需要资产治理

来源：[CSDN](https://blog.csdn.net/2401_86594982/details/153396312)、[53AI](https://www.53ai.com/news/zhishiguanli/2025111585230.html)

## 四、多平台数据采集

### 4.1 国内平台

| 平台 | 采集方式 | 关键限制 |
|------|---------|---------|
| 飞书 | 开放 API（tenant_access_token） | 需企业自建应用 |
| 钉钉 | 开放 API（企业内部应用） | 调用频次限制 |
| 微信 | 本地 SQLite / 第三方导出工具 | 无官方 API |

### 4.2 国际平台

| 平台 | 采集方式 | 关键限制 |
|------|---------|---------|
| iMessage | macOS chat.db（SQLite） | 需 Full Disk Access |
| Telegram | Telethon（MTProto） | FloodWait 限流 |
| WhatsApp | 内置导出 / 备份解密 | 端到端加密 |
| Slack | Web API（Bot/User Token） | Plan 限制历史消息 |
| Discord | Bot API | ToS 限制自动化 |
| Email | mbox / Gmail API | OAuth 范围控制 |
| Twitter/X | 官方数据归档 | 生成耗时 24h+ |

### 4.3 通用归档

Google Takeout、Facebook 数据下载等提供标准 ZIP/JSON 归档。

## 五、Agent Skills 规范

[agentskills.io](https://agentskills.io/) 定义了 Agent Skill 的标准格式：
- `SKILL.md` 为入口，YAML frontmatter + Markdown body
- `name` 字段约束（小写、字母数字连字符）
- 渐进式披露：核心信息在 SKILL.md，详情按需加载
- OpenClaw 的 `metadata` 须为单行 JSON

## 六、OpenClaw 记忆蒸馏

OpenClaw 博文描述了记忆蒸馏 → Skill 固化 → 模型降级的路径：
- 情景记忆 → 结构化 SOP → 可执行 Skill
- Skill 支持「降级」到更小的模型运行

来源：[E 路领航博客](https://blog.oool.cc/archives/openclaw-memory-distillation-skill-solidification-model-downgrade)

## 七、伦理考量

### 7.1 同意与授权

- 蒸馏他人需要考虑对方是否知情/同意
- 聊天记录中包含第三方发言，需脱敏处理
- 已故亲人的蒸馏需要家庭成员知情

### 7.2 用途边界

- 辅助理解与培训 ≠ 冒充真人
- 数字分身不应被用于欺骗他人
- 公众人物蒸馏限于公开资料与可追溯出处，侧重方法论与表达框架

### 7.3 AI 资产治理

- 提示词和 AI 配置也是组织资产
- 需要版本管理、审计记录、访问控制
- 产物应存放在组织可管理的目录

## 八、设计原则总结

基于以上调研，immortal-skill 确立了 8 条设计原则：

1. **分路蒸馏**：按维度（procedure/interaction/memory/personality）独立提取
2. **证据分级**：三级证据标注，impression 隔离存放
3. **渐进式披露**：SKILL.md 极短，长内容按需读取
4. **角色适配**：7 种角色模板，不同维度组合与伦理要求
5. **多源融合**：12+ 平台统一采集接口
6. **资产可溯**：manifest.json 记录来源和指纹
7. **版本可回退**：快照机制支持纠正后回滚
8. **伦理先行**：每个角色有对应的伦理声明

## 引用索引

| # | 主题 | 来源 |
|---|------|------|
| 1 | 被蒸馏成 Token 的现象 | [搜狐](https://it.sohu.com/a/1001511472_122535154) |
| 2 | Trace2Skill | [arXiv](https://arxiv.org/abs/2603.25158) |
| 3 | OpenClaw 记忆蒸馏 | [E 路领航](https://blog.oool.cc/archives/openclaw-memory-distillation-skill-solidification-model-downgrade) |
| 4 | 工程师 Skill 撰写实战 | [掘金](https://juejin.cn/post/7619245854759583759) |
| 5 | 数字员工 & 知识永生 | [CSDN](https://blog.csdn.net/2401_86594982/details/153396312) |
| 6 | AI 知识管理 | [53AI](https://www.53ai.com/news/zhishiguanli/2025111585230.html) |
| 7 | AI 资产治理 | [掘金](https://juejin.cn/post/7597276695403462697) |
| 8 | Agent Skills 规范 | [agentskills.io](https://agentskills.io/specification.md) |
| 9 | Preserver 问卷式永生 | [GitHub](https://github.com/Gogolian/preserver) |
| 10 | Hexis 持久记忆 | [GitHub](https://github.com/QuixiAI/hexis) |
| 11 | WeClone 聊天克隆 | [GitHub](https://github.com/xming521/weclone) |
| 12 | WeChatMsg 微信导出 | [GitHub](https://github.com/LC044/WeChatMsg) |
| 13 | DiscordChatExporter | [GitHub](https://github.com/Tyrrrz/DiscordChatExporter) |
| 14 | Telethon Telegram 客户端 | [docs.telethon.dev](https://docs.telethon.dev/) |
