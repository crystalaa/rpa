import os.path
import time
from typing import Optional

from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification
import calendar
from datetime import datetime, date
from playwright.sync_api import Playwright, Page, Browser, BrowserContext, TimeoutError, Locator


def generate_date_ranges(start_date_str: str, end_date: datetime = None) -> list:
    """
    生成查询日期范围列表
    2025年前：按年查询
    2025年及之后：按月查询

    参数:
        start_date_str (str): 开始日期字符串，格式为 'YYYY-MM-DD'
        end_date (datetime): 结束日期，默认为当前日期

    返回:
        list: 包含查询日期范围的字典列表，格式为 {'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD', 'year': 'YYYY'}
    """
    if end_date is None:
        end_date = datetime.now()

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')

    date_ranges = []
    current_date = start_date

    while current_date <= end_date:
        year = current_date.year

        if year < 2025:
            # 2025年前按年查询
            start_of_year = datetime(year, 1, 1)
            end_of_year = datetime(year, 12, 31)

            # 确保不超出结束日期
            if end_of_year > end_date:
                end_of_year = end_date

            date_ranges.append({
                'start_date': start_of_year.strftime('%Y-%m-%d'),
                'end_date': end_of_year.strftime('%Y-%m-%d'),
                'year': str(year)
            })

            # 移动到下一年
            if year == end_date.year:
                break
            current_date = datetime(year + 1, 1, 1)
        else:
            # 2025年及之后按月查询
            # 获取该月的第一天和最后一天
            start_of_month = datetime(current_date.year, current_date.month, 1)
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            end_of_month = datetime(current_date.year, current_date.month, last_day)

            # 确保不超出结束日期
            if end_of_month > end_date:
                end_of_month = end_date

            date_ranges.append({
                'start_date': start_of_month.strftime('%Y-%m-%d'),
                'end_date': end_of_month.strftime('%Y-%m-%d'),
                'year': str(current_date.year)
            })

            # 移动到下一个月
            if current_date.year == end_date.year and current_date.month == end_date.month:
                break
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

    return date_ranges


def read_multiple_sheets(excel_utils, sheet_configs: dict) -> dict:
    """
    读取多个工作表的数据
    参数:
        sheet_configs (dict): 工作表配置字典，格式为 {
            'sheet_name': {'header_row': 0, 'index_col': None, 'na_fill': ''}
        }
    返回:
        dict: 以工作表名为键，数据列表为值的字典
    示例:
        sheet_configs = {
            '登录信息': {'header_row': 0},
            '单位信息': {'header_row': 0},
            '核算科目': {'header_row': 0}
        }
        data = excel_utils.read_multiple_sheets(sheet_configs)
    """
    result = {}

    try:
        for sheet_name, config in sheet_configs.items():
            if sheet_name not in excel_utils.wb.sheetnames:
                logger.warning(f"工作表 '{sheet_name}' 不存在")
                result[sheet_name] = []
                continue

            header_row = config.get('header_row', 0)
            index_col = config.get('index_col', None)
            na_fill = config.get('na_fill', '')

            ws = excel_utils.wb[sheet_name]

            # 获取表头
            headers = []
            for cell in ws[header_row + 1]:  # openpyxl行号从1开始
                headers.append(str(cell.value) if cell.value is not None else f"Column_{len(headers) + 1}")

            # 读取数据行
            records = []
            for i, row in enumerate(ws.iter_rows(min_row=header_row + 2, values_only=True), start=header_row + 2):
                # 处理缺失值
                row_data = []
                for value in row:
                    if value is None:
                        row_data.append(na_fill)
                    else:
                        row_data.append(value)

                # 创建字典
                record = dict(zip(headers, row_data))

                # 添加行号信息
                record['__row__'] = i

                records.append(record)

            result[sheet_name] = records

        return result

    except Exception as e:
        raise RobotsException(f"读取多个工作表数据错误 - {str(e)}")


'''
1、安徽往来台账查询
自动导出记录
'''


class LoginAndDirect:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽往来台账查询")
        logger.debug("安徽往来台账查询RPA初始化完成")

    def login(self, username: str, password: str):
        """登录系统"""
        try:
            logger.info("第一步：打开登录页面", extra={'color': 'darkcyan'})
            self.base_pw.page.goto(self.base_url)
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.page.wait_for_load_state("networkidle")
            logger.info("第二步：输入账号密码，登录系统", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("登录页面-单位下拉框", sleep=1000)
            self.base_pw.locate_and_click("登录页面-省公司页签", sleep=500)
            self.base_pw.locate_and_click("登录页面-公司名称",sleep=500)
            self.base_pw.locate_and_fill("登录页面-用户名输入框", username)
            self.base_pw.locate_and_fill("登录页面-密码输入框", password)
            self.base_pw.locate_and_click("登录页面-登录按钮", sleep=3000)
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            raise RobotsException(f"登录失败: {str(e)}", e)

    def switch_department(self):
        """切换单位"""
        try:
            logger.info("第三步：切换登录单位", extra={'color': 'darkcyan'})
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locate_and_click("切换单位页面-下拉框", sleep=3000)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)
            self.base_pw.locate_and_click("切换单位页面-选择单位", sleep=5000)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第四步：导航到”往来台账查询“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=3000)
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=3000)
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-往来清账", sleep=1000)
                # self.base_pw.locate_and_click("页面导航-卡片翻页按钮-右")
                logger.debug(f'往来清账 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)
            # self.base_pw.locate_and_click("页面导航-更多")
            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-往来台账查询", sleep=3000)
            self.base_pw.set_page(page2.value)
            logger.info("成功打开往来台账查询页面")
        except Exception as e:
            raise RobotsException(f"导航到运维看板页面失败: {str(e)}", e)


class OperateQueryAndExportRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None
        logger.info("安徽往来台账查询RPA初始化完成")

    def process_data(self, account_info: list, account_start_date: str):
        """提交请求"""
        global row_locator
        try:
            logger.info("第四步：处理往来往来台账查询并导出数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")

            date_range = generate_date_ranges(account_start_date)
            count = 0
            for date_range in date_range:
                start_date = date_range['start_date']
                end_date = date_range['end_date']
                year = date_range['year']
                for account in account_info:
                    account_name = account.get("科目名称", "")
                    # account_id = account.get("科目id", "")
                    if not account_name:
                        continue
                    # 先清空原来条件
                    self.base_pw.locate_and_click("查询面板-重置按钮", exact=True, sleep=1000)
                    self.base_pw.locate_and_click("查询面板-单位名称更多", sleep=1000)
                    if count == 0:
                        self.base_pw.locate_and_fill("查询面板-单位名称弹出框搜索条件", "国网安徽省电力有限公司", sleep=1000)
                        self.dynamic_locate_and_click("国网安徽省电力有限公司", sleep=1000)
                    self.base_pw.locate_and_click("查询面板-单位名称弹出框确认按钮", sleep=1000)
                    count = count + 1
                    self.base_pw.locate_and_click("查询面板-核算科目更多", sleep=3000)
                    self.base_pw.locate_and_fill("查询面板-核算科目日期", end_date[:4], sleep=1000)
                    self.base_pw.locate_and_click("查询面板-核算科目查询", sleep=3000)
                    self.base_pw.page.wait_for_timeout(3000)
                    self.base_pw.locate_and_fill("查询面板-核算科目弹出框搜索条件", account_name, sleep=1000)
                    try:
                        self.dynamic_locate_and_click(account_name, sleep=1000)
                    except RobotsException:
                        logger.warning(f"未定位到科目{account_name},跳过该项")
                        self.base_pw.locate_and_click("查询面板-核算科目弹出框确认按钮", sleep=1000)
                        continue
                    self.base_pw.locate_and_click("查询面板-核算科目弹出框确认按钮", sleep=1000)
                    self.base_pw.locate_and_fill("查询面板-凭证开始日期", start_date)
                    self.base_pw.locate_and_fill("查询面板-凭证结束日期", end_date)
                    self.query_and_download(account_name, end_date, "未清")
                    self.base_pw.locate_and_click("查询面板-状态", sleep=1000)
                    self.query_and_download(account_name, end_date, "已清")

        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def query_and_download(self, account_name: str, end_date: str, status:str):
        self.base_pw.locate_and_click("查询面板-查询按钮", sleep=5000)
        total_count = self.base_pw.selectors.get('查询面板-数据条数')
        data_count_locator = self.base_pw.page.locator(total_count)
        if data_count_locator.count() == 0:
            self.base_pw.locate_and_click("按钮集合-导出", sleep=1000)
            self.base_pw.locate_and_click("按钮集合-导出确认", sleep=1000)
            self.base_pw.locate_and_click("按钮集合-导出管理", sleep=1000)

            # 等待导出管理页面加载
            self.base_pw.page.wait_for_load_state("networkidle")

            success = False
            export_flag = False
            formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            # row_locator = self.base_pw.page.locator(
            #     "xpath=//tr["
            #     "td[2]/div[contains(., '往来台账查询')] "  # 第1列匹配中文
            #     "and "
            #     "td[3]/div[contains(., '" + formatted_time + "')]"  # 第2列匹配时间
            #     "]"
            # )
            # row_locator.wait_for(state="attached")
            # if row_locator.count() < 1:
            #     raise RobotsException("导出管理未找到往来台账查询数据行。")
            max_wait_time = 600  # 最大等待时间（秒）
            check_interval = 2  # 检查间隔（秒）
            start_time = time.time()
            logger.info("开始等待导出记录生成...")
            while time.time() - start_time < max_wait_time:
                try:
                    # 尝试多种定位方式
                    # 1. 精确时间匹配
                    row_locator = self.base_pw.page.locator(
                        "xpath=//tr["
                        "td[2]/div[contains(., '往来台账查询')] "
                        "and "
                        "td[3]/div[contains(text(), '" + formatted_time[:16] + "')]"  # 只匹配到分钟
                                                                               "]"
                    )

                    if row_locator.count() > 0:
                        logger.info("通过精确时间匹配找到导出记录")
                        export_flag = True
                        break

                    # 2. 如果精确匹配失败，尝试只匹配任务名称并选择最新的
                    all_rows = self.base_pw.page.locator("xpath=//tr[td[2]/div[contains(., '往来台账查询')]]")
                    if all_rows.count() > 0:
                        row_locator = all_rows.first
                        logger.info("通过任务名称匹配找到导出记录")
                        export_flag = True
                        break

                except Exception as e:
                    logger.debug(f"查找导出记录时出现异常: {str(e)}")

                # 等待指定时间后重试
                time.sleep(check_interval)
                elapsed = int(time.time() - start_time)
                logger.debug(f"已等待 {elapsed} 秒，继续等待导出记录...")

            if not export_flag:
                raise RobotsException(f"等待导出记录超时（{max_wait_time}秒）")

            logger.info("导出记录定位成功")
            # 循环检查文件是否准备成功
            logger.info("开始等待文件导出准备完成...")
            while not success:
                try:
                    # 检查"成功标识"是否存在
                    success_locator = self.base_pw.locate_by_locator('按钮集合-导出成功标识', row_locator).first
                    # 等待元素出现，设置较短超时
                    if success_locator.count() > 0:
                        logger.info("文件导出成功，准备下载...")
                        success = True
                        break
                except Exception as e:
                    # 未找到成功标识，继续等待
                    pass
                logger.info(f"等待中...")
            # self.base_pw.page.wait_for_timeout(10000)
            export_button = self.base_pw.locate_by_locator("按钮集合-下载", row_locator, timeout=0, wait=True)
            with self.base_pw.page.expect_download() as download_info:
                export_button.click()
            while not download_info.is_done():
                time.sleep(1)  # 等待1秒，然后再次检查
            download = download_info.value
            original_file_name = download.suggested_filename
            # 分离文件名和扩展名
            file_name_parts = os.path.splitext(original_file_name)
            year_part = end_date[:4]
            if int(year_part) < 2025:
                file_date_part = year_part
            else:
                file_date_part = end_date[:7]
            new_file_name = f"{file_date_part}_{account_name}_{status}_{file_name_parts[0]}{file_name_parts[1]}"
            new_file_name = new_file_name.replace('\\', '_')
            # 确保data目录存在
            os.makedirs('data', exist_ok=True)
            save_path = os.path.join('data', new_file_name)
            download.save_as(save_path)
            logger.info(f"文件下载完成：{save_path}")
            self.base_pw.page.wait_for_timeout(3000)
            clean_locator = self.base_pw.locate_by_locator("按钮集合-清理", row_locator)
            clean_locator.click()
            self.base_pw.page.wait_for_timeout(3000)
            try :
                export_manage_dialog_locator = self.base_pw.page.locator(
                    self.base_pw.selectors.get('按钮集合-导出管理关闭按钮')).last
                export_manage_dialog_locator.wait_for(state="visible")
                logger.info("成功定位按钮集合-导出管理关闭按钮")
                export_manage_dialog_locator.click()
                self.base_pw.locate_and_click("按钮集合-导出关闭")
            except Exception as e:
                logger.error(f"未定位到按钮集合-导出管理关闭按钮: {str(e)}")

    def dynamic_locate_and_click(self, element_name: str,
                              wait: Optional[bool] = True,
                              exact: Optional[bool] = False,
                              timeout: Optional[int] = None,
                              sleep: Optional[int] = 0) -> Locator:

        try:

            if not self.base_pw.page:
                msg = "当前没有活动页面，请先设置活动页面"
                logger.error(msg)
                raise RobotsException(msg)
            #分步定位
            try:
                # 先定位包含文本的节点
                content_locator = self.base_pw.page.locator(f'div.el-tree-node__content > div.tl-tree-node__content', has_text=element_name).first
                if content_locator.count() > 0:
                    content_locator.wait_for(state="visible", timeout=1000)
                    # 再从该节点找到对应的复选框 input.el-checkbox__original
                    checkbox_locator = content_locator.locator('.. >> label.el-checkbox span.el-checkbox__input')
                    checkbox_locator.wait_for(state="visible", timeout=1000)
                    logger.debug(f"成功定位元素: {element_name}")
                else:
                    raise TimeoutError("未找到元素：" + f'div.tl-tree-node__content:has-text("{element_name}")')
            except TimeoutError as e:
                self.base_pw.take_screenshot(f'timeout_{element_name}', save_page=True, tag='errors')
                raise RobotsException(f'定位元素超时,元素名称: "{element_name}"', e)
            except Exception as e:
                self.base_pw.take_screenshot(f'error_{element_name}', save_page=True, tag='errors')
                raise RobotsException(f'定位元素失败,元素名称: "{element_name}"', e)

            checkbox_locator.click(force=True)
            if sleep > 0:
                self.base_pw.page.wait_for_timeout(sleep)
            return checkbox_locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并点击元素失败,元素名称: "{element_name}"', e)


    def run(self, username: str, password: str, account_info: list, account_start_date: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽往来台账查询导出流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            # TODO
            # self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            # self.base_pw = self.base_robot.base_pw
            self.base_pw.load_selectors("安徽往来台账查询-查询导出")
            self.process_data(account_info, account_start_date)

            # 处理关联交易协同并获取Excel文件路径
            # excel_file_path = self.process_workorder()

            result = {
                "success": True,
                # "data_file": excel_file_path,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')

            # self.base_pw.page.pause()

            logger.debug("安徽往来台账查询-查询导出流程执行完成")
            return result
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {str(e)}", e)


def send_email_notification(result, task_name):
    try:
        logger.debug(f"发送通知邮件：{result=}")
        send_rpa_success_notification(
            task_name=task_name,
            result_message="Robot执行成功",
            from_addr="xtgscwgk@ah.sgcc.com.cn",
            to_addr="xtgscwgk@ah.sgcc.com.cn",
            attachments=result.get("result_screenshot", None),
            additional_info=result.get("result_remark", "无")
        )
    except Exception as e:
        logger.warning(f"发送邮件失败：{e}")


def send_email_alert(errmsg, base_pw, task_name):
    error_screen = None
    logger.debug(f"send_email_alert with: {errmsg=}; base_pw={base_pw}")
    try:
        error_screen = base_pw.base_pw.error_screenshot
    except Exception as e:
        logger.debug(f"error when getting error_screenshot: {str(e)}")

    try:
        success = send_rpa_error_notification(
            task_name=task_name,
            error_message=str(errmsg),
            from_addr="xtgscwgk@ah.sgcc.com.cn",
            to_addr="xtgscwgk@ah.sgcc.com.cn",
            attachments=['logs/rpa.log', error_screen],
            additional_info="详细信息请参见附件日志"
        )

    except Exception as e:
        logger.warning(f"发送邮件失败：{e}")



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
        logger.debug(f'============ start {__name__} ===========')
        logger.debug(f"start ahdl_workorder robots with parameters:{kwargs}")

        logger.info("开始执行安徽往来管理（往来清账）")
        base_robot = None
        input_file = kwargs.get('input_file')
        # input_file = r'data/安徽往来清账.xlsx'
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        # 配置要读取的工作表
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
            '单位信息': {'header_row': 0},  # 第二个页签-单位信息(单位id, 单位名称)
            '核算科目': {'header_row': 0}  # 第三个页签-核算科目(科目id, 科目名称)
        }
        all_data = read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        unit_info = all_data['单位信息']
        account_info = all_data['核算科目']
        # data = excel_utils.read_excel()
        if len(login_info) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')
        username = login_info[0].get('登录账号', '')
        password = login_info[0].get('登录密码', '')
        base_url = login_info[0].get('登录地址', '')
        account_start_date = login_info[0].get('凭证开始时间', '')
        email_notif = login_info[0].get('发送通知邮件', '').strip().lower()

        logger.debug(f'登陆信息：{username=};{password=};{base_url=}')
        if password == '' or username == '' or base_url == '':
            raise RobotsException("Excel第一个页签中的登录信息不能为空！请检查！")

        encryptor = Encryptor()
        password = encryptor.decrypt(password)

        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)

            with BasePw(playwright, show_browser, record_video) as base_pw:
                base_robot = LoginAndDirect(base_pw, base_url)
                operate_robot = OperateQueryAndExportRobots(base_robot)
                result = operate_robot.run(username, password, account_info, account_start_date)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽往来管理（往来清账）")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽往来管理（往来清账）导出已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽往来管理（往来清账）导出执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽往来管理（往来清账）")
        raise
    except Exception as e:
        logger.error(f"安徽往来管理（往来清账）导出执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽往来管理（往来清账）")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
