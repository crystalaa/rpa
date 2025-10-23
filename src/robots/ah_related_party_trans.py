from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification,send_rpa_error_notification


'''
1、安徽电力关联交易协同
筛选“内部往来单位” 为 “培训中心” 的记录并全部同意
'''

class ReatedPartyTrans:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽电力关联交易协同")
        logger.debug("安徽电力关联交易协同RPA初始化完成")

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
            self.base_pw.locate_and_click("登录页面-登录按钮",sleep=3000)
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
            self.base_pw.locate_and_click("切换单位页面-选择单位")
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第四步：导航到”关联交易监控“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=1000)
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=1000)
            # 跳转到新的tab页

            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-关联交易监控",sleep=1000)
                # self.base_pw.locate_and_click("页面导航-卡片翻页按钮-右")
                logger.debug(f'关联交易监控 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)

            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-关联交易审核",sleep=2000)
            self.base_pw.set_page(page2.value)

            try:
                logger.debug("准备设置分页为每页2000条")
                self.base_pw.locate_and_click("页面导航-分页下拉框", sleep=500)
                self.base_pw.locate_and_click("页面导航-选项2000", sleep=1000)
                logger.debug("分页设置完成")
            except Exception as e:
                logger.warning(f"设置分页错误：{e}")

            logger.info("成功打开关联交易监控页面")
        except Exception as e:
            raise RobotsException(f"导航到运维看板页面失败: {str(e)}", e)


class PeiXunZhongXinRobots:
    def __init__(self, base_robot: ReatedPartyTrans):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("安徽电力关联交易协同（培训中心）RPA初始化完成")

    def process_data(self):
        """提交请求"""
        try:
            logger.info("第四步：处理关联交易（培训中心）协同数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.pause()

            self.base_pw.locate_and_click("关联交易审核-更多下拉", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-协同状态输入框", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-不需协同申请选项", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-查询按钮", sleep=1000)

            self.base_pw.locate_and_click("关联交易审核-列头-内部往来单位", sleep=1000)
            # self.base_pw.locate_and_click("关联交易审核-列头筛选按钮-内部往来单位", sleep=1000)
            self.base_pw.page.get_by_role("cell", name="内部往来单位", exact=True).get_by_role("cell").click()
            self.base_pw.page.wait_for_timeout(1000)
            self.base_pw.locate_and_fill("关联交易审核-列头查询弹窗-关键字输入框", "培训中心", sleep=1000)
            self.base_pw.page.keyboard.press('Enter')
            # self.base_pw.page.pause()
            rows = self.base_pw.locate_by_page("关联交易审核-列头查询弹窗-行数", wait=False)
            if rows.count() > 1:
                self.base_pw.locate_and_click("关联交易审核-列头查询弹窗-全选链接", sleep=1000)
                self.base_pw.locate_and_click("关联交易审核-列头查询弹窗-确定按钮", sleep=1000)
                self.base_pw.page.get_by_role("row", name="序号", exact=True).locator("div").nth(1).click()
                self.base_pw.page.wait_for_timeout(1000)
                self.base_pw.locate_and_click("关联交易审核-不需协同批复按钮", sleep=1000)

                agree_button = self.base_pw.locate_by_page("关联交易审核-同意按钮", wait=False)
                logger.debug(f'agree_button:{agree_button.inner_html()}')
                self.result_screenshot = self.base_pw.take_screenshot("1、关联交易审核-培训中心", tag="运行日志")
                if agree_button.get_attribute('disabled') is None:
                    agree_button.click()
                    self.base_pw.page.wait_for_timeout(1000)
                    self.base_pw.locate_and_click("关联交易审核-确定按钮", sleep=1000)
                    self.result_remark = "已批复"
                else:
                    logger.debug("同意按钮 is  disabled")
            else:
                self.result_screenshot = self.base_pw.take_screenshot("1、关联交易审核-培训中心（无记录）", tag='运行日志')
                self.result_remark = "没有“培训中心”数据，不做任何处理"
                logger.info(f'没有“培训中心”数据，不做任何处理' , extra={'color': 'blue'})
            # self.base_pw.page.pause()
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽电力关联交易（培训中心）协同流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            self.base_pw = self.base_robot.base_pw
            self.base_pw.load_selectors("安徽电力关联交易协同-培训中心")
            self.process_data()

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

            logger.debug("安徽电力关联交易（培训中心）协同流程执行完成")
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
                attachments=result.get("result_screenshot",None),
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

        logger.info("开始执行安徽电力关联交易（培训中心）协同")
        base_robot = None
        # input_file = kwargs.get('input_file')
        input_file = r'data/安徽电力关联交易协同.xlsx'
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        data = excel_utils.read_excel()
        if len(data) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')

        username = data[0].get('登录账号', '')
        password = data[0].get('登录密码', '')
        base_url = data[0].get('登录地址', '')
        email_notif = data[0].get('发送通知邮件', '').strip().lower()

        logger.debug(f'登陆信息：{username=};{password=};{base_url=}')
        if password == '' or username == '' or base_url == '':
            raise RobotsException("Excel第一个页签中的登录信息不能为空！请检查！")

        encryptor = Encryptor()
        password = encryptor.decrypt(password)

        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)

            with BasePw(playwright, show_browser, record_video) as base_pw:
                base_robot = ReatedPartyTrans(base_pw, base_url)
                pxzx_robot = PeiXunZhongXinRobots(base_robot)
                result = pxzx_robot.run(username, password)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽电力关联交易审核（培训中心）")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽电力关联交易协同已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽电力关联交易（培训中心）协同执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽电力关联交易审核（培训中心）")
        raise
    except Exception as e:
        logger.error(f"安徽电力关联交易（培训中心）协同执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽电力关联交易审核（培训中心）")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
