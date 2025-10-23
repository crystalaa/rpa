#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller运行时钩子
确保基础模块在程序启动时就被正确导入
"""

try:
    # 强制导入基础模块
    import json
    import logging
    import pathlib
    import os
    import sys
    import traceback
    import time
    import datetime
    import typing
    import importlib
    import importlib.util
    
    # 确保这些模块在程序启动时就被加载
    print("Runtime hook: 基础模块已预加载")
    
    # 验证关键模块是否可用
    if json is None:
        print("警告: json模块导入失败")
    else:
        print("✓ json模块已加载")
        
    if logging is None:
        print("警告: logging模块导入失败")
    else:
        print("✓ logging模块已加载")
        
except Exception as e:
    print(f"Runtime hook错误: {e}")
    # 即使出错也要继续，不要阻止程序启动 