# 来源与许可

本仓库是非官方维护的 HHD Decky 前端。插件沿用原 Decky 插件随包附带的 LICENSE（BSD 3-Clause，版权见该文件），保留其中的版权和许可声明；本仓库不重新许可上游代码。

- 原 Decky 插件：[hhd-dev/hhd-decky](https://github.com/hhd-dev/hhd-decky)（作者 Aarron Lee，原版权 2022-2023 Steam Deck Homebrew），上游已归档。本仓库的 Python 桥接和前端为独立重写（改用本机 UNIX socket `/run/hhd/api`，未复用上游源码结构），沿用其插件名 `Handheld Daemon` 与许可证谱系；Decky 以该名称识别已安装插件。
- HHD 4.1.12：LGPL-2.1-or-later，上游 https://github.com/hhd-dev/hhd ，完整随包许可见 `licenses/hhd-LICENSE`。
- adjustor 4.0.1：GPL-3.0，上游 https://github.com/hhd-dev/adjustor ，完整随包许可见 `licenses/adjustor-LICENSE`。
- `tests/fixtures/schema.json` 派生自 HHD 4.1.12 / adjustor 4.0.1 在 ROG Ally 上提供的设置定义；测试状态由定义中的默认值生成，不包含用户实际配置。
- `maintenance/compatibility.py` 及相关脚本包含针对上述上游版本的源码修改片段，相应部分受上游许可约束；本仓库不将上游代码重新许可为插件许可证。`maintenance/` 不随安装 ZIP 分发。

发布 ZIP 内包含本 NOTICE、插件 LICENSE 和 `licenses/` 中的上游许可证副本。

本仓库的开发与文档过程使用了 LLM 辅助生成和修改部分代码与文本；发布内容以仓库源码为准。
