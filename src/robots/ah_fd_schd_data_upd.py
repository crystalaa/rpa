import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from rpa_framework.core.base_pw import BasePw
from rpa_framework.utils.config import config
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.utils.log import logger
from rpa_framework.utils.robot_exception import RobotsException


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
            ...
        }
        data = excel_utils.read_multiple_sheets(sheet_configs)
    """
    result = {}

    try:
        for sheet_name, sheet_config in sheet_configs.items():
            if sheet_name not in excel_utils.wb.sheetnames:
                logger.warning(f"工作表 '{sheet_name}' 不存在")
                result[sheet_name] = []
                continue

            header_row = sheet_config.get('header_row', 0)
            sheet_config.get('index_col', None)
            na_fill = sheet_config.get('na_fill', '')

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



class LoginAndDirect:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽资金排程数据更新")
        logger.debug("安徽资金排程数据更新RPA初始化完成")

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

    def navigate_to_trans_page(self):
        """导航到”资金排程管理“页面"""
        try:
            logger.info("第二步：导航到”资金排程管理“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=3000)
            self.base_pw.locate_and_click("页面导航-资金收支管控", sleep=3000)
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-资金排程管理", sleep=1000)
                logger.debug(f'资金排程管理 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)

            logger.info("成功打开”资金排程管理“页面")
        except Exception as e:
            raise RobotsException(f"导航到”资金排程管理“页面失败: {str(e)}", e)

    def navigate_to_target_page(self):
        """导航到”资金日排程综合分析“页面"""
        try:
            logger.info("第三步：导航到”资金日排程综合分析“页面", extra={'color': 'darkcyan'})
            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-左侧菜单-展开", sleep=3000)
                self.base_pw.locate_and_fill("页面导航-左侧菜单-搜索输入框", "资金排程综合分析（含实施工具集）")
                self.base_pw.locate_and_click("页面导航-左侧菜单-选择菜单", sleep=1000)
            self.base_pw.set_page(page2.value)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)

            logger.info("成功打开”资金日排程综合分析“页面")
        except Exception as e:
            raise RobotsException(f"导航到”资金日排程综合分析“页面失败: {str(e)}", e)


class OperateQueryAndExportRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None
        logger.info("安徽资金排程数据更新RPA初始化完成")

    def process_data(self):
        """提交请求"""
        try:
            logger.info("第四步：点击更新按钮，打开更新数据弹窗，勾选选项，并更新数据", extra={'color': 'darkcyan'})

            # 1. 定位更新按钮并点击
            self.base_pw.locate_and_click("查询面板-更新按钮", sleep=1000)

            # 2. 定位更新数据弹窗中“全量更新复选框”并选中
            self.base_pw.locate_and_check("查询面板-更新数据弹窗-全量更新复选框")

            # 3. 定位更新数据弹窗中“周平衡数据复选框”并选中
            self.base_pw.locate_and_check("查询面板-更新数据弹窗-周平衡数据复选框")

            # 4. 定位更新数据弹窗中“日调度数据复选框”并选中
            self.base_pw.locate_and_check("查询面板-更新数据弹窗-日调度数据复选框")

            # 5. 定位更新数据弹窗中“内部结算数据复选框”并选中
            self.base_pw.locate_and_check("查询面板-更新数据弹窗-内部结算数据复选框")

            # 6. 定位更新数据弹窗中“开始更新按钮”并点击
            self.base_pw.locate_and_click("查询面板-更新数据弹窗-开始更新按钮", sleep=5000)

            self.wait_for_update_state()

        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def wait_for_update_state(self):
        """
        等待更新数据状态
        :raises RobotsException: 关键步骤超时/定位失败时抛出异常（含详细日志）
        """
        # 定义核心配置（便于维护）
        max_wait_time = 600  # 等待导出记录最大超时（秒）
        check_interval = 2  # 轮询检查间隔（秒）
        logger.info(f"开始等待更新数据状态...")

        update_flag = False
        formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        start_time = time.time()
        logger.info(f"开始等待更新数据状态记录生成（最大等待{max_wait_time}秒），目标时间：{formatted_time}")
        target_time = formatted_time[:7]
        while time.time() - start_time < max_wait_time:
            try:
                # 方式1：匹配完成状态
                row_locator = self.base_pw.page.locator(f"tr:nth-child(3):has(td:nth-child(5) > div:has-text('更新完成')):has(td:nth-child(4) > div:has-text('{target_time}'))")

                if row_locator.count() > 0:
                    logger.info(f"通过「计算进度+预算区间」匹配到更新成功状态记录，数量：{row_locator.count()}")
                    update_flag = True
                    break

                # 方式2：匹配失败状态
                row_locator = self.base_pw.page.locator(f"tr:nth-child(3):has(td:nth-child(5) > div:has-text('更新失败')):has(td:nth-child(4) > div:has-text('{target_time}'))")
                if row_locator.count() > 0:
                    logger.info(f"通过「计算进度+预算区间」匹配到更新失败状态记录，数量：{row_locator.count()}")
                    update_flag = True
                    break

            except Exception as e:
                logger.debug(f"本轮查找等待更新数据状态记录异常（忽略，继续轮询）：{str(e)}")

            # 轮询间隔
            time.sleep(check_interval)
            elapsed = int(time.time() - start_time)
            logger.debug(f"更新数据状态记录等待中，已耗时{elapsed}秒（剩余{max_wait_time - elapsed}秒）")

        # 等待更新数据状态记录超时判断
        if not update_flag:
            error_msg = f"导等待更新数据状态记录生成超时（{max_wait_time}秒），未匹配到目标记录"
            logger.error(error_msg, exc_info=True)
            raise RobotsException(error_msg)

        logger.info(f"等待更新数据状态记录定位成功")

        # 关闭更新数据弹窗
        self.base_pw.locate_and_click("查询面板-更新数据弹窗-关闭按钮", sleep=1000)
        logger.info("关闭更新数据弹窗成功")

    def run(self, username: str, password: str):
        """运行完整的流程"""
        try:
            logger.debug("开始运行安徽资金排程数据更新流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.navigate_to_trans_page()
            self.base_robot.navigate_to_target_page()

            self.process_data()

            result = {
                "success": True,
                # "data_file": excel_file_path,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')

            logger.debug("安徽资金排程数据更新-查询导出流程执行完成")
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
        send_rpa_error_notification(
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
    """
    base_robot = None
    try:
        logger.debug(f'============ start {__name__} ===========')
        logger.debug(f"start ah_ap_ar_acc_balance_rec_export robots with parameters:{kwargs}")

        logger.info("开始执行安徽资金排程数据更新")
        input_file = kwargs.get('input_file')
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        # 配置要读取的工作表
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
        }
        all_data = read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        if len(login_info) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')
        username = login_info[0].get('登录账号', '')
        password = login_info[0].get('登录密码', '')
        base_url = login_info[0].get('登录地址', '')
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
                result = operate_robot.run(username, password)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽资金排程数据更新")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽资金排程数据更新已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽资金排程数据更新执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽资金排程数据更新")
        raise
    except Exception as e:
        logger.error(f"安徽资金排程数据更新执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽资金排程数据更新")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
