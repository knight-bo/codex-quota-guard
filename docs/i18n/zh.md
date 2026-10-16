# 中文安装与使用指南

Codex Quota Guard 提供建议性的额度查询和监控。需要 Python 3.10+、POSIX 系统（Linux/macOS），以及已安装、完成正常身份验证且账户符合使用条件的官方 Codex CLI。运行时只依赖 Python 标准库。请使用可信 PATH 中的官方程序。

## 安装

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

执行后重启桌面应用，选择 Codex Quota Guard Local，安装并启用。GitHub 发布不代表获得公共插件目录审批。安装不会启动监控，也不会配置自动启动或定时任务。

## 查询、启动与停止

可以说：“查看 Codex 剩余额度”“启动额度监控，预留 10%，增加 2 个百分点缓冲，每 30 秒检查一次”或“停止额度监控”。单次查询不会启动持续监控。

以下命令从插件根目录运行。将 STATE 替换为同一个可信、私有、由当前用户拥有的状态目录的绝对路径；其权限应为 0700，位于仓库和插件缓存之外，父目录必须可信且可写。

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale zh
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale zh
```

只有明确请求才启动监控。start 在前台运行，不是后台守护进程；请保留并监督该会话。停止时在另一终端使用相同状态目录：

```sh
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale zh
```

随后检查原会话，确认进程确实退出；停止请求本身不是退出证明。也可在前台按 Ctrl-C。

## 结果与安全边界

该配置在任一适用周期剩余量低于或等于 12% 时阻止新任务的建议性许可，不保证精确保留 10%。其他客户端仍可能消耗额度。分别查看各周期及观测时间；缓存、过期或无效的读数不能视作当前余额。重置时间已过也需要重新读取。codex 是显式选择的额度类别，不能假定适用于所有模型。

默认仅查询和提醒，不中断任务。任何受管中断都需要明确授权，且必须限定为编排器拥有、当前 app-server 可访问的确切 thread/turn。它不能控制任意云端任务；检查点状态为 unconfirmed，中断确认也不代表任务完成或检查点保存成功。访问失败时使用正常审批和登录流程，勿更改权限、认证配置或 CODEX_HOME 来绕过限制，也勿直接读取凭据文件或会话日志。

更多信息：[主说明](../../README.md) · [语言支持](../LANGUAGES.md)
