#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源码运行入口，同时也是 PyInstaller 的打包入口。

    python run_panel.py                 # 起服务 + 开无边框应用窗口
    python run_panel.py --no-window     # 用普通浏览器标签页打开
    python run_panel.py --port 9000     # 换端口

装了包之后也可以直接 ``deepseek-key-panel`` 或 ``python -m deepseek_key_panel``。
"""

import os
import sys

# 支持不安装、直接克隆下来就跑
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from deepseek_key_panel.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
