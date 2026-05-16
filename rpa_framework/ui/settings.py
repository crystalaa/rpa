"""
系统设置功能入口

提供系统设置对话框的入口函数
"""

from rpa_framework.ui.components.settings_dialog import show_settings_dialog
from rpa_framework.utils.log import logger


def main(parent_window=None):
    """
    系统设置主函数
    
    :param parent_window: 父窗口
    """
    try:
        logger.info("打开系统设置")
        result = show_settings_dialog(parent_window)
        logger.info("系统设置对话框已关闭")
        return result
        
    except Exception as e:
        logger.error(f"打开系统设置失败: {str(e)}")
        raise Exception(f"打开系统设置失败: {str(e)}")


if __name__ == "__main__":
    # 独立运行时的测试
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    main()
    sys.exit(app.exec()) 