# 来源与许可

Decky 插件沿用原插件随包附带的 LICENSE，保留其中的版权和许可声明。本地维护的 Python 桥接和原生前端源码包含在本仓库中。

`tests/fixtures/schema.json` 派生自 HHD 4.1.12 / adjustor 4.0.1 在 ROG Ally 上提供的设置定义；测试状态由定义中的默认值生成，不包含用户实际配置。

`maintenance/compatibility.py` 包含针对上述上游版本的源码修改片段。相应部分受上游许可约束；本仓库不将上游代码重新许可为插件许可证。

- HHD 4.1.12：LGPL-2.1-or-later，完整随包许可见 `licenses/hhd-LICENSE`。
- adjustor 4.0.1：完整随包许可见 `licenses/adjustor-LICENSE`。

源码来源： https://github.com/hhd-dev/hhd ， https://github.com/hhd-dev/adjustor 。
