# 协议生成流程摘要

1. 选档位：`human_only` / `no_commercial_distill` / `research_ok`。
2. 填所有者名称。
3. 运行 `python3 kit/protocol_gen.py --owner "…" --tier … --output ./bundle`。
4. 将 `LICENSE-DISTILL.md` 与 `manifest.json` 与资料包放在同一目录并在 README 中声明。
