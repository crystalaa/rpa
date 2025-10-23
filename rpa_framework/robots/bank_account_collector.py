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
银行账号余额采集
'''
class BankAccountCollector:
    def __init__(self, base_pw: BasePw, base_url: str, fmp_url: str):
        self.base_pw = base_pw
        self.base_url = base_url
        self.fmp_url = fmp_url
        self.base_pw.load_selectors("银行账户补采")
        logger.info("银行账户补采RPA初始化完成")

    def login(self, username: str, password: str):
        """登录系统"""
        try:
            logger.info("开始登录系统")
            self.base_pw.page.goto(f"{self.base_url}/isc_sso/login?service=http%3A%2F%2Fdev.iscenv.com%3A22002%2Fisc_sso%2Foauth2.0%2FcallbackAuthorize?oauth20_callbackUrl=http://fmptest.sgcc.com.cn/base/redirectLogin&response_type=token&client_id=10003&redirect_uri=http://fmptest.sgcc.com.cn/base/redirectLogin&state=7308cad")
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locator("登录页面-单位下拉框").click()
            self.base_pw.locator("登录页面-公司总部").click()
            self.base_pw.locator("登录页面-用户名输入框").fill(username)
            self.base_pw.locator("登录页面-密码输入框").fill(password)
            self.base_pw.locator("登录页面-登录按钮").click()
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            logger.error(f"登录失败: {str(e)}")
            raise Exception(f"登录失败: {str(e)}")

    def switch_department(self):
        """切换单位"""
        try:
            logger.info("开始切换单位")
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locator("切换单位页面-下拉框").click()
            dept = self.base_pw.locator("切换单位页面-选择单位")
            dept.scroll_into_view_if_needed()
            dept.click()
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_collect_page(self):
        """导航到补采页面"""
        try:
            logger.info("开始导航到补采页面")
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locator("菜单页面-共享财务中心").click()
            self.base_pw.locator("菜单页面-资金收支管控").click()
            
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locator("菜单页面-账户办理开户").click()
            self.base_pw.set_page(page1.value)
            # self.base_pw.page.pause()
            self.base_pw.page.goto(f"{self.fmp_url}/fmp-grm/fmp-cap-monitor/gris/mapp/std-zjjk-fundmonitorweb/dataJhJkGZ/collectDataJkUI30.html")
            self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.pause()
            logger.info("成功导航到补采页面")
        except Exception as e:
            logger.error(f"导航到补采页面失败: {str(e)}")
            raise Exception(f"导航到补采页面失败: {str(e)}")

    def is_date(self, date: str):
        """判断日期格式是否正确"""
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date) :
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except Exception as e:
                return False
        return True

    def fill_date(self, element_name: str, date: str):
        """输入日期"""
        try:
            if date is None:
                return
            if not self.is_date(date):
                raise Exception(f"日期格式错误: '{date}'")
            locator = self.base_pw.locator(element_name)
            locator.evaluate("element=> element.removeAttribute('readonly')")
            locator.clear()
            # locator.press("Control+A")
            # locator.press("Backspace")
            locator.press_sequentially(date)
            locator.press('Tab')
            
        except Exception as e:
            logger.error(f"输入'{element_name}'的日期失败: {str(e)}")
            raise Exception(f"输入'{element_name}'的日期失败: {str(e)}")

    def collect_account_data(self, excel: ExcelUtils, start_date: str, end_date: str):
        """执行账户数据补采"""
        try:
            # 读取银行账号列表
            
            logger.info(f"开始执行账户数据补采")
            self.base_pw.locator("补采页面-补采按钮").click()
            # self.base_pw.page.pause()
            for row_num, row in excel.iter_excel(start_row=2,as_display=["A"],sheet_name="补采账号清单"):
                logger.debug(f'account_num:{row[0]},{row=},{row_num=}')

                try:
                    account_num = row[0]
                    self.base_pw.locator("补采页面-选择账号按钮").click()
                    self.base_pw.locator("补采页面-账号输入框").fill(account_num)
                    self.base_pw.locator("补采页面-查询按钮").click()

                    # account_row = self.base_pw.locator(element_name = "补采页面-查询账号", selector=f"table[id='yhzhDetailVOs_model']>>tr>>td:has-text('{account_num}')")
                    if self.base_pw.page.locator(f"table[id='yhzhDetailVOs_model']>>tr>>td:has-text('{account_num}')").count()>0:
                        # 选择账号
                        self.base_pw.page.locator(f"table[id='yhzhDetailVOs_model']>>tr>>td:has-text('{account_num}')").click()
                        self.base_pw.locator("补采页面-查询账号确定按钮").click()

                        # 输入日期范围
                        self.fill_date("补采页面-开始日期", start_date)
                        self.fill_date("补采页面-结束日期", end_date)
                        self.base_pw.locator("补采页面-回单采集Radio").click()
                        self.base_pw.locator("补采页面-交易余额采集Radio").click()
                        self.base_pw.locator("补采页面-补采确定按钮").click()
                        self.base_pw.locator("补采页面-提交弹窗_关闭按钮").click()
                        # self.base_pw.page.pause()

                        excel.write_cell("已补采", row_num, 'C', '补采账号清单')
                    else:
                        logger.error(f"未找到账号: {account_num}")
                        excel.write_cell("未找到账号", row_num, 'C', '补采账号清单')
                        self.base_pw.locator("补采页面-查询账号取消按钮").click()
                    excel.write_cell("", row_num, 'D', '补采账号清单')
                except Exception as e:
                    logger.error(f"补采账号 {row[0]} 失败: {str(e)}")
                    excel.write_cell('补采失败', row_num, 'C', "补采账号清单")
                    excel.write_cell( str(e), row_num, 'D', "补采账号清单")
                finally:
                    excel.write_cell(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row_num, 'B', '补采账号清单')
            
            logger.info("账户数据补采完成")
            
        except Exception as e:
            logger.error(f"执行账户数据补采失败: {str(e)}")
            raise Exception(f"执行账户数据补采失败: {str(e)}")

    def run(self, username: str, password: str, excel: ExcelUtils, 
            start_date: str = "2025-05-02", end_date: str = "2025-05-03"):
        """运行完整的补采流程"""
        try:
            logger.info("开始运行银行账户补采流程")
            self.base_pw.init_browser()
            self.login(username, password)
            # self.base_pw.page.pause()
            self.switch_department()
            self.navigate_to_collect_page()
            # self.base_pw.page.pause()
            self.collect_account_data(excel, start_date, end_date)
            logger.info("银行账户补采流程执行完成")
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {str(e)}", e)

def main(**kwargs):
    """主函数
    Args:
        **kwargs: 包含所有参数（file_path, show_browser, auto_record等）
    """
    try:
        logger.info("开始执行银行账户补采")
        input_file  = kwargs.get('input_file')
        if input_file == '':
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel = ExcelUtils(input_file)
        if "登录信息" not in excel.get_sheet_names():
            raise Exception('输入文件没有 "登录信息" 页签,请选择正确的输入文件!')

        username = excel.read_cell(2, "D","登录信息")
        password = excel.read_cell(2, "E","登录信息")
        base_url = excel.read_cell(2, "F","登录信息")
        fmp_url = excel.read_cell(2, "G","登录信息")
        logger.debug(f'登陆信息：{username=};{password=};{base_url=};{fmp_url=}')

        encryptor = Encryptor()
        password = encryptor.decrypt(password)

        with sync_playwright() as playwright:
            playwright_base = BasePw(playwright)
            collector = BankAccountCollector(playwright_base, base_url, fmp_url)
            collector.run(username, password, excel)
            logger.info("银行账户信息补采完成")

    except Exception as e:
        # logger.debug(f"银行账户补采失败: {e}")
        # raise Exception(f"银行账户补采失败: {e.__str__()}")
        raise

if __name__ == "__main__":
    main() 