# -*- coding: utf-8 -*-
"""
DeepSeek Key 面板
=================

导入 DeepSeek API Key，批量查余额、验证可用性、看用量和消耗。

* 网页版：``deepseek_key_panel.app``（本地服务 + 无边框应用窗口）
* 命令行版：``deepseek_key_panel.cli``

所有请求都由本机直接发往 ``api.deepseek.com`` / ``platform.deepseek.com``，
不经过任何第三方服务器。
"""

from .server import VERSION as __version__

__all__ = ["__version__"]
