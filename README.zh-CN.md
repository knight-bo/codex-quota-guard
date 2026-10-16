# codex-quota-guard

版本 0.3.0。实验性的建议型 Codex 额度查询与监控插件，运行时只依赖 Python 标准库，
非 OpenAI 官方产品。[安装指南](docs/PLUGIN-INSTALL.zh-CN.md) · [English](README.md)

[九语言安装与使用入口](docs/LANGUAGES.md)。人类可读报告使用 `--format text --locale zh`；
默认 JSON、协议字段、状态文件和退出码保持不变。语言支持不代表所有地区均可使用。

## 能做什么

- “查看 Codex 剩余额度”：单次读取，不启动监控
- “启动监控，保留 10%，缓冲 2 个百分点，每 30 秒检查”：启动显式前台轮询
- “查看缓存状态”：显示观测时间、过期状态和各适用额度窗口
- “停止额度监控”：协作请求停止，并检查原进程退出

read / start（watch 别名）/ check 使用相同的明确额度桶和私有状态目录。
stop 只需同一个 --state-dir。
--reserve 是 --threshold 的别名。状态目录必须位于插件缓存、源码仓库之外的可信
可写位置，归当前用户所有且权限为 0700；不得修改已有权限来绕过失败。

## 重要边界

默认剩余不超过 12%（10% 保留 + 2 个百分点缓冲）就拒绝新工作。所有适用窗口
都必须通过；剩余 = 100 − usedPercent，不是上下文或 token 用量。缺失、无效、
过期或失败的读数均拒绝准入；重置时间到达后必须重新读取，不能自动视为恢复。

这是协作式准入检查，不能原子预留额度。其他客户端、在途工作、网络延迟都可能
继续消耗额度，所以检测到阈值不代表硬性保住 10%。调度器须在每个工作单元前
执行 check，并监督监控进程；异常退出后的缓存可能到有效期才失效。

不自动登录、购买额度、兑换次数、读取凭据/会话日志、改变 CODEX_HOME 或安全设置。
认证只由官方 Codex 子进程处理。权限问题应走正常审批流程。

只读监控不停止研究任务。中断需要明确授权且绑定调度器拥有、当前 app-server
可访问的精确 thread/turn；本插件不控制任意托管云任务。checkpoint_status 始终为
unconfirmed，RPC 确认不代表任务已结束或进度已保存；须由拥有任务的调度器另行验证。

## 测试与许可证

```sh
python3 -m unittest discover -s tests -v
python3 scripts/quota_guard.py simulate --bucket demo --fixture fixtures/demo.jsonl --state-dir STATE
```

STATE 为所选私有绝对路径。模拟数据完全合成；任何 synthetic 快照都不能允许真实
工作。simulate 的成功退出只代表回放完成。真实 read/check 通过时退出 0，否则 2。

MIT 许可证，见 [LICENSE](LICENSE)。Copyright (c) 2026 knight-bo。GitHub 源码发布与公共插件目录上架是不同步骤。
[架构说明](docs/ARCHITECTURE.md) · [验证记录](docs/VALIDATION.md) ·
[安全说明](docs/SECURITY.md)
