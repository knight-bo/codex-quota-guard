# codex-quota-guard

版本 0.1.1：修复审查问题，替代存在模拟准入漏洞的 0.1.0。

实验性的建议型 Codex 额度监控 CLI，运行时仅依赖 Python 标准库。非 OpenAI 官方产品。
默认只读告警，支持合成数据回放；不会自动登录、读取凭据文件、购买额度、
兑换重置次数或改变安全配置。凭据仅由官方 Codex 子进程处理。

## 安装和验证

需要 Python 3.10+、Linux/macOS。实时模式需要已安装的官方 Codex CLI，以及
现有可用账户认证。构建安装使用 setuptools，运行时没有第三方依赖。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/codex-quota-guard simulate --bucket demo \
  --fixture fixtures/demo.jsonl --state-dir /tmp/quota-demo
```

fixtures 完全是合成数据，不代表真实账户查询。回放不会中断任务；从第一次写入开始，所有快照都标记 synthetic 并拒绝真实
准入，包括异常或中断期间。假设决策仅在 simulated_allow_new_work 中展示。
check 必须看到明确的 live 来源，缺少来源标记的旧快照也会被拒绝。

## 实时只读监控

```sh
codex-quota-guard read --bucket codex --state-dir /tmp/quota-live
codex-quota-guard watch --bucket codex --threshold 10 --buffer 2 \
  --interval 30 --max-age 90 --state-dir /tmp/quota-live
codex-quota-guard check --bucket codex --state-dir /tmp/quota-live
```

必须明确指定实际工作适用的额度桶。示例中的 codex 不是自动选择或通用模型映射。
多桶信息存在时优先采用；旧单桶视图必须具有匹配的 limitId，否则阻止新工作。
不同桶使用不同状态目录，任务所需的所有桶都必须通过检查。

剩余额度 = 100 − usedPercent。默认 10% 阈值加 2 个百分点缓冲，即任一适用
窗口剩余不超过 12% 时阻止新工作。检查 primary 和 secondary；明确 null
表示不适用，字段缺失表示未知。额度窗口不同于上下文长度或 token 使用量。
读数缺失、异常、过期、错误、已达到限制或重置时间已到，都不会放行。
时间到达不意味着额度自动恢复，必须重新读取。通知只使缓存失效；下一轮轮询
重新查询。同一重置时间内用量下降、重置时间倒退、原有窗口消失都保守阻止。
真实的同周期额度调整也可能因此持续被阻止，应人工核实，不自动清除状态。

状态目录必须属于当前用户、权限 0700、父目录可信。监控进程持有单写入锁，
check 可并发读取原子快照，且必须使用相同策略参数。连接错误按指数退避加抖动
重试，最长 60 秒。退出正常撤销准入；异常崩溃后快照可能到有效期才失效，
需要严格存活保证的调度器还应监督监控进程。每个工作单元开始前执行 check，
但它不是原子额度预留，也不能防止其他客户端同时消耗额度。

read/check 通过时退出 0，否则 2；simulate 成功完成回放退出 0，与回放中是否
低额度无关；Ctrl-C 退出 130。输出仅包含白名单字段，不输出服务器原始通知、
错误详情、账户标识或任务 ID。

## 显式受管任务中断

只有调度器明确拥有、且当前 app-server 可访问的 thread/turn 才能绑定：

```sh
codex-quota-guard watch --bucket codex --state-dir /tmp/quota-managed \
  --managed-thread YOUR_OWN_THREAD_ID --managed-turn YOUR_OWN_TURN_ID \
  --allow-interrupt
```

不加 allow-interrupt 只报告 would_interrupt。绑定精确 thread/turn，不枚举
研究任务，不搜索 PID，不向研究进程发送系统信号。CLI 启动自己的 stdio
app-server，并不接入现有托管云会话；该连接无法访问任务时不能中断。
库适配器可供拥有相应会话的调度器集成。

中断前持久化意图并写建议性的 checkpoint 请求。本版本不核验保存 ACK，
也不等待保存后再中断；checkpoint_status 始终为 unconfirmed。每个绑定只尝试一次，超时/崩溃
保留 pending_unknown，不自动重试。interrupt_acknowledged 仅说明 RPC 接收，
不证明 turn 已结束或 checkpoint 已保存。调度器仍需观察 turn/completed 并
确认自己的工作进程。本版本没有实现该完成确认。turn/interrupt 不保证杀死
脱离会话的子进程，也不控制任意托管云研究任务。

详细协作契约见 [架构说明](docs/ARCHITECTURE.md)，安全边界见
[安全审查](docs/SECURITY.md)，测试证据见 [验证说明](docs/VALIDATION.md)。
采用 [MIT 许可证](LICENSE)，版权所有 (c) 2026 knight-bo。
[官方协议文档](https://learn.chatgpt.com/docs/app-server)。

协议写入使用非阻塞 I/O 和超时；响应 ID 必须为精确整数。返回响应前处理
已缓冲及立即可读的通知，未完整的待处理帧保守拒绝。已缓冲响应也不能超过
截止时间。检查边界之后新到达的通知仍存在轮询竞态，不能提供原子额度预留。
