#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPA框架 - GUI主入口
"""

import sys
import os
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from rpa_framework.ui.app import App
from rpa_framework.robots.bank_account_collector import main as bank_account_main
from rpa_framework.robots.yingdao_order_collector import main as yingdao_main
from rpa_framework.robots.shanxi_jiankong import main as shanxi_jiankong_main
from rpa_framework.ui.components.settings_dialog import show_settings_dialog as settings_main
from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger
from rpa_framework.utils.menu_config import register_all_methods, get_menu_data

def setup_high_dpi():
    """设置高DPI支持"""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

def create_menu_data():
    """创建菜单数据"""
    # 注册所有方法映射
    register_all_methods()
    
    # 从配置文件加载菜单数据
    return get_menu_data()

def main():
    """主函数"""
    try:
        logger.info("启动图形界面模式")
        
        # 设置高DPI支持
        setup_high_dpi()
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = App(create_menu_data())
        window.show()
        
        # 运行应用程序
        return app.exec()
        
    except Exception as e:
        error_msg = f"图形界面启动错误: {str(e)}\n{traceback.format_exc()}"
        try:
            logger.error(error_msg)
        except Exception:
            print(f"图形界面启动失败: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 