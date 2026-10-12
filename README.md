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

- TDP、短时功耗上限、CPU 动态加速、GPU 频率、风扇及充电上限。
- RGB 与控制器设置，包括后台提供的启动/充电灯效高级选项。
- 配置保存、应用、删除；危险动作要求第二次点击确认。
- 分类和设置状态在 Steam 快捷菜单卸载/重新挂载后保留。
- 设置写入串行、滑块修改合并提交，写后等待后台读回确认。
- 设置定义按版本缓存，常规刷新数据从约 40KB 减少至 3.7KB。
- 只在插件页面挂载时每 4 秒读取状态，离开页面后停止轮询。
- 不常驻第二个 Electron 界面，不自行接管硬件控制循环。

“后台接受”不等于所有硬件都可直接读回。TDP、CPU boost、风扇等另有硬件读数；RGB 的实际颜色仍需肉眼确认。

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

## 维护已验证的 HHD 后台

`maintenance/compatibility.py` 针对 HHD 4.1.12 / adjustor 4.0.1 修复 CPU boost、HTTP 错误和内置更新行为。内置更新曾卸载 adjustor，并在硬件控制线程同步下载 UI，因此此配置阻止内置更新，改用维护脚本。

将 maintenance 目录复制到掌机 `/home/deck/.local/share/hhd/maintenance` 后，可以运行：

```sh
sudo /home/deck/.local/share/hhd/maintenance/repair-hhd.sh
```

该命令重新安装固定版本并重打补丁，会短暂停止 HHD；它不是升级到最新版本。脚本语法和补丁幂等应用经过验证，完整强制重装流程尚未做端到端验证。补丁遇到不匹配源码会报错，不应盲目用于其他版本。

## 测试范围与开销

105 个后台控制路径验证、100 个可见前端回调与页面重新挂载测试通过。掌机上已验证分类切换、RGB 提交，以及 TDP、CPU boost、充电上限、风扇模式、GPU 频率和配置 CRUD。

短时采样中 Decky 插件进程约 17MiB PSS，CPU 约占单核 0.2%；HHD 核心约 41MiB / 单核 2.2%。这些是特定设备上的观察，不包括 Steam 前端增量内存，不保证零帧率影响，也不证明无长期泄漏。关闭页面后轮询停止已实测。

没有穷尽测试所有控制器映射、休眠/重置及其他机型。修改配置前建议保存自己的配置。

## 许可与来源

保留原 Decky 插件的许可证，见 [LICENSE](LICENSE)。HHD/adjustor 的设置定义与兼容性修改遵循各自上游许可，见 [NOTICE.md](NOTICE.md) 和 `licenses/`。

上游项目：[HHD](https://github.com/hhd-dev/hhd)、[adjustor](https://github.com/hhd-dev/adjustor)。
