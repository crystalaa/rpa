from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification,send_rpa_error_notification


'''
1、安徽分布式电源购电业务关联确认
（1）按序号，核实发票（价税合计、税额、不含税金额）与对应应付数据（金额、成本、税额）相应字段数据是否一致
如相关字段核对一致，选择预算责任中心后，点击界面右下角【审核通过】按钮
（2）如相关字段数据核对不一致，点击界面右下角【回退营销】按钮
'''
html_path = "file://" + __file__.replace("\\", "/").rsplit("/", 1)[0] + "/test.html"
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
        self.base_pw.load_selectors("安徽分布式业票关联确认")
        logger.debug("安徽分布式电源购电结算业票关联确认RPA初始化完成")

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
            logger.info("第三步：导航到”安徽分布式电源购电结算业票关联确认“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-应用总览", sleep=1000, wait=True)
            self.base_pw.page.wait_for_load_state("load")
            # self.base_pw.locate_and_click("页面导航-价格管理", sleep=1000, wait=True)
            # self.base_pw.locate_and_click("页面导航-价格管理", sleep=1000, wait=True)
            self.base_pw.page.wait_for_timeout(5000)
            # self.base_pw.page.wait_for_load_state("load")
            self.base_pw.locate_and_click("页面导航-可再生能源补贴结算", sleep=1000, wait=True, timeout=0)
            with self.base_pw.page.expect_popup(timeout=0) as page1:
                self.base_pw.locate_and_click("页面导航-分布式电源结算", sleep=1000, wait=True)
            self.base_pw.set_page(page1.value)
            self.base_pw.locate_and_click("页面导航-业票关联确认", sleep=1000, wait=True)
            # 跳转到新的tab页
            # 添加处理弹窗的逻辑
            try:
                # 等待并关闭可能存在的提示弹窗
                popup_locator = self.base_pw.page.locator("div.el-message-box__wrapper")
                if popup_locator.count() > 0:
                    # 尝试点击弹窗的关闭按钮或确定按钮
                    close_btn = self.base_pw.page.locator("div.el-message-box__wrapper .el-message-box__btns button")
                    if close_btn.count() > 0:
                        close_btn.first.click()
                        self.base_pw.page.wait_for_timeout(1000)
            except Exception as popup_e:
                logger.debug(f"处理弹窗时出现小错误（可忽略）: {popup_e}")
            with self.base_pw.page.expect_popup(timeout=0) as page2:
                self.base_pw.page.locator(self.base_pw.selectors.get("页面导航-全量处理")).first.click()
                # self.base_pw.locate_and_click("页面导航-全量处理", sleep=1000)
                logger.debug(f'安徽分布式电源购电结算业票关联确认 popped up , {page2.value}')
            self.base_pw.set_page(page2.value)
            try:
                logger.debug("准备设置分页为每页1000条")
                # self.base_pw.page.select_option('#pageSize', '1000')
                ok = self.set_page_size_via_eval(1000)
                print("结果：", ok)
                logger.debug("分页设置完成")
            except Exception as e:
                logger.warning(f"设置分页错误：{e}")

            logger.info("成功打开安徽分布式电源购电结算业票关联确认页面")
        except Exception as e:
            raise RobotsException(f"导航到安徽分布式电源购电结算业票关联确认页面失败: {str(e)}", e)

    def set_page_size_via_eval(self, size=1000):
        page = self.base_pw.page

        s = str(size)
        return page.evaluate("""(v) => {
            const sel = document.querySelector('#pageSize');
            if (!sel) return false;
            sel.value = v;
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            // 更新 bootstrap 显示的按钮文本和 title（如果存在）
            const btn = document.querySelector('button.dropdown-toggle[data-id="pageSize"]');
            if (btn) {
                const fo = btn.querySelector('.filter-option');
                if (fo) fo.innerText = v;
                btn.title = v;
            }
            return true;
        }""", s)



class OperateRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None
        #存放需要人工审核的数据
        self.manual_rows = set()

        logger.info("安徽分布式电源购电结算业票关联确认RPA初始化完成")

    def process_data(self, query_info : list):
        """提交请求"""
        try:
            logger.info("第四步：处理安徽电厂购电业务关联确认数据", extra={'color': 'darkcyan'})
            message_infos = []
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.locate_and_click("查询面板及按钮-查询条件更多")
            time_List = ['开始电费年月', '结束电费年月', '开票日期开始时间', '开票日期结束时间', '接收日期开始时间',
                         '接收日期结束时间']
            input_List = ['发票代码', '发票号码', '项目编号', '所属供电所']
            pass_list = ['__row__']
            selectors = self.base_pw.selectors
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
                    self.base_pw.locate_and_fill(f"查询面板及按钮-{key}", str(value))
                else:
                    logger.info("暂不支持")

            self.base_pw.locate_and_click("查询面板及按钮-查询按钮", sleep=1000)
            self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.wait_for_selector(selectors.get("查询面板及按钮-表格数据行标识"), timeout=10000)
            row_locator = self.base_pw.page.locator(selectors.get("查询面板及按钮-表格数据行标识"))
            if 0 == row_locator.count():
                logger.warning("当前条件无数据，无需处理。")
                self.result_remark = "当前条件无数据，无需处理。"
                return None
            unAuditCntCount = 0
            el = self.base_pw.page.query_selector('#unauditSheetcnt')
            if not el:
                unAuditCntCount = 0
            txt = el.inner_text().strip()
            unAuditCntCount = int(txt) if txt else 0
            max_iterations = 5
            iteration = 0
            while iteration < max_iterations:
                iteration += 1
                while unAuditCntCount != 0:
                    rows = self.base_pw.page.query_selector_all(selectors.get("查询面板及按钮-表格数据行标识"))
                    for row in rows:
                        row_key = row.query_selector('td:nth-child(3)').inner_text().strip()
                        if row_key in self.manual_rows:
                            continue
                        # 获取发票信息表格
                        invoice_table = row.query_selector(selectors.get("查询面板及按钮-发票信息表格"))
                        invoice_rows = invoice_table.query_selector_all('tr')
                        # 获取结算数据表格
                        settlement_table = row.query_selector(selectors.get("查询面板及按钮-结算数据表格"))
                        settlement_rows = settlement_table.query_selector_all('tr')

                        # 获取发票信息的总价税合计、税额、不含税金额
                        invoice_total = 0
                        invoice_tax = 0
                        invoice_net = 0
                        for invoice_row in invoice_rows:
                            total = invoice_row.query_selector('td:nth-child(2) p:has-text("价税合计") span')
                            net = invoice_row.query_selector('td:nth-child(2) p:has-text("不含税金额") span')
                            tax = invoice_row.query_selector('td:nth-child(2) p:has-text("税额") span')
                            if total and net and tax:
                                invoice_total += float(total.inner_text())
                                invoice_net += float(net.inner_text())
                                invoice_tax += float(tax.inner_text())

                        # 获取结算数据的购电费、购电成本、购电税额
                        settlement_total = 0
                        settlement_cost = 0
                        settlement_tax = 0
                        for settlement_row in settlement_rows:
                            total = settlement_row.query_selector('p:has-text("金额") span')
                            cost = settlement_row.query_selector('p:has-text("成本") span')
                            tax = settlement_row.query_selector('p:has-text("税额") span')
                            if total and cost and tax:
                                settlement_total += float(total.inner_text())
                                settlement_cost += float(cost.inner_text())
                                settlement_tax += float(tax.inner_text())

                        # 比较并勾选复选框
                        if invoice_total == settlement_total and invoice_tax == settlement_tax and invoice_net == settlement_cost:
                            checkbox = row.query_selector('input[type="checkbox"]')
                            checkbox.check()
                            self.base_pw.locate_and_click("查询面板及按钮-审核通过按钮", sleep=1000)
                            modal = self.base_pw.page.wait_for_selector("div.modal:has(.modal-title:has-text('提示'))", timeout=10000)
                            try:
                                self.handle_audit_modal_or_raise("审核成功", modal,wait_timeout=0)
                                logger.info("审核通过，弹窗已关闭")
                            except RuntimeError as e:
                                # 这里是非“审核通过”的情况，异常信息包含弹窗文本
                                logger.info("需要人工处理或中断：", e)
                                message_infos.append(e)
                                self.manual_rows.add(row_key)
                                continue
                        else:
                            checkbox = row.query_selector('input[type="checkbox"]')
                            checkbox.check()
                            self.base_pw.locate_and_click("查询面板及按钮-回退营销按钮", sleep=1000)
                            modal_sel = "div.colorModal:has(#auditReason)"
                            # 等待并填入原因
                            self.base_pw.page.wait_for_selector("#auditReason", timeout=5000)
                            self.base_pw.page.fill("#auditReason", "审核不通过")
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
                                modal = self.base_pw.page.wait_for_selector("div.modal:has(.modal-title:has-text('提示'))", timeout=0)
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
                                self.base_pw.page.wait_for_selector("div.modal:has(.modal-title:has-text('提示'))", state='detached', timeout=10000)
                            except Exception as e_modal:
                                logger.info(f"等待或关闭弹窗时出错: {e_modal}", extra={'color': 'red'})
                        el = self.base_pw.page.query_selector('#unauditSheetcnt')
                        if not el:
                            unAuditCntCount = 0
                        txt = el.inner_text().strip()
                        unAuditCntCount = int(txt) if txt else 0
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
            return message_infos
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def handle_audit_modal_or_raise(self, ok_substr="审核成功", modal=None, wait_timeout=5000):
        """
        等待弹窗出现，读取文本。
        - 若文本包含 ok_substr：点击右上角 x 关闭弹窗并返回 True。
        - 否则：尝试点击 x 关闭弹窗，然后抛出 RuntimeError(弹窗文本)。
        使用 sync Playwright API。
        """

        page = self.base_pw.page

        # 读取 modal-body 文本（多种选择器兜底）
        body_loc = page.locator("div.modal:has(.modal-title:has-text('提示')) .modal-body")
        text = ""
        try:
            if body_loc.count() > 0:
                text = body_loc.first.inner_text().strip()
        except Exception:
            # 读取失败保持空字符串
            text = ""

        # 尝试点击右上角的 x 关闭按钮（多重兜底）
        closed = False
        try:
            close_btn = modal.query_selector('button.close')
            if close_btn:
                close_btn.click()
                closed = True
            else:
                # 备选：查找任何 footer/按钮里的 × 或 标记为关闭的按钮
                alt = page.locator('button:has-text("×"), button:has-text("关闭"), .modal-footer button.btn-default')
                if alt.count() > 0:
                    alt.first.click()
                    closed = True
        except Exception:
            closed = False

        # 最后兜底：如果仍然没有关闭，尝试按 Esc 或通过 JS 隐藏 modal（不推荐但可救急）
        if not closed:
            try:
                page.keyboard.press('Escape')
                closed = True
            except Exception:
                pass

        if not closed:
            # 通过 JS 强制隐藏 modal（最后手段）
            try:
                page.evaluate("""() => {
                    const m = document.querySelector('div.colorModal.modal, div.modal');
                    if (m) { m.style.display = 'none'; m.setAttribute('aria-hidden', 'true'); }
                    return !!m;
                }""")
                closed = True
            except Exception:
                closed = False

        # 等待弹窗完全消失（best-effort）
        try:
            page.wait_for_selector('div.colorModal.modal, div.modal.fade.in, .modal.show', state='detached', timeout=3000)
        except Exception:
            # 不强求成功
            pass

        # 根据文本决定返回或抛错
        if ok_substr == text:
            return True
        else:
            # 抛出异常并把弹窗文本带上
            raise RuntimeError(text)

    def run(self, username: str, password: str, query_info : list):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽分布式电源购电结算业票关联确认处理流程")
            self.base_robot.base_pw.init_browser()
            self.base_pw = self.base_robot.base_pw
            self.base_robot.login(username, password)
            self.base_robot.navigate_to_trans_page()
            msg_info = self.process_data(query_info)
            if msg_info:
                self.result_remark += "其中部分数据需要人工处理。"
                if not self.result_remark:
                    self.result_remark = ''
                for i, it in enumerate(msg_info, 1):
                    text = str(it).strip()
                    if not text:
                        continue
                    # 示例：加序号并换行
                    self.result_remark += ('\n' if self.result_remark else '') + f"{i}. {text}"
            result = {
                "success": True,
                # "data_file": excel_file_path,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')


            logger.debug("安徽安徽分布式电源购电结算业票关联确认流程执行完成")
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

        logger.info("开始执行安徽分布式电源购电结算业票关联确认RPA")
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

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽分布式电源购电结算业票关联确认")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽分布式电源购电结算业票关联确认已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽分布式电源购电结算业票关联确认执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg = e, base_pw = base_robot, task_name = "安徽分布式电源购电结算业票关联确认")
        raise
    except Exception as e:
        logger.error(f"安徽分布式电源购电结算业票关联确认执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg = e, base_pw = base_robot, task_name = "安徽分布式电源购电结算业票关联确认")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
