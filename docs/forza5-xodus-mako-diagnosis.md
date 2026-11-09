# Forza Horizon 5 / Xodus / MAKO 实机诊断

日期：2026-10-24，Pacific/Auckland。

环境：Xodus Nexus 0.3.11、backend 0.2.11、runtime 11.0-20261022-gf4adc821，MAKO 4.6。

## 结论与限制

- 游戏曾实际加载 MAKO；界面显示 Xodus 不能说明渲染层只附加到启动器。游戏继承 Steam App ID 4045960248。
- MAKO 的 active 状态不能证明实际达到指定倍率。以下数字来自 Renderer 的 `fixed-plan` 诊断，只覆盖启动阶段短样本，不是稳定游戏性能或屏幕扫描输出实测。

| 对照 | 输入 base_fps | 输出 observed_output_fps | 结果 |
| --- | ---: | ---: | --- |
| 固定 4 倍、样本 1 | 26.9682 | 53.9363 | 约 2 倍，有 generated-delivery-miss / acquire-budget-exhausted |
| 固定 4 倍、样本 2 | 26.0418 | 52.0835 | 约 2 倍，同类交付失败 |
| FG 关闭、渲染层保留 | 40.2202 | 40.2202 | 仍崩溃 |
| 完全绕过 MAKO 层 | 未测量 | 未测量 | 启动后持续运行，但卡在游戏内部安装等待 |

连续崩溃的回溯位于 `ForzaHorizon5.exe + 0x4f43b30`，向 0x9 / 0x29 写入导致异常，Xodus 返回 5。完全绕过层后曾运行成功，但后续显式禁用层的启动仍崩溃；不能据单次成功认定 MAKO 渲染层是根因。禁用 MAKO 的 wrapper 仍可能注入 MangoHud、改变 Overlay 等环境，因此需无 wrapper 对照。

## 游戏内部安装等待

Xodus 下载状态为 complete / 100%，installState 为 ready。禁用 MAKO 后仍停留在“正在安装，请稍等”，日志反复记录 `xsts_authorize_privilege xsts authorization failed, status 400`。这与尚未关闭的上游问题高度一致：

https://github.com/domsvoboda/xodus-nexus/issues/269

检查时当前发布版本就是已安装版本，未发现已确认解决此问题的更新。不能保证重登账号、重装游戏或修改图形设置能够修复。

## 已实施改动

- 消除 `MicrosoftGame.Config` 与指向它的 `MicrosoftGame.config` 软链接造成的大小写歧义，保留唯一普通文件 `MicrosoftGame.config`；原文件已备份。修复后内容发现歧义日志消失，但安装等待仍存在。
- 创建 `forza-horizon-5` 独立配置，精确匹配 `ForzaHorizon5.exe`。
- 保存该配置的 `disable_mako=true`，通过插件自身 ConfigurationService 重新生成官方格式 wrapper。验证其他进程仍启用 MAKO，Forza 进程绕过。临时硬编码绕过已删除。
- 对照期间只关闭过 Forza 配置的 FG；该配置目前保持关闭，默认配置未更改。
- 临时启用过逐游戏 MAKO_PRESENT_DIAGNOSTICS，最终已删除该诊断变量。
- 冷启动复测发现：继承 SteamAppId 时，生成的 wrapper 优先走 App ID 分支，不再执行进程名分支；无 App ID 的脚本测试未覆盖这个实际调用条件。仅保存进程配置的 disable_mako 并不足以阻止注入，复测仍出现同地址崩溃。因此最终逐游戏启动项明确指定 `MAKO_PROFILE=forza-horizon-5 /home/deck/.local/bin/mako-run %command%`。该配置保持禁用渲染层，其他游戏默认配置未更改。
- 原配置、崩溃诊断保存在掌机 `~/.config/mako-render/` 内带时间戳的 backup / forza-crash-evidence 目录。

未修改或删除存档、账号凭据、授权校验。未向上游提交日志或消息。

## 后续关键更正

用户确认曾在桌面模式进入游戏。因此安装等待的根因尚未证明是上游 #269；错误相同仅是线索，需要对照成功会话。不得据此宣布此安装无法游玩。

为建立干净对照，最终清空 Forza 的 launchOptions（原设置已备份），完全移除 MAKO wrapper 及其额外环境影响，并使用已存在的单游戏 Steam 快捷方式 AppID 3290271857 / GameID 14131610020797743104 启动。MAKO 独立配置仍保存，但无 wrapper 启动不使用它。

## 桌面模式复测及最终状态

用户补充：今天同一份安装曾在桌面模式、不加 MAKO 启动项成功进入驾驶。这是有效的成功基线，不应因当前失败而否定。

- 干净游戏模式进程确认未加载 MAKO 和 MangoHud，仍在 `+0x4f43b30` 崩溃。
- 临时 `VKD3D_CONFIG=no_upload_hacks` 曾让游戏模式进程存活超过一分钟，但仍出现授权 HTTP 400；桌面模式重复此参数仍崩溃，不能认定修复。
- 通过 `steamosctl switch-to-desktop-mode plasmax11.desktop` 进入真实 KDE/X11，会话内空启动项仍复现同地址异常。
- 撤销清单文件改名，恢复原 `MicrosoftGame.Config` 普通文件及 `MicrosoftGame.config` 软链接布局，仍崩溃。因此该文件布局改动最终已撤销。
- 清理无游戏运行时残留的 xodus-service 并由正常启动流程新建后台，仍崩溃。
- 旧 `pfx` 更名保留后，正常 launcher 自动创建全新前缀，仍在相同代码地址崩溃（写入地址 0x19）。测试结束已恢复旧 pfx；全新测试前缀另外保存在 `pfx.failed-clean-test-20261024`，未删除任何存档。
- CrashReport: `ACCESS_VIOLATION_WRITE`，UPTIME 0，USERCONFIG_ID 空，用户配置尚未完成初始化，D3D_HR_ERROR 0。这些是现场，不足以确定根因。

最终保留空游戏启动项，额外工具开关为关闭。MAKO 配置与诊断备份仍在，但不参与当前启动。当前会话留在桌面模式，默认登录模式未更改。**故障未修复，不能据现有证据认定 MAKO、模式差异或 #269 是全部问题的根因。**

## GitHub 搜索找到的新线索与修复验证

- https://github.com/domsvoboda/xodus-nexus/issues/132 ：FH6 的退出码 5、写入地址 0x9/0x19/0x29 被定位到 Wine builtin concrt140 的 concurrent_vector 竞态；微软 VC++ 原生 DLL 可解决，维护者推荐游戏菜单 Install / update VC++，报告者确认成功。虽为 FH6，故障特征与本机高度吻合，但不能仅凭相似即认定同因。
- 实机检查发现旧前缀 `system32/concrt140.dll` 324224 字节，含 `Wine builtin DLL` 标记，未有完整的微软 VC++ x64 安装注册信息。
- 使用 Nexus 0.3.11 源码 `src/main/vc-runtime.ts` 的微软官方下载地址、版本 14.44.35211.0、SHA256 `cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b` 下载验证后，在原游戏前缀运行官方 installer `/install /quiet /norestart`。
- 备份：掌机 `~/.config/mako-render/backup-before-vc-install-20261024-133430`。
- 安装退出 0，注册表 Installed=1 / Version=v14.44.35211.00；新 concrt140.dll 324208 字节，不再含 Wine builtin 标记。
- PID 10792 的实际映射确认加载前缀中的微软 CONCRT140.dll，游戏已显示 TURN 10 STUDIOS 动画、越过原启动崩溃阶段。仍需区分启动崩溃改善与后续安装等待；未因此宣布全部修复。
- https://github.com/domsvoboda/xodus-nexus/issues/201 的后续评论明确记载：曾实际完成比赛，后续更新后也出现 Installing 等待及 XSTS 400。这与用户“曾成功进入”并不矛盾。
- https://github.com/domsvoboda/xodus-nexus/issues/259 的维护者回复明确区分：0.3.11 修复 prefix 权限退出码 70，并不确认修复 Installing 等待。该 chmod 方案不适用于本机退出码 5。

## VC++ 修复后的深入诊断与 4×验证

1. 官方 runtime 对应源码包（66 MB）SHA256 `6716280fa13584d034426898c00133ea3f20e29a15324142fd2f5753d4ff1108` 已核验；仅解出 xgameruntime 源码用于诊断，没有修改或替换 runtime DLL。
2. 使用 runtime 内置 `XUSER_AUTH_METADATA_LOG`，成功确认 Store license、entitled receipt/inventory/metadata、SISU 和多次 Xbox Live XSTS 请求成功。点击 Start Game 后，部分 GetTokenAndSignature 请求返回 HTTP 400。这不是“所有 Xbox 授权失败”。
3. 一轮 `WINEDEBUG=+gdkc` 的选择性分析确认：Xbox Live 与 PlayFab 请求可成功，`https://gameservices.fh5.forzamotorsport.net/Services/o.xtsw` 使用 audience `https://gameservices.fh5.forzamotorsport.net` 时被 XSTS 返回 400。
4. 清单没有 MSAAppId，日志确认 `msaAppId (null), fullTrust 0`；当前 runtime 的 `get_rps_tickets` 后备 client ID 为 `0000000040159362`，对应 Minecraft Bedrock Windows，返回的 title-specific endpoints 也是 Minecraft 服务。该事实是高度相关线索，尚未以正确 FH5 身份复测来证明最终因果关系。不能通过猜 ID、伪造授权或绕过许可来处理。
5. 未能从游戏文件或公开 Store 元数据核验 FH5 正确 MSA client ID。当前安装等待仍未解决，需要正确的 UWP/title authentication 支持或上游修复。

MAKO 的 Forza 独立配置改为固定 4×、base_fps_cap=30、flow_scale=0.5、lighter/performance model enabled，关闭额外 MangoHud；默认配置不变。明确 `MAKO_PROFILE=forza-horizon-5`，避免继承 Steam ID 时落回默认配置。

桌面实机 1920×1080 / 120 Hz：连续 20 个 retained fixed-plan 样本观察到 input≈30.0001、observed_output_fps≈120、generated_per_real=3、generated_skipped=0。这是启动/菜单场景的 Renderer 交付数据，不等同于驾驶场景或光学测量的 scanout 帧率。原始数字样本保存在掌机 `~/.config/mako-render/forza-4x-verified-samples.txt`。

最后关闭 WINEDEBUG、XUSER_AUTH_METADATA_LOG 和 MAKO_PRESENT_DIAGNOSTICS 的临时启动参数，保留：

```text
MAKO_PROFILE=forza-horizon-5 /home/deck/.local/bin/mako-run %command%
```

微软 VC++ 已安装且保留；旧存档未删除；没有应用认证二进制补丁，没有将诊断发送给第三方。**启动崩溃与 4×交付取得实机改善/验证，进入游戏内容的安装等待仍未修复。**

## 2026-10-24: Reddit focus workaround tested remotely
Confirmed active X11 window Forza Horizon 5. Tested Alt+Tab away/restore, Super key repeated six times, Shift+Tab and Super+G, and Alt+Return. Closed the separate Steam input keyboard window using WM_DELETE_WINDOW (not Steam or the game). Final screenshot artifacts/forza-windowed.png clearly still reads 正在安装...请稍候. These focus workarounds did not unblock this run. Latest game log has 13 xsts authorization failed status 400 records; they are prior retry records, not proof that the keystrokes generated new requests.
Current pinned Nexus source xpackage.c uses a layout GUID with hyphens removed, not the oversized package family name described by Ferestre patch 0016. Installed game includes layout_7401a627-f4a2-461f-af22-7ee7b7e26b9a.xml. Therefore Ferestre package identifier patch alone is not established as applicable. Ferestre's paired client/runtime and metadata-driven Windows TitleId authentication remain a separate candidate requiring isolated validation; not yet installed or verified on this device.

## English locale test
Changed only FH5 launcher game locale zh-CN to en-US after stopping the game/main launcher, with timestamped launcher-state backup on device. Actual game PID 25851 has LANG=en_US.UTF-8, LC_ALL=en_US.UTF-8, LANGUAGE=en_US:en and MAKO_PROFILE=forza-horizon-5. Screenshot confirms START GAME in English. Pressed Return; final screenshot artifacts/forza-english-final.png shows INSTALLING... PLEASE WAIT. Fresh run logged five XSTS400 retries by 01:20:34Z. English did not unblock entry in this test. Left English configured as requested; MAKO profile unchanged.

## 2026-10-24: upstream status check and Ferestre mechanism confirmation

上游核查(本机 WebFetch,未注册账号):0.3.11 / backend 0.2.11 / runtime 11.0-20261022 仍是最新 release,其后无任何提交;main 分支 Oct 22 后无修复 XSTS/audience/MSA 相关提交。#269、#201 仍 open,维护者零回复。新增 #336(2026-10-24,SnowRunner 9NP6WL1XQDBW,同版本栈,profile/library 阶段 XSTS 400 死循环;同机 Deep Rock Galactic 正常)——问题按游戏区分且影响面扩大,不是本机特有。

Ferestre 本地克隆(artifacts/ferestre-research,HEAD f2a64ba)核对结果,与本机 gdkc 诊断互相印证并回答了上一节的遗留问题:

- `titles/9NNX1VVR3KNQ.toml`(FH5 配方,状态 playable,2026-09-07 验证)记载:`MicrosoftGame.Config` 提供 TitleId `7900C3C7`、**没有 MSAAppId**——不存在"正确的 FH5 MSAAppId"可找,上节的问题就此关闭。
- `docs/XBOX_LIVE.md`:正确行为是无 MAAppId 时按数值 TitleId 走 Windows title authentication(设备 token + proof key,同一密钥),不冒用其他应用身份;每个服务请求的 audience 来自该 title 的 NSAL(`/titles/current/endpoints`),"服务主机名不等于 token audience";XSTS 对 title claim 返回 400/403 时可退回同身份 user/device 链重试,且"被拒的 audience 不回退为通用 Xbox audience"。
- 本机现象 = Ferestre 明确列为错误路径的行为:runtime 的 `get_rps_tickets` 回退 client ID `0000000040159362`(Minecraft Bedrock,9NBLGGH2JHXJ)冒名请求 FH5 的 `gameservices.fh5.forzamotorsport.net` audience → XSTS 400。Ferestre 修复链:`xodus-cli/0009/0014/0024` + `xgameruntime/0005/0017/0019`,实现元数据驱动 TitleId 认证、per-title endpoint 发现与 issuer 绑定 token 缓存;修复后 FH5 title-service 请求 403→200,Festival Playlist 可加载,玩家确认。
- Ferestre 的 INSTALLING 症状另有 package identifier 溢出原因(xgameruntime/0016);此前已核对 Nexus 的 xpackage.c 用去连字符 GUID,不受该项影响。本机剩余阻塞就是 title 认证 400。

**当前判定:安装等待的根因方向已由两条独立证据线(本机 gdkc 选择性日志 + Ferestre 已验证实现)收敛到 xodus-service 缺少 MSAAppId-less Windows title 的 TitleId 认证路径。本机无法通过配置修复;重登、权限、locale、焦点等已实测无效。待办:① 在 #269 提交本机脱敏证据并指出修复方向(对外发帖需用户批准);② Ferestre paired client/runtime 隔离验证(需用户决定,不影响现有 Nexus 安装);③ 跟踪上游新 release。**

## 2026-10-24: Nexus runtime 官方源码核对(根因实锤)

下载官方源码包 `xodus-nexus-runtime-11.0-20261022-gf4adc821-source.tar.xz`(69 MB,release 附 sha512sum)并核对,以下行号均在 `shared-build/wine-src/dlls/xgameruntime/xuser.c`:

- L438-461 `get_rps_tickets`:`static const char platform_client_id[] = "0000000040159362"`,注释明确写这是 xodus 平台自身的 MSA client id,并举例 Deep Rock Galactic(无 MSAAppId、RequiresXboxLive=false)用平台身份即可工作——与 #336 中 DRG 正常、SnowRunner 卡死完全吻合。L461:RPS 请求 `ClientId = msaAppId ? msaAppId : platform_client_id`,FH5(无 MSAAppId)因此用平台(即 Minecraft Bedrock 的)身份铸 user/device token。L454 的 TRACE 格式与本机日志 `msaAppId (null), fullTrust 0` 逐字一致。
- L2660+ `xsts_authorize_privilege`:XSTS 请求以调用方传入的 RelyingParty(FH5 title 服务的 audience)组装;L2678 `if (!title || !user->titleToken) title = FALSE`——FH5 无 titleToken(TitleId 认证路径不存在),请求退化为"平台身份 user/device token + 游戏 audience"。XSTS 拒绝 400 后 L2687 `ERR("xsts authorization failed, status %lu")` 即本机日志反复出现的错误行。
- L808/819:Nexus **已有** NSAL 端点发现(`/titles/default/endpoints` 与 `/titles/current/endpoints`,L728 解析每端点 RelyingParty)——因此缺的不是 audience 发现,而仅是 Ferestre `xodus-cli/0014`/`xgameruntime/0017` 实现的那块:MSAAppId-less legacy Windows title 的数值 TitleId 认证(user/device/title token 同一 proof key,不用平台 ID 冒名)。已提供给用户的 #269 评论草稿中"per-title audience discovery"半句因此略宽,核心方向(TitleId-based Windows title authentication)正确。

回归触发点(为何 10-21 前后开始失败)仍未确定:候选是微软服务端收紧,或 runtime 在 20261020/22 引入/改变该路径;需 diff 更早版本 runtime 源码(20261018 及更早)才能判定,暂未执行。

源码核对后,Ferestre 实机测试作为"诊断手段"已无必要,仅保留"现在就能玩"的价值。

## Downgrade credential format repair
User downgraded launcher to 0.3.9/backend0.2.8; old backend failed before game start with stored credentials empty/invalid. Secret Service reachable, KDE wallet unlocked, account --json stored=true, but profile --json exit1 session-user-unavailable. Root cause confirmed: user-tokens secret began XODUS_KEYRING_BASE64_V1:, payload valid JSON with user STS entry, whereas installed0.2.8 binary lacks support for that envelope. Device/user metadata entries already rawJSON. Saved exact original user-tokens inside SAME encrypted wallet under service 'Xodus Downgrade Backup', username 'user-tokens-before-downgrade-20261024-181943'; did not export credentials. Converted only active user-tokens to decoded legacy JSON using secret-tool, exact read-back verified. Retest account exit0 stored=true; profile exit0 valid profile/subscription JSON with ticket-response-received. Restarted downgraded launcher using xodus-downgrade-credential-repaired userunit. This fixes downgrade credential access only; FH5 installation wait not yet retested. Rollback by copying original backup secret back to service Xodus Service/username user-tokens via private subprocess stdin; never print secret values.

## Hidden processes / no visible launcher after further user downgrade
Device currently in Gamescope (DISPLAY=:1), launcher diagnostics0.3.8/backend0.2.8. Terminated FH5 PID120924, Xodus main92044 plus children, service120636 and CLI120658. No long-lived xodus/forza userunits existed. Moved leftover SingletonLock/Cookie/Socket to timestamped stale-singleton folder in profile after confirming old processes stopped. Started existing Xodus Steam shortcut via64bit rungameid17377266946109603840. Gamescope screenshot artifacts/xodus-repaired.png confirms visible logged-in launcher. Clicked observed Play at465,381 using DISPLAY=:1 xdotool; FH5 PID123002 launched and actual Gamescope screenshot artifacts/forza-reopened.png confirms visible legal intro. This verifies visibility/startup recovery only, not FH5 world entry. Steam Xodus shortcut currently Exe AppImage, launchoptions quoted launch-nexus script path (redundant/misconfigured but not changed while Steam running); original standalone FH5 shortcut absent from current shortcuts.vdf. Runtime remains20261022 according to current.json, despite launcher/backend downgrade. Did not change game content, saves or credential records this turn.
