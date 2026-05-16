"""
示例自定义Robot文件

演示如何编写符合CLI要求的自定义robot文件
"""

from rpa_framework.core.base_pw import BasePw
from rpa_framework.utils.log import logger
from playwright.sync_api import sync_playwright
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
import time
from typing import Dict, Any

def main(**kwargs):
    """主函数
    
    Args:
        **kwargs: 参数字典，包含以下键：
            - show_browser (bool): 是否显示浏览器
            - record_video (bool): 是否自动录制
            - input_file (str): 输入文件路径（可选）
    """
    try:
        logger.info("开始执行示例自定义Robot")
        logger.debug(f'输入参数: {kwargs}')
        logger.debug(f'{config.config=}')
        
        # 从参数中获取配置信息
        show_browser = kwargs.get("show_browser", False)
        record_video = kwargs.get("record_video", False)
        input_file = kwargs.get("input_file", None)
        
        logger.info(f"浏览器显示: {show_browser}")
        logger.info(f"录制视频: {record_video}")
        if input_file:
            logger.info(f"输入文件: {input_file}")
        
        with sync_playwright() as playwright:
            with BasePw(playwright, show_browser, record_video) as base_pw:
                # 初始化浏览器
                base_pw.init_browser()
                
                # 示例：访问一个网页
                logger.info("第一步：访问示例网页", extra={'color': 'darkcyan'})
                base_pw.page.goto("https://www.baidu.com")
                base_pw.page.wait_for_load_state('networkidle')
                
                # 示例：获取页面标题
                page_title = base_pw.page.title()
                logger.info(f"页面标题: {page_title}")
                
                # 示例：截图
                logger.info("第二步：截取页面截图", extra={'color': 'darkcyan'})
                screenshot_path = base_pw.take_screenshot('首页',tag='screen')
                logger.info(f"截图已保存: {screenshot_path}")
                
                # 示例：获取页面内容
                logger.info("第三步：获取页面内容", extra={'color': 'darkcyan'})
                page_content = base_pw.page.content()
                content_length = len(page_content)
                logger.info(f"页面内容长度: {content_length} 字符")
                
                # 示例：如果有输入文件，可以读取文件内容
                if input_file:
                    logger.info("第四步：处理输入文件", extra={'color': 'darkcyan'})
                    try:
                        with open(input_file, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        logger.info(f"输入文件内容长度: {len(file_content)} 字符")
                    except Exception as e:
                        logger.warning(f"读取输入文件失败: {str(e)}")
                
                # 示例：等待一段时间
                logger.info("第五步：等待操作完成", extra={'color': 'darkcyan'})
                time.sleep(2)
                
                logger.info("示例自定义Robot执行完成", extra={'color': 'green'})
                
                # 返回执行结果
                result = {
                    "success": True,
                    "data_file": None,  # 如果有数据文件，返回路径
                    "video_file": base_pw.get_video_path(),
                    "screenshot_file": screenshot_path,
                    "page_title": page_title,
                    "content_length": content_length
                }
                
                if base_pw.get_video_path():
                    logger.info(f'视频已保存到: {base_pw.get_video_path()}')
                
                return result
                
    except RobotsException as e:
        logger.error(f"示例自定义Robot执行出错: {e.message}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise
    except Exception as e:
        logger.error(f"示例自定义Robot执行出错: {str(e)}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise


if __name__ == "__main__":
    # 本地测试
    main(show_browser=True, record_video=False) 