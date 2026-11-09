# SteamOS 更新后 HHD 恢复与界面验收

日期：2026-10-24（Pacific/Auckland）。实机 SteamOS 3.9.5 / 20261023.100，ROG Ally RC71L；HHD 4.1.12 / adjustor 4.0.1。

## 已复现的问题及处理

1. 系统 Python 升到 3.14.6，旧 HHD venv 的包仍在 python3.13 目录，启动出现 `ModuleNotFoundError`。使用 `venv/lib/python3.14 -> python3.13` 兼容链接恢复；没有复制第二套解释器。这仍是兼容恢复，不代表已重建独立运行环境。
2. 原自定义 TDP 滑块仅修改 inactive custom 值，Turbo 模式保持不变。实机复现 API 成功、硬件仍为 30/30/30W。现在修改瓦数自动启用 custom，并等待 sysfs 硬件上限确认。
3. 原配置保存在 `/var/lib/overlays/etc/upper/previous/hhd/state.yml`，而当前 `/etc/hhd` 在更新后重新生成。恢复旧风扇、GPU、灯光与快捷键等配置，再固定 15W / 关闭 TDP boost。原配置与恢复前配置先备份到 root 私有的 `/var/lib/hhd-trial/recovery-20261024-230627/before.tar.gz`。
4. 新增 `/etc/atomic-update.conf.d/90-hhd.conf` 保留 `/etc/hhd/**`；依据设备 `/usr/lib/rauc/atomic-update-keep.conf` 的 drop-in 规则。模板为 `maintenance/preserve-hhd.conf`。尚未通过再次升级系统验证保留行为。
5. 保存配置会触发 64 项写入限制。现在完整配置按 schema 数量校验，单次普通修改仍限 64 项；不保存动作、隐藏状态与内部遥测。
6. 上游 profile/apply 使用共享 condition，实机曾提前返回旧配置。现在读取已保存配置，预先校验全部值，再串行分批写入并读回确认；TDP 同样等待硬件确认。
7. 原生 TextField 的 onChange 传入事件，原实现却把事件当配置名称。已提取输入字符串并加入回归测试。
8. 分类下拉改为 11 个模块卡片，模块内返回；风扇、CPU/GPU 从功耗页拆分，高级设置默认折叠。实机布局测试抓到原 ButtonItem 在窄面板越界，已改成限定宽度的原生 DialogButton。

## 验证结果

| 层级 | 结果 |
| --- | --- |
| Python 自动测试 | 22 项通过，覆盖 105 条控制定义及配置／TDP 回归 |
| 前端隔离测试 | 100 个可见回调，含所有模式分支、危险操作确认、模块进入返回、重挂载、名称事件、调色事件钩子 |
| 实机 API | 94 项当前设置写入相同值并读回；这部分验证接口，不等同逐项硬件变化 |
| 实机临时修改 | TDP 14→15W、CPU boost 开→关、充电上限 80%→原值、风扇曲线、GPU 范围、RGB 亮度、快捷键、充电灯开关；均恢复 |
| 实机配置 | 创建、列出、读取、应用、删除、新插件实例读回；应用配置后 TDP 硬件读回通过 |
| 实机前端 | 原生名称输入事件、保存 UI Regression、二次确认应用、二次确认删除；测试配置已移除 |
| 实机调色 | natural 预设及原设置恢复；不能代替目视色彩判断 |
| 实机 UI | 11 个模块逐页进入返回、卡片不重叠、控件不横向越界、无运行时异常；保留截图 |
| 最终状态 | HHD 同一进程运行、NRestarts=0；三个 TDP 上限为 15/15/15W；保留 My 15W 配置 |

可复现命令：

```sh
node tools/build.js
python -m unittest discover -s tests -v
node tests/test_frontend.js
# 下列两项仅在 SteamOS 实机运行。硬件测试会临时修改设置，应先备份。
sudo /home/deck/.local/share/hhd/venv/bin/python tools/verify_live.py --exercise
/home/deck/.local/share/hhd/venv/bin/python tools/verify_ui.py
```

实机测试输出在 `/home/deck/.local/state/hhd-recovery/live-audit.json` 与 `ui-audit/`。UI 验收要求先打开 HHD 面板，并暂停用户操作。

## 验证边界

没有实际执行关机、休眠、重置、内置更新等动作；测试的是确认保护与调用路径。没有穷举控制器模式变更、所有外设与实体灯光效果。未重启整机或再升级系统来验证持久性，也没有进行游戏负载／帧率基准。因此 15W 是硬件功耗上限，不代表整机始终消耗 15W。用户无关的游戏诊断文件未修改。
