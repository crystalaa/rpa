from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from ah_related_party_trans import ReatedPartyTrans, send_email_alert, send_email_notification


'''
3、安徽电力关联交易: 个人扣除项目
筛选“分录摘要” 为 “社保、公积金、社会保险、个税、个人所得税、五险一金、企业年金、补充医疗保险” 的记录并全部同意
'''

class GeRenKouChuRobots:
    def __init__(self, base_robot: ReatedPartyTrans):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = []
        self.result_remark = ''

        logger.info("安徽电力关联交易协同（个人扣除项目）RPA初始化完成")

    def process_data(self):
        """提交请求"""
        try:
            items = ["社保", "公积金", "社会保险", "个税", "个人所得税", "五险一金", "企业年金", "补充医疗保险"]
            logger.info("第四步：处理关联交易协同数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.pause()

            self.base_pw.locate_and_click("关联交易审核-更多下拉", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-协同状态输入框", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-不需协同申请选项", sleep=1000)
            self.base_pw.locate_and_click("关联交易审核-查询按钮", sleep=1000)
            for item in items:
                logger.info(f"开始处理：“个人扣除项目-{item}”")
                self.base_pw.locate_and_click("关联交易审核-列头-分录摘要", sleep=1000)
                # self.base_pw.locate_and_click("关联交易审核-列头筛选按钮-内部往来单位", sleep=1000)
                self.base_pw.page.get_by_role("cell", name="分录摘要", exact=True).get_by_role("cell").click()
                self.base_pw.page.wait_for_timeout(1000)
                self.base_pw.locate_and_fill("关联交易审核-列头查询弹窗-关键字输入框", item, sleep=1000)
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
                    screenshots_path = self.base_pw.take_screenshot(f"3、关联交易审核-个人扣除项目-{item}（无记录）", tag='运行日志')
                    self.result_screenshot.append(screenshots_path)
                    if agree_button.get_attribute('disabled') is None:
                        agree_button.click()
                        self.base_pw.page.wait_for_timeout(1000)
                        self.base_pw.locate_and_click("关联交易审核-确定按钮", sleep=1000)
                    else:
                        logger.debug("同意按钮 is  disabled")
                else:
                    screenshots_path = self.base_pw.take_screenshot(f"3、关联交易审核-个人扣除项目-{item}（无记录）", tag='运行日志')
                    self.result_screenshot.append(screenshots_path)
                    self.result_remark += f"没有“个人扣除项目-{item}”数据，不做任何处理<br>"
                    logger.info(f'没有“个人扣除项目-{item}”数据，不做任何处理' , extra={'color': 'blue'})
                logger.debug(f"“个人扣除项目-{item}”处理完成")
            # self.base_pw.page.pause()
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽电力关联交易(个人扣除项目)协同流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            self.base_pw = self.base_robot.base_pw
            #### 个人扣除项目和自动清账操作的元素一样，所以使用自动清账的selector
            self.base_pw.load_selectors("安徽电力关联交易协同-自动清账")
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

            logger.info("安徽电力关联交易协同(个人扣除项目)流程执行完成")
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
        logger.debug(f'============ start {__name__} ===========')
        logger.debug(f"start ahdl_workorder robots with parameters:{kwargs}")

        logger.info("开始执行安徽电力关联交易协同(个人扣除项目)")
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
                pxzx_robot = GeRenKouChuRobots(base_robot)
                result = pxzx_robot.run(username, password)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽电力关联交易审核（个人扣除项目）")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽电力关联交易协同(个人扣除项目)已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽电力关联交易协同(个人扣除项目)执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽电力关联交易审核（个人扣除项目）")
        raise
    except Exception as e:
        logger.error(f"安徽电力关联交易协同(个人扣除项目)执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽电力关联交易审核（个人扣除项目）")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
