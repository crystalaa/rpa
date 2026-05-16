#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPA自动化框架

一个基于Playwright和PySide6的RPA自动化框架，
用于快速开发各种自动化机器人。
"""

__version__ = "1.0.0"
__author__ = "RPA开发团队"
__email__ = "rpa@example.com"
__description__ = "RPA自动化框架 - 用于快速开发自动化机器人"

# 导出主要的类和函数
from rpa_framework.core.base_pw import BasePw
from rpa_framework.core.page_helper import PageHelper
from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.utils.robot_exception import RobotsException

__all__ = [
    "BasePw",
    "PageHelper",
    "config",
    "logger",
    "ExcelUtils",
    "RobotsException",
    "__version__",
    "__author__",
    "__email__",
    "__description__",
]
