# 安装与使用插件（0.4.0）

这是独立的本地技能插件，非 OpenAI 官方产品。需要 Linux/macOS、Python 3.10+
和已安装、已认证的官方 Codex CLI。插件通过随包 Python 脚本运行，无需 pip 安装。
安装插件不会启动监控，也不会更改账户认证或安全设置。

## 从本地仓库安装

1. 将完整仓库放到可信本地目录，保留隐藏目录及 scripts、quota_guard、skills。
2. 在仓库根目录运行：

   ```sh
   codex plugin marketplace add .
   codex plugin marketplace list
   ```

3. 重启 ChatGPT 桌面端，在插件目录的本地来源 “Codex Quota Guard Local” 中安装
   并启用 “Codex Quota Guard”，然后在新对话中测试。

随包 `.agents/plugins/marketplace.json` 的 `source.path` 为 `./`，指向仓库根目录。
根目录 `plugin.json` 是可移植入口，`.codex-plugin/plugin.json` 提供兼容入口。
更新代码后刷新对应 marketplace 并重启客户端；确认安装副本包含新版文件。
客户端及管理员策略可能限制本地来源，CLI 注册成功不等于桌面安装已验证。

GitHub 仓库公开并可访问后，也可注册仓库来源：

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

此命令注册来源；GitHub 发布不代表已上架公共插件目录。公共目录需要另行提交审核。
本地安装方式依据[官方插件打包说明](https://developers.openai.com/plugins/build/plugins)。

## 自然语言使用

- “查看 Codex 剩余额度”：只查询一次。
- “启动 Codex 额度监控，保留 10%，缓冲 2 个百分点，每 30 秒检查”：明确启动轮询。
- “查看额度监控的缓存状态”：报告缓存时间、是否过期和各窗口数值。
- “停止额度监控”：向该监控的状态目录发送停止请求，并确认原进程退出。

需要指定独立、私有、可写的状态目录，放在插件缓存和仓库之外；监控、检查和停止
使用同一目录。不要通过修改已有目录权限、CODEX_HOME 或认证设置来绕过错误。

监控为前台进程，必须保留受监督的执行会话；不安装后台守护进程或开机启动项。
默认阈值为 10% + 2 个百分点，即任一适用窗口剩余不超过 12% 时拒绝新工作。
这是检测与协作准入，不保证硬性保住 10%，也不能控制任意云任务。

## 手动调用与验证

在仓库根目录，把 STATE 替换为你选择的私有绝对路径：

```sh
python3 scripts/quota_guard.py --help
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE
# 在另一个终端中执行：
python3 scripts/quota_guard.py check --bucket codex --reserve 10 --buffer 2 --state-dir STATE
python3 scripts/quota_guard.py stop --state-dir STATE
```

不要原样使用 STATE 占位符。插件技能会使用安装位置解析出的绝对脚本路径，无需切换目录。
check 只读缓存，不能代替实时查询；须与产生快照时的策略一致。缺失、过期或无效
数据保守拒绝。停止请求被接受不代表原进程已退出，需要检查该执行会话。

若 app-server 被权限限制，走正常审批流程；不要放宽沙箱或读取凭据、会话日志。
单独的 stderr PATH 警告不代表查询失败，以握手和匹配额度响应为准。

## 多语言报告

使用 `--format text --locale zh` 可显示中文报告。默认 JSON 保持机器接口不变。
其他八种语言、区域语言回退规则及安装说明见[语言入口](LANGUAGES.md)。

## 自选检测线与“暂停”的边界

可以选择 5%、10%、20%、30% 等剩余额度。`--reserve` 范围为 0–100，
`--buffer` 非负，二者之和不能超过 100；默认 buffer=2。
例如 reserve=20、buffer=0 表示读到剩余不超过 20% 时触发；buffer=2 则是 22%。

- “只查询一次，以剩余 5%、缓冲 0 为检测线”：read，不启动监测。
- “启动监测，剩余 20%、缓冲 0、每 30 秒检查”：仅显式启动监测和协作准入检查。
- “把当前监测改成剩余 30%、缓冲 2”：先停止并确认原监测退出，再按新参数启动。
- “仅授权在触发检测线时，中断调度器拥有且当前连接可访问的 thread T / turn U”：
  只有真实目标及访问能力已核实，才可显式启用 managed 模式；T/U 是示意占位符。

“低于某额度暂停”若没有明确目标，不能据此启用任意任务中断。先说明检测/协作停止
与真实中断不同并确认目标。`--allow-interrupt` 的真实中断闭环尚未验证；普通插件
进程另启 app-server，不会接管现有桌面或云会话。详见[受管中断范围](MANAGED-INTERRUPT.md)。
中断也不是可恢复的 pause/resume API，不代表已保存。

轮询间隔、RPC 延迟、失败重试和其他客户端消费都可能使触发滞后。buffer=0 是精确
检测线，不是恰好在该百分比停止的保证，更不是硬保留额度。
本轮仅通过 GitHub 分发，不进行官方目录上架。人机确认流程见[确认工作流](CONFIRMATION-WORKFLOW.md)。

任意比例确认流程使用 `--target`，不要把旧 `--reserve` 准入策略误当任务暂停：例如
`--target 80 --warn-margin 2 --confirm-margin 1 --task-key VERIFIED_TASK`。
37.5 等小数也有效；默认剩余82提醒、81询问，到80拒绝新准入但不自行暂停任务。
VERIFIED_TASK 为实际已核实任务标识的示意，不能原样使用。先确认宿主
能保持受监督后台会话并接收事件；不支持时只做单次查询，不承诺持续提醒。
