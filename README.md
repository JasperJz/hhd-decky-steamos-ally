# HHD Decky for SteamOS / ROG Ally

为 SteamOS 上的 ROG Ally 整理的 Handheld Daemon（HHD）Decky 界面。使用 Steam 原生控件，通过本机 UNIX socket 访问 HHD，提供功耗、风扇、RGB、控制器、快捷键和配置管理。

这是本地维护版本，**不是 HHD 官方发布**。插件界面和硬件控制后台是两个部分：本仓库提供 Decky 插件及已测试版本的兼容性补丁，不打包 HHD 核心或 Electron 软件窗口。

## 已验证环境

- ROG Ally RC71L，SteamOS 3.8.28。
- HHD 4.1.12、adjustor 4.0.1，安装在 `/home/deck/.local/share/hhd/venv`。
- 本机 HHD API：`/run/hhd/api`。
- Decky 使用 legacy IIFE / Python 调用接口；将来 Decky 移除该接口时需要迁移。

其他机型和版本尚未验证。界面根据当前后台提供的设置定义生成，具体功能以设备支持为准。

## 功能与修复

- 性能监控：独立 MangoHud 页面，57 个显示项目按帧率、CPU、GPU、内存、电池与系统分组；点击开关即写入当前 MangoApp 配置并重载，无需重启游戏。保留字体和布局，首次修改备份为 `output-hud.conf.before-hhd-manager`，重载失败恢复配置。部分指标依赖硬件／游戏支持。MAKO 原始帧率与输出帧率合并显示为 `FPS 原始 → 输出`，由单个开关控制：固定模式读取 base_fps / observed_output_fps；动态模式由记录的输出请求间隔得到 FG req，不能视为屏幕扫描帧率。需通过 mako-run 开启 MAKO_PRESENT_DIAGNOSTICS 并重新启动游戏；采样超过 4 秒未更新即显示 N/A，不回放历史日志。MAKO 更新或重建包装脚本后需重新确认诊断已开启。

- TDP、短时功耗上限、CPU 动态加速、GPU 频率、风扇及充电上限。
- RGB 与控制器设置，包括后台提供的启动/充电灯效高级选项。
- 配置保存、应用、删除；危险动作要求第二次点击确认。
- 11 个模块按钮切页，模块内返回；风扇与 CPU/GPU 独立分组，高级项默认收起。页面和设置状态在 Steam 快捷菜单卸载/重新挂载后保留。
- 设置写入串行、滑块修改合并提交，写后等待后台读回确认。
- 调整 TDP 自动进入自定义模式，并核对实际硬件上限；可一键固定 15W。完整配置保存不再受单次修改 64 项限制，配置应用也逐项确认。
- 设置定义按版本缓存，常规刷新数据从约 40KB 减少至 3.7KB。
- 只在插件页面挂载时每 4 秒读取状态，离开页面后停止轮询。
- 不常驻第二个 Electron 界面，不自行接管硬件控制循环。
- 屏幕色彩：原生、自然增强、鲜艳（饱和度 120 / 对比度 10）、柔和鲜艳，以及手动调节。通过 Gamescope 17³ LUT 应用 SDR 调色，不主动强制 GPU 合成。
- 调色滑块合并提交，LUT 缓存到磁盘（最多保留约 16 份）。调色恢复采用事件钩子：插件加载、Steam 启动完成、界面模式变化、游戏启动／退出和睡眠唤醒时，重新应用已启用的调色；集中到来的事件合并处理，卸载时注销钩子。无后台定时检查或周期补发；关闭调色时不发送 LUT。若事件发生时 Gamescope 尚未就绪，记录错误并等待下一个事件或手动调整，不进行定时重试。事件接口缺失时跳过该钩子，具体 Steam 版本需实机验证。

屏幕色彩设置独立存放在 `/home/deck/.config/hhd-decky-color/`，首次可导入 Screen Colors 的参数和当前 LUT。启用本功能前应停用 Screen Colors，避免两个控制器互相覆盖。首次迁移沿用旧 LUT 保持观感；后续手动修改使用本插件的独立调色算法，相同数字不代表与其他插件逐像素一致。调色是审美调整，不是仪器校色，也不能提升 LCD 的物理对比度。

“后台接受”不等于所有硬件都可直接读回。TDP、CPU boost、风扇等另有硬件读数；RGB 的实际颜色仍需肉眼确认。

## 截图

暂无。真实运行截图待补（不会用生成图片替代）。

## 输入服务如何协作

控制器由 **HHD 核心后台**处理，Decky 插件负责显示与修改配置。在已验证的掌机配置中，`hhd-power.service` 启动前临时停止并屏蔽 `inputplumber.service`，停止后解除临时屏蔽并恢复 InputPlumber。

不要同时让两个服务接管同一控制器。上述服务接管配置属于掌机已有系统设置，**安装本仓库插件不会自动建立或改变这些服务**。也应避免同时启用另一个持续写入 TDP/风扇的插件。

## 本地构建与测试

需要 Python 3 和 Node.js；无需 npm 依赖安装。

```sh
node tools/build.js
python -m unittest discover -s tests -v
node tests/test_frontend.js
```

`index.js` 是前端源码，构建复制到 `dist/index.js`。`main.py` 是 Decky Python 后端。测试中的 schema 来自已验证版本，state 使用默认值生成，不包含用户真实配置。

## 安装插件

安装前提：设备上已有可用的 HHD 后台。HHD 的安装与配置请遵循其上游文档（https://github.com/hhd-dev/hhd ）；SteamOS 上没有官方一键安装方式。本仓库 `maintenance/` 脚本只适用于下方“已验证环境”描述的特定版本组合，不是通用安装器。安装 ZIP 不会安装 HHD、adjustor、系统服务，也不会配置 InputPlumber。

### Decky 本地 ZIP 安装（推荐）

1. 从 [Releases](https://github.com/JasperJz/hhd-decky-steamos-ally/releases) 下载 `hhd-decky-版本.zip`，不要下载 GitHub 自动生成的 Source code 压缩包。
2. 将 ZIP 放到掌机的 Downloads 目录。
3. 打开 Decky 设置，启用开发者模式，在开发者选项中选择从 ZIP 安装插件，选择这个文件并确认。
4. 打开 Handheld Daemon，确认后台连接正常。

公开仓库可直接下载 Release ZIP，也可在 Decky 的 URL 安装入口使用该 ZIP 的直接下载链接。仓库为私有时，需要先登录有权限的 GitHub 账号下载，再选择本地 ZIP；直接把私有 Release 地址交给 Decky 下载会缺少 GitHub 登录权限。发布 ZIP 只安装插件，仍需要设备上已有可用 HHD 后台；它不会自动安装 HHD、adjustor 或配置输入服务。

Release 同时附带 `SHA256SUMS` 供校验。在源码目录运行 `node tools/build.js` 后执行 `python tools/package.py` 可复现安装包，输出位于 `artifacts/`。包内只包含一个 `hhd-decky/` 目录及运行文件、说明和许可证，不包含测试数据或设备配置。

### 从源码复制安装

先确认 HHD 已正常运行，且 `/run/hhd/api` 存在，再在掌机上执行：

```sh
sudo bash tools/install.sh
```

脚本只安装插件，并在覆盖已有插件前创建备份。默认 Decky 目录为 `/home/deck/homebrew`，可用 `DECKY_HOME` 指定。安装后需重新加载此插件或通过 Decky 设置重启加载器；后者可能重新加载 Steam 界面，不建议在游戏中进行。

不安装 HHD 系统服务、不修改输入服务、不设置自启动、不修改用户硬件配置。完整 HHD 后台应单独配置。

## 界面已安装但连不上后台

界面能打开但报「HHD 后台未响应：…」或「插件连接超时」时，按顺序检查：

1. HHD 后台是否在运行：`systemctl status hhd-power`（或你实际使用的 HHD 服务）。
2. 套接字是否存在：`ls -l /run/hhd/api`。文件不存在说明 HHD 未运行或未以该方式暴露 API；本插件只通过这个本机 UNIX socket 通信，不支持 HHD 的 HTTP/token 模式。
3. Decky 的 legacy Python 插件后端是否正常：本插件使用 legacy IIFE / Python 调用接口，目标 Decky 版本移除该接口时插件将无法工作；可在 Decky 开发者选项或 `journalctl` 中查看插件 Python 错误。
4. 是否有两个控制器驱动同时接管手柄（HHD 与 InputPlumber 冲突），参见上文「输入服务如何协作」。
5. 使用屏幕调色时 Gamescope 未就绪只会影响调色，不影响设置读写；调色相关报错见插件内「屏幕色彩」页面状态行。

## 卸载

在 Decky 设置中卸载 Handheld Daemon。若启用过屏幕调色，请先在插件中关闭调色（必要时再启用 Screen Colors）。插件在插件目录之外创建的文件需手动清理：`/home/deck/.config/hhd-decky-color/`（调色配置与 LUT 缓存）和 `/home/deck/.cache/hhd-mako-hud/`（MAKO 采样数据）。MangoHud 配置文件会保留修改前的备份（`output-hud.conf.before-hhd-manager`）。

## 维护已验证的 HHD 后台

`maintenance/compatibility.py` 针对 HHD 4.1.12 / adjustor 4.0.1 修复 CPU boost、HTTP 错误和内置更新行为。内置更新曾卸载 adjustor，并在硬件控制线程同步下载 UI，因此此配置阻止内置更新，改用维护脚本。

将 maintenance 目录复制到掌机 `/home/deck/.local/share/hhd/maintenance` 后，可以运行：

```sh
sudo /home/deck/.local/share/hhd/maintenance/repair-hhd.sh
```

该命令重新安装固定版本并重打补丁，会短暂停止 HHD；它不是升级到最新版本。脚本语法和补丁幂等应用经过验证，完整强制重装流程尚未做端到端验证。补丁遇到不匹配源码会报错，不应盲目用于其他版本。

## 测试范围与开销

### 可选：X11 桌面游戏内键盘兼容处理

当 Steam 能接收键盘命令，但全屏游戏或登录窗口遮挡屏幕键盘时，可使用 `maintenance/desktop_keyboard.py`。它仅用于 KDE/X11 桌面模式，游戏模式沿用 HHD 原来的调用路径。安装包 ZIP 不会自动安装此补丁。

把 `desktop_keyboard.py` 和 `install_desktop_keyboard.py` 放在同一目录，在已验证的 HHD 环境运行：

```sh
sudo /home/deck/.local/share/hhd/venv/bin/python maintenance/install_desktop_keyboard.py
sudo systemctl restart hhd-power
```

这是 HHD 后台源码补丁；重启后台会短暂重连控制器。调用键盘时可能短暂露出桌面，再返回原来的游戏。辅助进程仅在键盘打开期间运行，关闭后退出并恢复此前的合成器/游戏窗口属性。依赖 `xdotool`、`gdbus` 及 KDE 默认的 Meta+D、Alt+Shift+F12 快捷键；其他桌面环境未验证。不读取或记录输入文本。

原 HHD 文件备份在 `/var/lib/hhd-trial/desktop-keyboard-plugin-original.py`。恢复该文件到 HHD 的 `plugins/plugin.py` 并重启 `hhd-power` 即可撤回。HHD 重装或升级后需要重新应用此可选补丁；旧版本 Release 不包含它。

105 个后台控制路径验证、100 个可见前端回调与页面重新挂载测试通过。掌机上已验证分类切换、RGB 提交，以及 TDP、CPU boost、充电上限、风扇模式、GPU 频率和配置 CRUD。

短时采样中 Decky 插件进程约 17MiB PSS，CPU 约占单核 0.2%；HHD 核心约 41MiB / 单核 2.2%。这些是特定设备上的观察，不包括 Steam 前端增量内存，不保证零帧率影响，也不证明无长期泄漏。关闭页面后轮询停止已实测。

没有穷尽测试所有控制器映射、休眠/重置及其他机型。修改配置前建议保存自己的配置。

2026-10-24 在 SteamOS 3.9.5 上完成更新后恢复和新版模块界面验收：22 项 Python 测试、100 个前端回调、94 项实机设置写入／读回、11 个模块导航与布局检查通过。实机修改验证、配置恢复过程和未覆盖范围见 [恢复与验收记录](docs/20261024-recovery-verification.md)。系统更新可能丢弃额外的 `/etc` 配置；`maintenance/preserve-hhd.conf` 是本机 HHD 配置保留规则模板，插件 ZIP 不自动安装此系统规则。

## 许可与来源

保留原 Decky 插件的许可证，见 [LICENSE](LICENSE)。HHD/adjustor 的设置定义与兼容性修改遵循各自上游许可，见 [NOTICE.md](NOTICE.md) 和 `licenses/`。

上游项目：[HHD](https://github.com/hhd-dev/hhd)、[adjustor](https://github.com/hhd-dev/adjustor)；原 Decky 插件上游（已归档）：[hhd-dev/hhd-decky](https://github.com/hhd-dev/hhd-decky)。

本仓库的开发与文档过程使用了 LLM 辅助生成和修改部分代码与文本；发布内容以仓库源码为准。

MAKO FPS 由 Decky 后端每秒采样并原子写入短文本，MangoHud 只执行 cat 读取，避免其约 50ms 的命令读取窗口漏读 Python 输出。仅在监控和合并 FPS 都启用时采样；关闭或卸载后停止采样。无新采样时显示 `FPS -- → --`。

---

# English

**HHD Decky for SteamOS / ROG Ally** is an unofficial, community-maintained Decky frontend for [Handheld Daemon (HHD)](https://github.com/hhd-dev/hhd). It renders the HHD backend's settings with native Steam controls and talks to HHD over the local UNIX socket `/run/hhd/api` — no second daemon, no idle polling, no token handling.

- **This is not the official HHD plugin.** The upstream plugin [hhd-dev/hhd-decky](https://github.com/hhd-dev/hhd-decky) is archived; this repository continues that role with an independently rewritten backend and frontend under the same BSD 3-Clause license. The plugin keeps the name `Handheld Daemon` because Decky identifies installed plugins by that name; renaming would strand existing installs without updates.
- **The ZIP installs the plugin only.** It does not install HHD or adjustor, add system services, or configure InputPlumber. A running HHD backend is required.

## Verified environment

- ROG Ally RC71L; SteamOS 3.8.28 (initial verification) and 3.9.5 (re-verification 2026-10-24, see `docs/`).
- HHD 4.1.12 and adjustor 4.0.1 in a user venv; HHD API at `/run/hhd/api`.
- Other devices and versions are unverified. The UI is generated from the backend's settings definitions, so the available controls depend on your device and HHD version.

## Features

- Power: TDP, short-term power limit, CPU boost, GPU frequency, fan curves, charge limit; automatic custom-mode switch and hardware-limit checks.
- RGB and controller settings, including advanced boot/charge lighting options offered by the backend.
- Profile save / apply / delete with two-step confirmation for destructive actions.
- Performance page: 57 MangoHud overlay items grouped by category, applied live without restarting the game; merged MAKO raw → output FPS display for frame-gen diagnosis.
- Screen color grading (native / natural / vivid / soft presets plus manual control) applied through a Gamescope 17³ LUT, with event-hooked restore on plugin load, Steam startup, mode changes, game start/exit and wake. Independent config in `~/.config/hhd-decky-color/`, with first-run import from the Screen Colors plugin (disable Screen Colors before enabling this feature).
- Settings definitions cached per backend version; status polled only while the plugin page is mounted.

## Prerequisite: HHD backend

Install and configure HHD first, following the upstream documentation: https://github.com/hhd-dev/hhd . SteamOS has no official one-click HHD installer; the environment this repository was verified on is listed above. The `maintenance/` scripts in this repo target that verified version combination only — they are not a general-purpose installer. Do not let two services (for example InputPlumber and HHD) take over the same controller at the same time, and avoid running a second plugin that continuously writes TDP/fan.

## Install from a ZIP

1. Download `hhd-decky-<version>.zip` from [Releases](https://github.com/JasperJz/hhd-decky-steamos-ally/releases) — not GitHub's auto-generated "Source code" archive. Verify against `SHA256SUMS`.
2. Copy the ZIP to the handheld's Downloads folder.
3. Decky → Settings → enable Developer Mode → Developer → Install plugin from ZIP → select the file.
4. Alternatively use Decky's install-from-URL with the ZIP's direct download link (the repository is public).
5. Open "Handheld Daemon" in the Quick Access menu and check that the backend connects.

## Update and uninstall

- Update: install the newer ZIP over the existing plugin (same plugin name), or pick the newer version if you browse this repository through the Decky Plugins Extended custom store.
- Uninstall from Decky settings. If screen color grading is enabled, disable it first. For a full cleanup, remove `/home/deck/.config/hhd-decky-color/` and `/home/deck/.cache/hhd-mako-hud/`; your pre-existing MangoHud config backup (`output-hud.conf.before-hhd-manager`) is kept.

## Troubleshooting: the UI installs but cannot reach the backend

The plugin shows 「HHD 后台未响应：…」(backend not responding) or 「插件连接超时」(timeout) when the backend is unreachable. Check in order:

1. Is the HHD backend running? `systemctl status hhd-power` (or your HHD service).
2. Does the socket exist? `ls -l /run/hhd/api`. If it is missing, HHD is not running or does not expose its API there — this plugin only speaks to that local UNIX socket and does not support HHD's HTTP/token mode.
3. Is Decky's legacy Python plugin backend working? This plugin uses the legacy IIFE / Python calling convention; if a future Decky version removes it, the plugin stops working. Plugin Python errors show up in Decky's developer options or `journalctl`.
4. Are two controller drivers fighting over the gamepad (HHD vs InputPlumber)? See the input-service notes in the Chinese section above.
5. Gamescope not being ready only affects color grading, not settings read/write; color errors are shown on the plugin's color page status row.

## Screenshots

Not yet available — real-device screenshots are to be added. No generated mockups are used.

## Limitations and status

- Device verification covers ROG Ally RC71L on SteamOS 3.8.28 / 3.9.5 with HHD 4.1.12 + adjustor 4.0.1 (records in `docs/`). Color-grading restore hooks depend on Steam/Decky interfaces that vary by version.
- Development of this repository was assisted by an LLM for code and documentation; what ships is the reviewed source in this repository.
- License: BSD 3-Clause carried over from the original plugin (see [LICENSE](LICENSE)). HHD (LGPL-2.1-or-later) and adjustor (GPL-3.0) materials follow their upstream licenses; see [NOTICE.md](NOTICE.md) and `licenses/`.
