from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification

'''
1、安徽电厂购电业务关联确认
（1）按序号，核实发票（价税合计、税额、不含税金额）与对应应付数据（金额、成本、税额）相应字段数据是否一致
如相关字段核对一致，选择预算责任中心后，点击界面右下角【审核通过】按钮
（2）如相关字段数据核对不一致，点击界面右下角【回退营销】按钮
'''


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


class LoginAndDirect:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽电厂购电业票关联确认")
        logger.debug("安徽电厂购电业务关联确认RPA初始化完成")

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

    # def switch_department(self):
    #     """切换单位"""
    #     try:
    #         logger.info("第三步：切换登录单位", extra={'color': 'darkcyan'})
    #         self.base_pw.set_page(self.base_pw.get_main_page())
    #         # self.base_pw.locate_and_click("切换单位页面-下拉框", sleep=3000)
    #         # self.base_pw.page.wait_for_load_state("networkidle")
    #         # self.base_pw.page.wait_for_timeout(3000)
    #         # self.base_pw.locate_and_click("切换单位页面-选择单位")
    #         # logger.info("单位切换成功")
    #     except Exception as e:
    #         logger.error(f"切换单位失败: {str(e)}")
    #         raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第三步：导航到”安徽电厂购电业务关联确认“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-应用总览", sleep=1000, wait=True)
            self.base_pw.page.wait_for_load_state("load")
            # self.base_pw.locate_and_click("页面导航-价格管理", sleep=1000, wait=True)
            # self.base_pw.locate_and_click("页面导航-价格管理", sleep=1000, wait=True)
            self.base_pw.page.wait_for_timeout(5000)
            # self.base_pw.page.wait_for_load_state("load")
            self.base_pw.locate_and_click("页面导航-省内购电结算", sleep=1000, wait=True, timeout=0)
            with self.base_pw.page.expect_popup(timeout=0) as page1:
                self.base_pw.locate_and_click("页面导航-电厂购电结算", sleep=1000, wait=True)
            self.base_pw.set_page(page1.value)
            self.base_pw.locate_and_click("页面导航-业票关联确认", sleep=1000, wait=True)
            # 跳转到新的tab页

            with self.base_pw.page.expect_popup(timeout=0) as page2:
                self.base_pw.locate_and_click("页面导航-全量处理", sleep=1000)
                logger.debug(f'电厂购电业务关联确认 popped up , {page2.value}')
            self.base_pw.set_page(page2.value)
            try:
                logger.debug("准备设置分页为每页1000条")
                self.base_pw.page.select_option('#mktPageSize', '1000')
                # self.base_pw.locate_and_click("页面导航-分页下拉框", sleep=500)
                # self.base_pw.locate_and_click("页面导航-选项2000", sleep=1000)
                logger.debug("分页设置完成")
            except Exception as e:
                logger.warning(f"设置分页错误：{e}")

            logger.info("成功打开安徽电厂购电业务关联确认页面")
        except Exception as e:
            raise RobotsException(f"导航到安徽电厂购电业务关联确认页面失败: {str(e)}", e)


class OperateRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("安徽电厂购电业务关联确认RPA初始化完成")

    def process_data(self, query_info: list):
        """提交请求"""
        try:
            logger.info("第四步：处理安徽电厂购电业务关联确认数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")
            time_List = ['开始电费年月', '结束电费年月', '开票日期开始时间', '开票日期结束时间']
            input_List = ['发票代码', '发票号码']
            pass_list = ['__row__', '预算责任中心']
            selectors = self.base_pw.selectors
            # for obj in query_info:
            for key, value in query_info[0].items():
                if key in pass_list:
                    continue
                elif key in time_List and (value is not None and value != ""):
                    selector = selectors.get(f"查询面板及按钮-{key}")
                    # 设置开始日期输入框的值
                    # 触发输入框的change事件
                    date_input = self.base_pw.page.locator(selector)

                    date_input.evaluate('''(element, value) => {
                        element.value = value;
                        const event = new Event('change', { bubbles: true });
                        element.dispatchEvent(event);
                    }''', value)
                elif key in input_List:
                    self.base_pw.locate_and_fill(f"查询面板及按钮-{key}", value)
                else:
                    logger.info("暂不支持")

            with self.base_pw.page.expect_response(lambda response: 'listRelAuditGroup' in response.url,
                                                   timeout=30000) as response_info:
                self.base_pw.locate_and_click("查询面板及按钮-查询按钮", sleep=1000)
                response = response_info.value
                response_data = response.json()
                if str(response_info.value.status) != "200":
                    response_msg = response_data.get("message")
                    logger.error(f"查询数据错误：{response_msg}")
                    self.result_remark = f"查询数据错误：{response_msg}"
                    return

            # 获取总条数
            # total_count = self.base_pw.page.inner_text(selectors.get("查询面板及按钮-数据总条数"))
            # page_size = 1000
            # total_pages = (int(total_count) + page_size - 1) // page_size

            # # 循环处理每一页
            # for page_idx in range(1, total_pages + 1):
            #     # 如果不是第一页，点击下一页按钮
            #     if page_idx > 1:
            #         self.base_pw.page.click(selectors.get("查询面板及按钮-下一页"))
            #         self.base_pw.page.wait_for_timeout(5000)  # 等待页面加载
            #
            #     # 获取当前页的页码
            #     current_page_data = self.base_pw.page.inner_text(selectors.get("查询面板及按钮-当前页码"))
            #     logger.info(f"Processing page {current_page_data}")
            # try:
            #     self.base_pw.page.wait_for_selector(selectors.get("查询面板及按钮-表格数据行标识"), timeout=10000)
            #     rows = self.base_pw.page.query_selector_all(selectors.get("查询面板及按钮-表格数据行标识"))
            #     if not rows:
            #         logger.info("查询数据为空，跳过当前处理")
            #         pass
            # except Exception:
            #     logger.info("查询数据为空，跳过当前处理")
            #     pass
            unAuditCntCount = 0
            el = self.base_pw.page.query_selector('#unAuditCnt')
            if not el:
                unAuditCntCount = 0
            txt = el.inner_text().strip()
            unAuditCntCount = int(txt) if txt else 0
            if unAuditCntCount == 0:
                logger.warning("当前查询条件无数据，无需处理。")
                self.result_remark = "查询数据为空，无需处理。"
                return

            max_iterations = 5
            iteration = 0
            while iteration < max_iterations:
                iteration += 1
                while unAuditCntCount != 0:
                    rows = self.base_pw.page.query_selector_all(selectors.get("查询面板及按钮-表格数据行标识"))
                    for row in rows:
                        # 获取发票信息表格
                        invoice_table = row.query_selector(selectors.get("查询面板及按钮-发票信息表格"))
                        invoice_rows = invoice_table.query_selector_all(selectors.get("查询面板及按钮-行标识"))
                        # 获取结算数据表格
                        settlement_table = row.query_selector(selectors.get("查询面板及按钮-结算数据表格"))
                        settlement_rows = settlement_table.query_selector_all(selectors.get("查询面板及按钮-行标识"))

                        # 获取发票信息的总价税合计、税额、不含税金额
                        invoice_total = 0
                        invoice_tax = 0
                        invoice_net = 0
                        for invoice_row in invoice_rows:
                            total = invoice_row.query_selector('td:nth-child(2) p:nth-child(1) span')
                            net = invoice_row.query_selector('td:nth-child(2) p:nth-child(2) span')
                            tax = invoice_row.query_selector('td:nth-child(2) p:nth-child(3) span')
                            if total and net and tax:
                                invoice_total += safe_float_convert(total.inner_text())
                                invoice_net += safe_float_convert(net.inner_text())
                                invoice_tax += safe_float_convert(tax.inner_text())

                        # 获取结算数据的购电费、购电成本、购电税额
                        settlement_total = 0
                        settlement_cost = 0
                        settlement_tax = 0
                        for settlement_row in settlement_rows:
                            total = settlement_row.query_selector('td:nth-child(3) p:nth-child(1) span')
                            cost = settlement_row.query_selector('td:nth-child(3) p:nth-child(2) span')
                            tax = settlement_row.query_selector('td:nth-child(3) p:nth-child(3) span')
                            if total and cost and tax:
                                settlement_total += safe_float_convert(total.inner_text())
                                settlement_cost += safe_float_convert(cost.inner_text())
                                settlement_tax += safe_float_convert(tax.inner_text())

                        # 比较并勾选复选框
                        if invoice_total == settlement_total and invoice_tax == settlement_tax and invoice_net == settlement_cost:
                            checkbox = row.query_selector('input[type="checkbox"]')
                            checkbox.check()
                    sum_checked = self.base_pw.page.query_selector('#sumChecked')
                    sum_checked_value = sum_checked.inner_text()
                    if sum_checked_value != '0':
                        logger.info(f"勾选条数不为0，当前勾选条数为: {sum_checked_value}")
                        # 执行其他操作，选择预算责任中心，并点击审核通过按钮
                        # 定位预算责任中心的下拉框
                        budget_center_selector = '#s2id_mktBudgetCen_render .select2-choice'
                        budget_center = self.base_pw.page.query_selector(budget_center_selector)

                        # 点击下拉框以展开选项
                        budget_center.click()

                        # 等待搜索框加载
                        self.base_pw.page.wait_for_selector('#s2id_autogen4_search')

                        # 输入筛选值
                        search_input = self.base_pw.page.query_selector('#s2id_autogen4_search')
                        current_budegt_dept = query_info[0].get("预算责任中心")

                        search_input.fill(current_budegt_dept)  # 替换为实际需要筛选的值

                        # 等待选项加载
                        self.base_pw.page.wait_for_selector('.select2-result-selectable')
                        # 选择具体的选项
                        option_selector = f".select2-result-selectable:has-text('{current_budegt_dept}')"
                        option = self.base_pw.page.query_selector(option_selector)
                        option.click()
                        pass_btn = self.base_pw.page.query_selector('#mktAuditPassBtn')
                        pass_btn.click()
                        self.base_pw.page.wait_for_timeout(10000)
                    else:
                        logger.info("此时没有审核通过的数据，需要全部勾选，回退营销")
                        for row in rows:
                            checkbox = row.query_selector('input[type="checkbox"]')
                            checkbox.check()
                        rollback_btn = self.base_pw.page.query_selector('#mktAuditBackBtn')
                        rollback_btn.click()
                        modal_sel = "div.colorModal:has(#mktAuditReason)"
                        # 等待并填入原因
                        self.base_pw.page.wait_for_selector("#mktAuditReason", timeout=5000)
                        self.base_pw.page.fill("#mktAuditReason", "审核不通过")

                        # 在包含该 textarea 的 modal 内找到"确定"按钮并点击
                        confirm_btn = self.base_pw.page.locator(f"{modal_sel} >> button.btn-primary:has-text('确定')")
                        if confirm_btn.count() == 0:
                            # 兜底：有时按钮没有文本准确匹配，可以用 buttonindex 属性或最后一个 btn-primary
                            confirm_btn = self.base_pw.page.locator(
                                f"{modal_sel} >> button[buttonindex='1'], {modal_sel} >> button.btn-primary").first
                        confirm_btn.click()
                        # 等待 modal 消失，确认操作已完成
                        self.base_pw.page.wait_for_selector(modal_sel, state="detached", timeout=10000)
                    # 等待弹窗出现并检查标题为“提示”，然后点击关闭按钮（x 或 按钮“关闭”）
                    try:
                        # 等待任意 modal-dialog 出现
                        modal = self.base_pw.page.wait_for_selector('div.modal-dialog', timeout=15000)
                        # 校验标题文本包含“提示”
                        title_el = modal.query_selector('.modal-title')
                        title_text = title_el.inner_text().strip() if title_el else ''
                        if '提示' in title_text:
                            # 优先点击右上角的 x 按钮
                            close_btn = modal.query_selector('button.close')
                            if close_btn:
                                close_btn.click()
                            else:
                                # 点击 modal 底部的“关闭”按钮（备选）
                                footer_btn = modal.query_selector('button:has-text("关闭")')
                                if footer_btn:
                                    footer_btn.click()
                                else:
                                    # 最后尝试通过 data-dismiss 关闭
                                    try:
                                        modal.query_selector('[data-dismiss="modal"]').click()
                                    except Exception:
                                        logger.info("弹窗关闭按钮未找到", extra={'color': 'red'})
                        else:
                            # 如果不是提示弹窗，也尝试关闭
                            try:
                                modal.query_selector('button.close') and modal.query_selector('button.close').click()
                            except Exception:
                                logger.info("弹窗存在但未识别为提示弹窗", extra={'color': 'orange'})

                        # 等待弹窗消失
                        self.base_pw.page.wait_for_selector('div.modal-dialog', state='detached', timeout=10000)
                        el = self.base_pw.page.query_selector('#unAuditCnt')
                        if not el:
                            unAuditCntCount = 0
                        txt = el.inner_text().strip()
                        unAuditCntCount = int(txt) if txt else 0
                    except Exception as e_modal:
                        logger.info(f"等待或关闭弹窗时出错: {e_modal}", extra={'color': 'red'})
                if iteration >= max_iterations:
                    logger.info("达到最大循环次数10，停止继续检查，防止死循环", extra={'color': 'red'})
                    el = self.base_pw.page.query_selector('#unAuditCnt')
                    if not el:
                        unAuditCntCount = 0
                    txt = el.inner_text().strip()
                    unAuditCntCount = int(txt) if txt else 0
                    if unAuditCntCount > 0:
                        self.result_remark = f"当前未审核数据还有{unAuditCntCount}条，但已达到最大循环次数10，停止继续检查，防止死循环"
                    else:
                        self.result_remark = "当前数据已审核完毕"
                    # self.result_remark = f"当前未审核数据还有{unAuditCntCount}条，但已达到最大循环次数10，停止继续检查，防止死循环"
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str, query_info: list):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽电厂购电业务关联确认处理流程")
            self.base_robot.base_pw.init_browser()
            self.base_pw = self.base_robot.base_pw
            self.base_robot.login(username, password)
            self.base_robot.navigate_to_trans_page()
            self.process_data(query_info)

            result = {
                "success": True,
                # "data_file": excel_file_path,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')

            logger.debug("安徽电厂购电业务关联确认流程执行完成")
            return result
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {str(e)}", e)


def safe_float_convert(text):
    if not text:
        return 0.0
    # 移除千分位分隔符(逗号)和首尾空白
    cleaned_text = text.strip().replace(',', '')
    return float(cleaned_text)


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

        logger.info("开始执行安徽电厂购电业务关联确认")
        base_robot = None
        input_file = kwargs.get('input_file')
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        # 配置要读取的工作表
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
            '查询面板': {'header_row': 0}  # 第二个页签-账号信息
        }
        all_data = read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        query_info = all_data['查询面板']
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
                pxzx_robot = OperateRobots(base_robot)
                result = pxzx_robot.run(username, password, query_info)

                if email_notif not in ['', '否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽电力关联交易审核（培训中心）")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽电厂购电业务关联确认已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽电厂购电业务关联确认执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="安徽电厂购电业务关联确认")
        raise
    except Exception as e:
        logger.error(f"安徽电厂购电业务关联确认执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="安徽电厂购电业务关联确认")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
