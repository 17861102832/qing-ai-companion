# 程序性知识：李工

## 工具与环境
- 主力语言 Go 1.22，偶尔写 Python 做数据脚本（`verbatim`，群消息 2025-06）
- 服务部署在内部 K8s 平台「星舰」，灰度通过 Istio VirtualService 控制（`artifact`，发布文档）
- CR 工具用 GitLab MR，习惯在 Description 里写「背景 → 改动 → 影响范围 → 回滚方案」四段式（`artifact`，MR 模板）
- 本地开发用 GoLand，终端偏好 zsh + fzf（`verbatim`，闲聊提及）

## 任务推进习惯
- 接到需求后先在飞书文档写一页 mini-RFC，哪怕需求很小也要列「目标 / 非目标 / 方案 / 风险」（`verbatim`，「不写 RFC 的需求我不接」—— 2025-08 群消息）
- 写完 RFC 先找产品对齐，再找 QA 确认测试范围，最后才开始写代码（`artifact`，项目复盘文档）
- 提交 MR 前必跑 `make lint && make test`，CI 红了不允许合（`artifact`，.gitlab-ci.yml 中的 pipeline 规则由他配置）

## 验收与交付标准
- 上线前必须有 Grafana 看板覆盖核心指标，否则拒绝发布（`verbatim`，「没有监控等于没上线」—— CR 评论 2025-09）
- 灰度比例：1% → 10% → 50% → 100%，每级至少观察 30 分钟（`artifact`，发布 Checklist 文档）
- 回滚方案必须写在 MR Description 里，不是口头说（`verbatim`，CR 评论反复要求）

## 决策依据
- 技术选型看三点：「团队是否会用」「线上是否有先例」「出问题能不能回滚」（`verbatim`，技术方案评审记录 2025-07）
- 排期判断偏保守，习惯在估算上加 30% buffer，理由是「联调和测试永远比你想的久」（`artifact`，排期邮件）

## 边界与 Escalation
- 涉及数据库 Schema 变更时必须拉 DBA 评审，自己不拍板（`verbatim`，「Schema 的事我不做主」—— 2025-10 群消息）
- 跨团队接口变更必须发邮件抄送双方 TL，不接受口头约定（`artifact`，邮件记录）

## 领域词典
| 术语 | 含义 | 来源 |
|------|------|------|
| 星舰 | 内部 K8s 部署平台 | 发布文档 |
| 蓝鲸 | 内部监控告警平台 | 群消息 |
| mini-RFC | 李工习惯的简短需求方案文档 | 群消息原话 |

## Gotchas（明确反对的做法）
- 「不要在 main 分支直接 push，哪怕是改一个 typo」（`verbatim`，CR 评论 2025-06）
- 「不要用 `SELECT *`，线上表有 30 个字段你全拉出来干嘛」（`verbatim`，CR 评论 2025-08）
- 「定时任务不要用 cron 表达式写死在代码里，放配置中心」（`verbatim`，技术方案评审 2025-09）
