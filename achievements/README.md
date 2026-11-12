# Quick Achievements

在 SteamOS 游戏模式里查看正在运行的 Steam 游戏的成就。打开面板时从 Steam 客户端读取当前账号的进度，显示已解锁数量、成就说明和 Steam 提供的单项进度。「未解锁」和「已解锁」可通过切换栏查看，默认展示未解锁成就。隐藏成就直接显示 Steam 返回的名称和说明。

运行 `python achievements/build.py`，在 Decky 的开发者设置中选择从 ZIP 安装，然后选中生成的 `artifacts/quick-achievements-0.2.0.zip`。

进入 Decky → Quick Achievements 即可查看。游戏内解锁新成就后，可选择「刷新成就」重新读取。
