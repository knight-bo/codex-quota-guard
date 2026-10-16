# 安装与使用插件（0.2.0）

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
