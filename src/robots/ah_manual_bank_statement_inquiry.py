from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification
from datetime import datetime, timedelta
from typing import List, Tuple

'''
1、安徽银企对账
'''


def generate_date_ranges(start_year_month: str, end_date: datetime = None) -> List[str]:
    if end_date is None:
        end_date = datetime.now()
    start_year, start_month = map(int, start_year_month.split("-"))
    current_date = datetime(start_year, start_month, 1)
    year_months = []
    while current_date <= end_date:
        year_months.append(current_date.strftime("%Y-%m"))
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1,1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1,1)
    return year_months


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
            '账号信息': {'header_row': 0}
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


def set_input_value(self, input_id, value_to_set):
    try:
        # 1. 等待元素加载
        self.base_pw.page.wait_for_selector(input_id, state="visible", timeout=5000)

        # 2. 执行 JS 操作
        self.base_pw.page.evaluate(
            """
            (arg) => {
                const input = document.querySelector(arg.id);
                if (input) {
                    input.removeAttribute("readonly");
                    input.value = arg.value;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
            """,
            {
                "id": input_id,
                "value": value_to_set
            }
        )
    except Exception as e:
        print(f"❌ 操作失败：{e}")


class LoginAndDirect:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽银行对账单查询【手工采集】对账单")
        logger.debug("安徽银行对账单查询【手工采集】对账单RPA初始化完成")

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
            self.base_pw.locate_and_click("登录页面-公司名称", sleep=500)
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
            # self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.wait_for_timeout(3000)
            self.base_pw.locate_and_click("切换单位页面-选择单位", sleep=5000)
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第四步：导航到”银企对账“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=3000)
            self.base_pw.locate_and_click("页面导航-资金收支管控", sleep=3000)
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-银企对账首页", sleep=1000)
                # self.base_pw.locate_and_click("页面导航-卡片翻页按钮-右")
                logger.debug(f'银企对账首页 popped up , {page1.value}')
            self.base_pw.page.wait_for_timeout(3000)
            self.base_pw.set_page(page1.value)
            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-银行对账单查询", sleep=3000)
            self.base_pw.set_page(page2.value)
            logger.info("成功打开银行对账单查询页面")
        except Exception as e:
            raise RobotsException(f"导航到银行对账单查询页面失败: {str(e)}", e)


class OperateRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("安徽银行对账单查询【手工采集】对账单初始化完成")

    def process_data(self, account_info: list, start_date: str):
        """提交请求"""
        try:
            logger.info("第四步：处理安徽银行对账单查询【手工采集】对账单", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("load")
            date_range = generate_date_ranges(start_date)
            for acc in account_info:
                for collect_date in date_range:
                    client = self.base_pw.context.new_cdp_session(self.base_pw.page)
                    client.send("Network.clearBrowserCache")
                    self.base_pw.page.reload(wait_until="networkidle")
                    self.base_pw.locate_and_click("查询面板及按钮-手工采集按钮")
                    self.base_pw.page.wait_for_selector('#collectBillsDilag', state='visible')
                    # self.base_pw.locate_and_click("查询面板及按钮-账号下拉框")

                    xpath = self.base_pw.selectors.get("查询面板及按钮-采集账号")
                    self.base_pw.page.evaluate(
                        f'''
                        (value) => {{
                            // 找到 collectBacode 元素并设置其值
                            const collectBacodeEl = $('#collectBacode'); // 使用 jQuery 选择器获取元素
                            if (collectBacodeEl.length > 0) {{
                                // 使用 qzzcombobox 的 API 设置值
                                if (collectBacodeEl.qzzcombobox(true)) {{
                                    collectBacodeEl.qzzcombobox(true).text(value);
                                    collectBacodeEl.trigger('change');
                                    collectBacodeEl.trigger('input');
                                }} else {{
                                    // 如果 qzzcombobox 不可用，则使用普通方式设置值
                                    collectBacodeEl.qzzcombobox({{"multiple": false, "multiSelect": false, "data": []}});
                                    collectBacodeEl.qzzcombobox(true).text(value);
                                    collectBacodeEl.trigger('change');
                                    collectBacodeEl.trigger('input');
                                }}
                                
                            }} else {{
                                console.error("collectBacode 元素未找到");
                            }}
                        }}
                        ''',
                        acc['账号']
                    )
                    collect_date_css = self.base_pw.selectors.get("查询面板及按钮-采集日期")
                    self.base_pw.page.evaluate(
                        """
                        (arg) => {
                            const input = document.querySelector(arg.id);
                            if (input) {
                                input.removeAttribute("readonly");
                                input.value = arg.value;
                                input.dispatchEvent(new Event("input", { bubbles: true }));
                                input.dispatchEvent(new Event("change", { bubbles: true }));
                            }
                        }
                        """,
                        {
                            "id": collect_date_css,
                            "value": collect_date[:7]
                        }
                    )
                    self.base_pw.locate_and_click("查询面板及按钮-采集弹窗确认按钮")
                    logger.info(f"当前账号：{acc['账号']}，采集日期：{collect_date}已完成")
                    self.base_pw.page.wait_for_timeout(5000)
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str, account_info: list, start_date: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽银行对账单查询【手工采集】对账单流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            # self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            self.process_data(account_info, start_date)

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

            logger.debug("安徽银行对账单查询【手工采集】对账单流程执行完成")
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

        logger.info("开始执行安徽银行对账单查询【手工采集】对账单")
        base_robot = None
        input_file = kwargs.get('input_file')
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        # excel_utils = ExcelUtils(input_file)
        # data = excel_utils.read_excel()
        excel_utils = ExcelUtils(input_file)
        # 配置要读取的工作表
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
            '账号信息': {'header_row': 0}  # 第二个页签-账号信息
        }
        all_data = read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        account_info = all_data['账号信息']
        if len(login_info) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')
        username = login_info[0].get('登录账号', '')
        password = login_info[0].get('登录密码', '')
        base_url = login_info[0].get('登录地址', '')
        start_date = login_info[0].get('开始时间', '')
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
                operate_robot = OperateRobots(base_robot)
                result = operate_robot.run(username, password, account_info, start_date)

                if email_notif not in ['', '否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽银行对账单查询【手工采集】对账单")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽银行对账单查询【手工采集】对账单已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽安徽银行对账单查询【手工采集】对账单执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="安徽银行对账单查询【手工采集】对账单")
        raise
    except Exception as e:
        logger.error(f"安徽银行对账单查询【手工采集】对账单执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="安徽银行对账单查询【手工采集】对账单")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
