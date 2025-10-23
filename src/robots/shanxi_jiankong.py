from datetime import datetime
import re
import os
import time
from pathlib import Path

from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
# from playwright import Playwright

'''
山西监控
'''
class ShanxiJiankong:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.base_pw.load_selectors("陕西监控")
        logger.info("陕西监控RPA初始化完成")

    def debug_pause(self, message: str = "调试暂停"):
        """调试暂停函数"""
        if self.debug_mode:
            logger.info(f"🔍 {message}")
            logger.info("按回车键继续执行下一条指令...")
            input()
            logger.info("继续执行...")

    def login(self, username: str, password: str, dept: str):
        """登录系统"""
        try:
            logger.info("开始登录系统")
            self.base_pw.page.goto(self.base_url)

            #self.base_pw.page.pause()

            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.page.wait_for_load_state("networkidle")

            self.base_pw.locate_and_click("登录页面-请选择机构")

            self.base_pw.locate_and_click("登录页面-机构名称")
            self.base_pw.locate_and_fill("登录页面-用户名输入框", username)
            self.base_pw.locate_and_fill("登录页面-密码输入框", password)
            self.base_pw.page.wait_for_timeout(3000)

            self.base_pw.locate_and_click("登录页面-请选择单位")
            self.base_pw.page.wait_for_load_state("networkidle")

            self.base_pw.locate_and_fill("登录页面-单位搜索框", dept)
            self.base_pw.page.wait_for_load_state("networkidle")

            self.base_pw.locate_and_click("登录页面-单位名称")
            self.base_pw.locate_and_click("登录页面-确定按钮")

            self.base_pw.locate_and_click("登录页面-登录按钮")
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            raise RobotsException(f"登录失败: {str(e)}", e)


    def navigate_to_monitor_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("开始导航到运维看板页面")
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locate_and_click("页面导航-智慧应用中心")
            self.base_pw.locate_and_click("页面导航-共享服务中心")
            #self.base_pw.page.locator("a:has-text('运维看板')").first.click()
            #self.base_pw.locate_and_click("页面导航-运维看板")
            
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.page.wait_for_load_state("networkidle")
                logger.debug('befor  ywkb')
                self.base_pw.page.locator("a:has-text('运维看板')").first.click()
                self.base_pw.page.wait_for_load_state("networkidle")

            self.base_pw.set_page(page1.value)

            logger.info("成功导航到运维看板页面")
        except Exception as e:
            raise RobotsException(f"导航到运维看板页面失败: {str(e)}", e)

    def submit_request(self):
        """提交请求"""
        try:
            # playwright.locator('span.ListBoxDiv > table.treeListGrid:first-child>tbody>tr:has(td.treeListTitle)')
            # playwright.locator('span.ListBoxDiv > table.treeListGrid:first-child>tbody>tr:has(td.gridCellRelative)')
            # locator("table.treeListGrid:first-child tr:has(td.treeListTitle)  td div.checkBoxDiv")
            # locator("table.treeListGrid:nth-child(2)  td div.checkBoxDiv")
            # locator("table.treeListGrid:first-child  td div.checkBoxDiv")
            logger.info("开始提交请求")

            self.base_pw.locate_and_click("运维看板-运维监控看板")
            self.base_pw.page.keyboard.press("Alt+;")
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(1000)

            self.base_pw.locate_and_click("运维看板-系统异常数")
            self.base_pw.locate_and_click("运维看板-系统异常-tab", exact=True)
            self.base_pw.page.wait_for_load_state("networkidle")
            #self.base_pw.page.pause()
            self.base_pw.page.get_by_role("row", name="序号", exact=True).locator("div").nth(1).click()

            #self.base_pw.locate_and_click("运维看板-系统异常-勾选全选")
            self.base_pw.take_screenshot('系统异常')

            self.base_pw.locate_and_click("运维看板-系统异常-重新执行")
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.locate_and_click("运维看板-环节异常-tab", exact=True)
            self.base_pw.page.wait_for_load_state("networkidle")
            #self.base_pw.page.pause()

            #self.base_pw.locate_and_click("运维看板-环节异常-勾选全选")
            self.base_pw.page.get_by_role("row", name="序号", exact=True).locator("div").nth(1).click()
            #self.base_pw.page.pause()
            self.base_pw.take_screenshot('环节异常')

            self.base_pw.locate_and_click("运维看板-环节异常-强制同步")
            logger.info("请求提交成功")
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str, dept: str):
        """运行完整的补采流程"""
        try:
            logger.info("开始运行陕西监控流程")
            self.base_pw.init_browser()
            self.login(username, password, dept)
            self.navigate_to_monitor_page()
            self.submit_request()

            result = {
                "success": True,
                "data_file": None,
                "video_file": self.base_pw.get_video_path()
            }
            
            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')
                
            logger.info("陕西监控流程执行完成")
            return result
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {str(e)}", e)

def main(**kwargs):
    """主函数
    
    Args:
        **kwargs: 参数字典，包含以下键：
            - show_browser (bool): 是否显示浏览器
            - record_video (bool): 是否自动录制
            - debug_mode (bool): 是否启用调试模式
            - username (str): 登录用户名
            - password (str): 登录密码  
            - order_name (str): 要搜索的商品名称
    """
    try:
        logger.info("开始执行陕西监控")
        logger.info("lalalalalala~~~~")
        input_file  = kwargs.get('input_file')
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        data = excel_utils.read_excel()
        if len(data) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')

        dept = data[0].get('单位名称', '')
        username = data[0].get('登录账号', '')
        password = data[0].get('登录密码', '')
        base_url = data[0].get('登录地址', '')

        logger.debug(f'登陆信息：{dept=};{username=};{password=};{base_url=}')
        if dept=='' or password=='' or username=='' or base_url=='':
            raise RobotsException("Excel第一个页签中的登录信息不能为空！请检查！")


        encryptor = Encryptor()
        password = encryptor.decrypt(password)
        
        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)
            
            with BasePw(playwright, show_browser, record_video) as base_pw:
                robot = ShanxiJiankong(base_pw, base_url)
                result = robot.run(username, password, dept)
                logger.info("陕西监控已完成", extra={'color': 'green'})
                return result
                
    except RobotsException as e:
        logger.error(f"陕西监控执行出错: {e.message}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise
    except Exception as e:
        logger.error(f"陕西监控执行出错: {str(e)}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise


if __name__ == "__main__":
    main() 
