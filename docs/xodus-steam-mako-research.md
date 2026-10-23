# Xodus Nexus 游戏直接从 Steam 游戏模式启动并使用 MAKO

研究日期：2026-10-23（Pacific/Auckland）。源码核对版本：Xodus Nexus `v0.3.11`、MAKO `plugin-v4.6.0`。本文是研究记录；没有安装、修改或启动掌机上的游戏来验证兼容性。

## 结论与建议

**可以不先打开 Nexus 主界面，直接在 Steam 游戏模式点击单个游戏。** Nexus 已有官方的逐游戏 Steam 快捷方式和 `--launch-game` 启动入口。它启动的是后台运行的 Nexus 会话，不是绕过 Xodus：账户检查、授权、游戏包准备、专用运行时、前缀和云存档服务仍保留。出错或需要交互时仍可能弹出 Nexus 界面或系统钱包窗口。[快捷方式源码](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-shortcuts.ts)、[启动与服务生命周期](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/index.ts)

**推荐方案：导出每个游戏的 Steam 快捷方式，在 Nexus 的该游戏启动选项里添加 `/home/deck/.local/bin/mako-run %command%`。** 这是从两边官方源码推导出的接入方案，尚未在这台掌机游戏内验证；不能把“语法支持”说成“已经补帧成功”。Nexus 的 `prepareGameWrapper` 专门包装游戏 Wine 入口，账户服务、前缀准备和停止命令都在包装器之外；MAKO 文档要求第三方启动器使用逐游戏 wrapper/prefix。[Nexus 包装器](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-wrapper.ts)、[MAKO 第三方启动器指南](https://github.com/eugeniosegala/MAKO/blob/plugin-v4.6.0/plugin/docs/LAUNCHERS.md)

不要将游戏 exe 直接交给普通 Steam Proton 作为等价替代：Nexus 的实际路径要求当前受管理 backend，使用 `run <game-path> <prepared-wine> --exe <manifest-executable> --materialize-chain`，还负责 Xodus 服务与其专用 runtime。[游戏启动参数](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-launch.ts)、[运行时准备](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/proton.ts)

## 已核实的源码行为

- `game-shortcuts.ts` 生成持久的 `shortcuts/launch-game`，执行 AppImage `--nexus-profile <profile> --launch-game <16位游戏ID>`。Steam 项目目标为 `/bin/sh`，参数包括此脚本和游戏 ID；应保留这一原生 Linux 目标，不额外强制 Steam Proton。[源码](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-shortcuts.ts)
- `index.ts` 在存在启动游戏 ID 时令 `shortcutOnly=true`，初始化 backend/runtime、刷新账户后直接接收启动请求，不先调用普通主窗口路径；游戏完成和服务清理完成后自动退出。错误会转入 `showLauncher()`。重复请求同一个活动游戏会合并，另一个游戏已启动时拒绝新的启动。[主流程](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/index.ts)、[请求串行化](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/shortcut-launch.ts)
- `launchTools.launchOptions` 支持前置程序、环境变量与独立的 `%command%` 标记，路径应写绝对路径；它不是 shell，不支持管道、命令替换或通用 shell 语法，`~` 也不会由 shell 展开。不能覆盖 Nexus 管理的 `WINEPREFIX`、`WINEARCH`、`XODUS_*`、`STEAM_COMPAT_*`。[解析器](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/shared/launch-tools.ts)
- 若同时勾选 Nexus 的 Gamescope/MangoHud，实际顺序是自定义 prefix → Gamescope/MangoHud → Wine。游戏模式本身已有 Gamescope，因此第一轮验证宜关闭额外嵌套 Gamescope 和 Nexus MangoHud，使用现有 MAKO/HUD 配置，避免额外变量和重复监控。这是验证建议，不是所有游戏通用的兼容性要求。[包装器顺序](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-wrapper.ts)

## 为什么 MAKO 优先放在逐游戏设置

Nexus 的环境清理没有统一删除 MAKO 或 Vulkan 层变量：`externalLauncherEnvironment` 只恢复字体与 Steam IME；`gameWindowEnvironment` 清除 Electron 桌面身份、APPIMAGE/APPDIR 等；Proton wrapper 重设自身库路径与 Wine 环境。因而把 MAKO 包在 Steam 快捷方式最外层，首次冷启动时可能继承所需变量，但还不能保证 AppImage/运行时整体兼容。[子进程环境](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/process.ts)、[启动器环境](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/launcher-environment.ts)、[游戏窗口环境](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-log.ts)、[Proton wrapper](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/proton.ts)

更关键的是，Nexus 已运行时，第二实例经 singleton handoff 只传递 `gameId/profile`，不会把新的启动进程环境整体传进旧进程。仅在外层添加 MAKO 会依赖 Nexus 是否已经运行，逐游戏 Wine wrapper 可避免这个问题，并避开 Electron 主界面和账户服务。[实例交接](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-shortcuts.ts)、[主进程交接](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/index.ts)

## Steam 是否需要退出或重启

`v0.3.11` 已有 live import：Steam 运行时通过原生 `steam://addnonsteamgame/` 和 `/tmp/addnonsteamgamefile` 握手，由 Steam 导入并回读其分配的快捷方式 ID。**不需要一概要求先退出或重启 Steam。** Steam 未运行时才直接更新 VDF，该路径在写入前再次要求 Steam 完全退出，并保存备份。若离线导出，则下次启动 Steam 加载；live import 超时不能当作成功。[运行时导入](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/steam-live.ts)、[离线写入](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/steam-shortcuts.ts)、[两种路径选择](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/index.ts)

## MAKO 适用范围与待验证事项

MAKO 4.6 需要 Vulkan；兼容的 DirectX 游戏通过 DXVK/VKD3D 可满足这一前提，DX12 本身不是排除条件。OpenGL 需另外考虑 Zink，不能假定所有 Xodus 游戏都兼容。补帧和 LS1 还需要已有合法 Lossless Scaling 安装；MAKO Scaler 和 shaders 不需要。[官方 4.6 指南](https://github.com/eugeniosegala/MAKO/blob/plugin-v4.6.0/plugin/docs/LAUNCHERS.md)、[4.6 README](https://github.com/eugeniosegala/MAKO/blob/plugin-v4.6.0/README.md)

实际部署后应确认：Steam 中确实出现单游戏条目；启动时不要求手动点 Nexus Play；钱包/账户能正常解锁；游戏进程实际加载 MAKO Vulkan 层；MAKO Live Status 报告 FG 活动、正确分辨率与倍率；退出后 Steam 正常停止、存档正常。不能仅凭 FPS 变高或启动参数存在判定补帧成功。游戏进程匹配和 Steam 非 Steam App ID 可能影响 MAKO profile，需使用实际可执行进程匹配核实。[MAKO profile 与启动要求](https://github.com/eugeniosegala/MAKO/blob/plugin-v4.6.0/README.md)

## 掌机只读检查记录（来自主任务）

主任务已核实掌机 AppImage 为 `0.3.11`、哈希与官方一致；现有 `~/.config/xodus-nexus/shortcuts/launch-game` 指向此 AppImage 并使用上述官方参数；存在 launcher 快捷方式但未看到逐游戏 `.desktop` 导出。该记录只说明接入基础已具备，不代表游戏模式或 MAKO 已做运行验证。没有在此文写入账户、凭据、令牌或私密日志。

掌机当前只有一个 ready 游戏：**Nobody Saves the World**，主程序为 `Game.exe`，现未设置 `launchTools`；已有 Nexus 管理的专用 Wine runtime，且 `/home/deck/.local/bin/mako-run` 存在。建议的实际使用流程是：一次性在 Nexus 的该游戏设置中配置上述 MAKO 启动选项，再从该游戏菜单 **Add to Steam** 导出；以后回到 Steam 游戏模式，直接点击 **Nobody Saves the World** 启动，Nexus 在后台完成必需准备。保留 Steam 快捷方式的 `/bin/sh` 目标，不勾选强制 Steam Proton；初次验证不启用 Nexus 额外 Gamescope。具体游戏在 MAKO 4.6 下是否成功补帧仍未实测。[游戏菜单快捷方式与运行时职责](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/README.md)、[逐游戏 wrapper](https://github.com/domsvoboda/xodus-nexus/blob/v0.3.11/src/main/game-wrapper.ts)
