"""
动态导入示例Robot
演示如何创建可以被动态导入的Robot文件
"""
import sys
from pathlib import Path

# 添加项目根目录到路径，以支持相对导入
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config


def main(**kwargs):
    """主函数 - 这是动态导入时调用的入口函数
    
    Args:
        **kwargs: 参数字典，包含以下键：
            - show_browser (bool): 是否显示浏览器
            - record_video (bool): 是否自动录制
            - debug_mode (bool): 是否启用调试模式
    """
    try:
        logger.info("开始执行动态导入示例Robot")
        
        # 获取参数
        show_browser = kwargs.get("show_browser", False)
        record_video = kwargs.get("record_video", False)
        debug_mode = kwargs.get("debug_mode", False)
        
        logger.info(f"执行参数: show_browser={show_browser}, record_video={record_video}, debug_mode={debug_mode}")
        
        # 模拟Robot执行过程
        logger.info("步骤1: 初始化动态Robot")
        if debug_mode:
            input("按回车键继续...")
        
        logger.info("步骤2: 执行主要业务逻辑")
        if debug_mode:
            input("按回车键继续...")
        
        logger.info("步骤3: 完成执行")
        
        result = {
            "success": True,
            "message": "动态导入示例Robot执行成功",
            "data": {
                "robot_type": "dynamic",
                "execution_time": "2024-01-01 12:00:00"
            }
        }
        
        logger.info("动态导入示例Robot执行完成")
        return result
        
    except Exception as e:
        error_msg = f"动态导入示例Robot执行失败: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def test_function():
    """测试函数 - 用于验证模块导入"""
    return "动态导入测试成功"


# 模块级别的变量
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "这是一个动态导入的示例Robot模块"


if __name__ == "__main__":
    # 当直接运行此文件时的测试代码
    print(f"模块版本: {MODULE_VERSION}")
    print(f"模块描述: {MODULE_DESCRIPTION}")
    
    # 测试main函数
    result = main(show_browser=True, debug_mode=True)
    print(f"执行结果: {result}") 