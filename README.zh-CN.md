# codex-quota-guard

版本 0.5.0。实验性的建议型 Codex 额度查询与监控插件，运行时只依赖 Python 标准库，
非 OpenAI 官方产品。[安装指南](docs/PLUGIN-INSTALL.zh-CN.md) · [English](README.md)

[九语言安装与使用入口](docs/LANGUAGES.md)。人类可读报告使用 `--format text --locale zh`；
默认 JSON、协议字段、状态文件和退出码保持不变。语言支持不代表所有地区均可使用。

## 能做什么

- “查看 Codex 剩余额度”：单次读取，不启动监控
- “监控这项任务，剩余额度到 80% 时先问我是否暂停”：绑定已核实任务并输出确认事件
- “启动监控，保留 10%，缓冲 2 个百分点，每 30 秒检查”：使用独立的旧版准入模式
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

MIT 许可证，见 [LICENSE](LICENSE)。Copyright (c) 2026 knight-bo。仅通过 GitHub 下载分发，保持桌面端限定；安装不会启动监控或研究任务。
[架构说明](docs/ARCHITECTURE.md) · [验证记录](docs/VALIDATION.md) ·
[安全说明](docs/SECURITY.md)

## 任意剩余额度目标与确认

用户可以用自然语言选择 0–100 范围内任意有限数值，例如“剩余到 80% 时先问我是否暂停此项任务”。
80 就是实际目标，不限于固定档位，也不是已用 80%。核实具体任务的稳定身份后，可运行：

```sh
python3 scripts/quota_guard.py start --bucket codex --target 80 --warn-margin 2 --confirm-margin 1 --task-key VERIFIED_STABLE_TASK_KEY --interval 30 --max-age 90 --state-dir STATE
```

STATE 须替换为可信私有绝对路径；任务键必须来自已核实的任务上下文，不能猜测。
输出和持久状态只保留任务键的哈希绑定，不输出原始任务 ID。CLI 默认 JSON 供宿主 AI 解读，
只发出带版本的事件，不负责确认用户收到消息、获得同意或暂停任务。

- 剩余不超过 82%：预警
- 剩余不超过 81%：confirmation_required；宿主问“到80%时暂停此项任务吗？”
- 剩余不超过 80%：target_reached，仍不能凭此自动执行暂停
- 首次有效读取就已经不超过 80%：立即发出确认与到达事件，改问“当前已到或低于80%，现在暂停此项任务吗？”，不能再问未来是否到达

两个 margin 都是百分点，须为 0–100 的有限非负数，warn-margin >= confirm-margin；
目标加 margin 超过 100 时，实际触发线封顶 100。目标模式拒绝 --allow-interrupt。
用户批准必须对应这个已核实的具体任务、目标值和可访问的受支持控制方式。
事件不证明用户已看到、同意，或任务已暂停，也不提供任意云任务控制能力。

宿主必须在受监督的后台会话保持监控进程，同时继续接收用户消息。如果无法同时做到，
应说明持续监控会阻塞交互，仅提供单次查询，不承诺持续监控。不要为测试而启动研究。
同一任务/目标的事件去重记录跨重启保留；额度上涨或重置不自动恢复任务。
改变目标或其他监控配置需要新的明确监控约定，先停止并核实旧进程退出，再重启。
用户取消时停止监控，并核实退出。

旧版 reserve/buffer 准入与目标确认是独立机制：例如 reserve=80、buffer=0 在剩余
不超过 80% 时拒绝协作式新工作；buffer=2 则在 82% 触发。两种模式都不能保证恰好
在目标余额停止消耗。详见[确认工作流](docs/CONFIRMATION-WORKFLOW.md)和
[受管中断范围](docs/MANAGED-INTERRUPT.md)。

达到目标后还会锁定拒绝协作式新工作（allow_new_work=false、confirmation_target_reached），
跨额度回升和重启保留；这不证明任务已暂停。只有用户明确要求新一轮监控且旧进程已退出时，
才使用 --new-cycle 清理事件记录与准入锁定；它不代表批准或恢复任务，首次启动无需此参数。

支持 37.5 等小数目标；100% 目标在剩余 100% 时也可能立即询问，0% 目标不能防止额度耗尽。
目标参数支持 read/start/watch/check，不支持 CLI simulate。目标模式 check 须使用相同任务键、
目标和 margins；它返回 events=[]，宿主应结合缓存阶段和真实对话恢复待答问题，不能将事件去重当作送达保证。


目标模式直接按用户选择的剩余百分比决定准入，buffer固定为0，提醒/确认提前量不改变
到线值；不可与旧reserve/threshold/buffer参数混用。旧10%默认不会覆盖用户选的比例。

## 可选的 Tibo 公共重置公告提醒

独立的 `resetwatch` 不需要账户、API key 或额外通知权限。可区分 planned（计划）、
completed（第三方记录的完成公告）、banked（储存型重置额度，收到与兑换未确认）和
manual_credit（手动补偿公告）。始终保留原帖 URL／ID、发布时间、来源与核验声明。
公共公告不能证明个人额度到账，也绝不自动恢复、暂停研究或清除额度目标锁。

```sh
python3 scripts/quota_guard.py resetwatch --help --locale zh
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE --format text --locale zh
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE --format text --locale zh
```

将 PUBLIC_STATE 换为仓库／缓存外的私有绝对父目录。公告状态使用独立子目录，不改动
账户额度监测。首次成功只建立基线，不轰炸历史；去重跨重启保存，planned→completed
只提醒新状态。默认每小时轮询，冷却和有界退避均持久保存；网络失败、来源过期、格式
或来源错误只表示未知。宿主须消费 JSON 并调用已有本地通知适配器；事件不代表已送达。
停止后还须确认原进程退出；休眠、退出、网络和来源延迟会影响监测，不保证实时。
默认使用固定 ModelYard 公共 RSS，已移除 HTML 和任意地址入口。抓取时间与来源事件日期
分开，覆盖未知；同帖分类更新标为本地观察。已测提供的真实裁剪样本；本机在线抓取仍受阻。
robots 不等于版权许可，不能声称来源授权再分发。
[中文完整用法与插件指引](docs/i18n/zh.md) · [配置与 JSON 约定](docs/RESET-WATCH.md) ·
[来源核查与发布限制](docs/RESET-SOURCES.md)。
