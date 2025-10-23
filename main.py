import sys
import traceback
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from rpa_framework.ui import App
from rpa_framework.utils import logger
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
