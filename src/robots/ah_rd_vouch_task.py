from datetime import datetime
import os
from pathlib import Path

from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification
from urllib.parse import urlparse
import json
import re
import pandas as pd

'''
研发支出人工成本切换凭证导入任务
'''


class RdVouchTrans:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("研发支出人工成本切换凭证导入任务")
        logger.debug("研发支出人工成本切换凭证导入任务RPA初始化完成")

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
            continue_login = self.base_pw.page.get_by_role("button", name="继续登录")
            if continue_login.count() > 0:
                continue_login.click()
                self.base_pw.page.wait_for_timeout(3000)
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            raise RobotsException(f"登录失败: {str(e)}", e)

    def switch_department(self, department_name: str):
        """切换单位"""
        try:
            logger.info(f"第三步：切换到单位 - {department_name}", extra={'color': 'darkcyan'})
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locate_and_click("切换单位页面-下拉框", sleep=3000)
            # page.get_by_role("link", name="组织1500 ").click()
            # self.base_pw.page.get_by_role("textbox", name="输入关键字", exact=True).click()
            # self.base_pw.page.get_by_role("textbox", name="输入关键字", exact=True).fill(department_name)
            unit_count = self.base_pw.page.locator(f"div span:has-text('{department_name}')").count()
            if unit_count == 0:
                input_loc = self.base_pw.page.get_by_placeholder("输入关键字")
                if input_loc.count() == 1:
                    input_loc.fill(department_name)
                    self.base_pw.page.locator(f"div span:has-text('{department_name}')").click()
                elif input_loc.count() > 1:
                    input_loc.first.fill(department_name)
                    self.base_pw.page.locator(f"div span:has-text('{department_name}')").click()
            elif unit_count == 1:
                self.base_pw.page.locator(f"div span:has-text('{department_name}')").click()
            else:
                self.base_pw.page.locator(f"div span:has-text('{department_name}')").first.click()

            logger.info(f"单位切换成功: {department_name}")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")


class ProcessRobots:
    def __init__(self, base_robot: RdVouchTrans = None):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw if base_robot else None
        self.base_url = base_robot.base_url if base_robot else None
        self.debug_mode = False
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("研发支出人工成本切换凭证导入任务——RPA初始化完成")

    def split_excel_by_unit(self, data_info: list, output_dir: str):
        """按单位拆分Excel文件，并将单位与账号信息关联"""
        try:
            logger.info("开始按单位拆分Excel文件", extra={'color': 'darkcyan'})

            # 直接从data_info构建DataFrame
            df = pd.DataFrame(data_info)

            # 确保单位列存在
            if '单位名称' not in df.columns:
                raise Exception("Excel文件中缺少'单位名称'列")

            # 按单位分组
            grouped = df.groupby('单位名称')

            # 创建输出目录
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            split_files = []

            for unit_name, unit_df in grouped:
                # 去掉单位列
                unit_df = unit_df.drop(columns=['单位名称', '__row__'], errors='ignore')

                # 生成文件名（单位名称作为文件名，去除特殊字符）
                safe_name = unit_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                output_file = os.path.join(output_dir, f"{safe_name}.xlsx")

                # 保存Excel
                unit_df.to_excel(output_file, index=False, engine='openpyxl')

                split_files.append({
                    'unit_name': unit_name,
                    'file_path': output_file,
                    'record_count': len(unit_df)
                })

                logger.info(f"已生成单位文件: {unit_name}, 记录数: {len(unit_df)}, 文件路径: {output_file}")

            logger.info(f"Excel拆分完成，共生成 {len(split_files)} 个单位文件", extra={'color': 'green'})
            return split_files

        except Exception as e:
            raise RobotsException(f"Excel拆分失败: {str(e)}", e)

    def match_unit_accounts(self, login_info_list: list, unit_names: list):
        """将单位名称与账号信息匹配"""
        try:
            logger.info("开始匹配单位与账号信息", extra={'color': 'darkcyan'})

            # 创建单位到账号的映射
            unit_account_map = {}

            for account_info in login_info_list:
                account_unit_name = account_info.get('单位名称', '').strip()
                if not account_unit_name:
                    continue

                # 查找匹配的单位
                for unit_name in unit_names:
                    if account_unit_name in unit_name or unit_name in account_unit_name:
                        unit_account_map[unit_name] = {
                            'username': account_info.get('登录账号', ''),
                            'password': account_info.get('登录密码', ''),
                            'base_url': account_info.get('登录地址', '')
                        }
                        logger.info(f"匹配成功: 单位'{unit_name}' 使用账号'{account_info.get('登录账号', '')}'")
                        break

            # 检查是否所有单位都找到了对应的账号
            unmatched_units = [unit for unit in unit_names if unit not in unit_account_map]
            if unmatched_units:
                logger.warning(f"以下单位未找到匹配的账号: {unmatched_units}")
                raise Exception(f"以下单位未找到匹配的账号: {', '.join(unmatched_units)}")

            logger.info(f"单位账号匹配完成，共匹配 {len(unit_account_map)} 个单位", extra={'color': 'green'})
            return unit_account_map

        except Exception as e:
            raise RobotsException(f"单位账号匹配失败: {str(e)}", e)

    def process_unit_data(self, unit_info: dict):
        """处理单个单位的数据（业务逻辑待定）"""
        try:
            unit_name = unit_info.get('unit_name', '')
            file_path = unit_info.get('file_path', '')

            logger.info(f"开始处理单位数据: {unit_name}", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=1000)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.set_page(self.base_pw.context.pages[self.base_pw.context.pages.__len__() - 1])
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=1000)
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-账务处理及查询", sleep=1000)
                logger.debug(f'账务处理及查询 popped up , {page1.value}')
            self.base_pw.set_page(page1.value)

            with self.base_pw.page.expect_popup() as page3_info:
                self.base_pw.page.get_by_text("财务记账单导入").click()
            self.base_pw.set_page(page3_info.value)

            file_input = self.base_pw.page.locator("input[type='file']")
            file_input.set_input_files(file_path)
            self.base_pw.page.wait_for_timeout(30000)

            # 点击数据检查按钮
            logger.info(f"点击数据检查按钮", extra={'color': 'darkcyan'})

            resp_url = "validateImportedData"
            with self.base_pw.page.expect_response(lambda response: resp_url in response.url,
                                                   timeout=30000) as response_info:
                # self.base_pw.page.locator("#syncWdRelation").click()
                self.base_pw.locate_and_click("财务记账单导入-数据检查按钮", sleep=3000)
            if response_info.is_done():
                self.base_pw.locate_and_click("财务记账单导入-确认按钮", sleep=1000)
                # 检查导入按钮是否可用（置灰则说明数据检查未通过）
                import_btn = self.base_pw.locate_by_page("财务记账单导入-导入按钮")
                if import_btn.is_disabled():
                    logger.error(f"单位 {unit_name} 数据检查未通过，导入按钮置灰，异常退出")
                    raise RobotsException(f"单位 {unit_name} 数据检查未通过，导入按钮置灰，无法导入")

                # 数据检查通过，点击导入按钮
                logger.info(f"数据检查通过，点击导入按钮", extra={'color': 'darkcyan'})
                self.base_pw.locate_and_click("财务记账单导入-导入按钮", sleep=3000)
                self.base_pw.page.wait_for_load_state("networkidle")
                logger.info(f"单位 {unit_name} 导入操作已执行")

                logger.info(f"单位 {unit_name} 数据处理完成")

        except Exception as e:
            logger.error(f"处理单位 {unit_name} 数据失败: {str(e)}")
            raise RobotsException(f"处理单位数据失败: {str(e)}", e)

    def run(self, kwargs: dict, input_file: str, data_info: list, login_info_list: list):
        """运行完整的流程，每个单位使用各自的账号登录"""
        try:
            logger.debug("开始运行研发支出人工成本切换凭证导入任务流程")

            # 1. 拆分Excel文件
            output_dir = os.path.join(os.path.dirname(input_file), "split_files")
            split_files = self.split_excel_by_unit(data_info, output_dir)

            # 2. 匹配单位与账号信息
            unit_names = [unit_info['unit_name'] for unit_info in split_files]
            unit_account_map = self.match_unit_accounts(login_info_list, unit_names)

            # 3. 为每个单位创建独立的登录会话并处理数据
            failed_units = []
            success_units = []

            for unit_info in split_files:
                unit_name = unit_info['unit_name']
                file_path = unit_info['file_path']

                try:
                    logger.info(f"========== 开始处理单位: {unit_name} ==========", extra={'color': 'green'})

                    # 获取该单位的账号信息
                    account_info = unit_account_map.get(unit_name)
                    if not account_info:
                        logger.error(f"单位 {unit_name} 未找到对应的账号信息")
                        failed_units.append(unit_name)
                        continue

                    # 解密密码
                    encryptor = Encryptor()
                    unit_password = encryptor.decrypt(account_info['password'])

                    # 为每个单位创建独立的浏览器会话
                    with sync_playwright() as playwright:
                        show_browser = kwargs.get("show_browser", False)
                        record_video = kwargs.get("record_video", False)

                        with BasePw(playwright, show_browser, record_video) as base_pw:
                            # 初始化浏览器
                            base_pw.init_browser()

                            # 创建该单位的robot实例
                            unit_robot = RdVouchTrans(base_pw, account_info['base_url'])

                            # 登录系统
                            unit_robot.login(account_info['username'], unit_password)
                            unit_robot.switch_department(unit_name)

                            # 处理该单位的数据
                            self._process_unit_with_login(base_pw, unit_name, file_path)

                            # 记录成功的单位
                            success_units.append(unit_name)
                            logger.info(f"========== 单位 {unit_name} 处理成功 ==========", extra={'color': 'green'})

                except Exception as e:
                    logger.error(f"处理单位 {unit_name} 失败: {str(e)}", exc_info=True)
                    failed_units.append(unit_name)
                    # 继续处理下一个单位
                    continue

            # 生成结果报告
            result = {
                "success": len(failed_units) == 0,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path() if hasattr(self, 'base_pw') else None,
                "split_files": split_files,
                "success_count": len(success_units),
                "failed_count": len(failed_units),
                "success_units": success_units,
                "failed_units": failed_units
            }

            # 生成总结信息
            summary = f"处理完成：成功 {len(success_units)} 个单位，失败 {len(failed_units)} 个单位"
            if failed_units:
                summary += f"\n失败单位：{', '.join(failed_units)}"

            self.result_remark = summary
            logger.info(summary, extra={'color': 'green'})

            logger.debug("研发支出人工成本切换凭证导入任务流程执行完成")
            return result

        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {str(e)}", e)

    def _process_unit_with_login(self, base_pw: BasePw, unit_name: str, file_path: str):
        """处理已登录单位的数据"""
        try:
            logger.info(f"开始处理单位数据: {unit_name}", extra={'color': 'darkcyan'})

            base_pw.locate_and_click("页面导航-共享财务中心", sleep=1000)
            base_pw.page.wait_for_load_state("networkidle")
            base_pw.set_page(base_pw.context.pages[base_pw.context.pages.__len__() - 1])
            base_pw.locate_and_click("页面导航-会计核算报告", sleep=1000)
            with base_pw.page.expect_popup() as page1:
                base_pw.locate_and_click("页面导航-账务处理及查询", sleep=1000)
                logger.debug(f'账务处理及查询 popped up , {page1.value}')
            base_pw.set_page(page1.value)

            with base_pw.page.expect_popup() as page3_info:
                base_pw.page.get_by_text("财务记账单导入").click()
            base_pw.set_page(page3_info.value)

            file_input = base_pw.page.locator("input[type='file']")
            file_input.set_input_files(file_path)
            base_pw.page.wait_for_load_state("networkidle")
            base_pw.page.wait_for_timeout(3000)
            conform_btn = base_pw.page.get_by_role("button", name=re.compile(r"确\s*定") )
            if conform_btn.count() > 0 :
                conform_btn.click()

            check_btn = base_pw.page.locator("#checkDataBtn")
            if check_btn.is_enabled():
                # 点击数据检查按钮
                logger.info(f"点击数据检查按钮", extra={'color': 'darkcyan'})

                resp_url = "validateImportedData"
                with base_pw.page.expect_response(lambda response: resp_url in response.url,
                                                  timeout=30000) as response_info:
                    base_pw.locate_and_click("财务记账单导入-数据检查按钮", sleep=3000)

                if response_info.is_done():
                    # base_pw.locate_and_click("财务记账单导入-确认按钮", sleep=1000)
                    base_pw.page.wait_for_timeout(2000)
                    conform_btn1 = base_pw.page.get_by_role("button", name=re.compile(r"确\s*定"))
                    if conform_btn1.count() > 0:
                        conform_btn1.click()
                    # 检查导入按钮是否可用（置灰则说明数据检查未通过）
                    import_btn = base_pw.page.locator("#importBtn")
                    if import_btn.is_disabled():
                        logger.error(f"单位 {unit_name} 数据检查未通过，导入按钮置灰，异常退出")
                        raise RobotsException(f"单位 {unit_name} 数据检查未通过，导入按钮置灰，无法导入")

                    # 数据检查通过，点击导入按钮
                    logger.info(f"数据检查通过，点击导入按钮", extra={'color': 'darkcyan'})
                    base_pw.locate_and_click("财务记账单导入-导入按钮", sleep=3000)
                    base_pw.page.wait_for_load_state("networkidle")
                    logger.info(f"单位 {unit_name} 导入操作已执行")

                    logger.info(f"单位 {unit_name} 数据处理完成")
            else:
                logger.info("数据检查按钮置灰不可点击")
        except Exception as e:
            logger.error(f"处理单位 {unit_name} 数据失败: {str(e)}")
            raise RobotsException(f"处理单位数据失败: {str(e)}", e)


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
            - input_file (str): 输入Excel文件路径
    """
    try:
        logger.debug(f'============ start {__name__} ===========')
        logger.debug(f"start rd_vouch_task robots with parameters:{kwargs}")

        logger.info("开始执行研发支出人工成本切换凭证导入任务流程")
        base_robot = None
        input_file = kwargs.get('input_file')

        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        sheet_configs = {
            '登录信息': {'header_row': 0},
            '财务记账单': {'header_row': 0}

        }
        all_data = ExcelUtils.read_multiple_sheets(excel_utils, sheet_configs)
        login_info_list = all_data['登录信息']
        data_info = all_data['财务记账单']

        if len(login_info_list) < 1:
            raise RobotsException(f'"{input_file}" 第一个页签缺少登录信息')

        # 检查是否有多个单位的登录信息
        first_login = login_info_list[0]
        email_notif = first_login.get('发送通知邮件', '').strip().lower()

        # 验证登录信息的完整性
        for idx, login_info in enumerate(login_info_list):
            unit_name = login_info.get('单位名称', '')
            username = login_info.get('登录账号', '')
            password = login_info.get('登录密码', '')
            base_url = login_info.get('登录地址', '')

            if not unit_name or not password or not username or not base_url:
                raise RobotsException(
                    f"Excel登录信息页签第{idx + 2}行的登录信息不完整！单位名称、登录账号、密码和登录地址不能为空！")

            logger.debug(f'登录信息 {idx + 1}: 单位={unit_name}, 账号={username}')

        # 创建一个临时的base_robot用于邮件通知
        base_robot = None
        debug_mode = kwargs.get("debug_mode", False)

        # 创建ProcessRobots实例（不需要base_robot）
        process_robot = ProcessRobots(None)
        process_robot.debug_mode = debug_mode

        # 执行任务
        result = process_robot.run(kwargs, input_file, data_info, login_info_list)

        # 发送邮件通知
        if email_notif not in ['', '否', 'n', 'no', '不发送']:
            send_email_notification(result=result, task_name="研发支出人工成本切换凭证导入任务流程")
        else:
            logger.debug("通知邮件已关闭")

        logger.info("研发支出人工成本切换凭证导入任务流程已完成", extra={'color': 'green'})
        logger.debug(f"result: {result}")
        return result

    except RobotsException as e:
        logger.error(f"研发支出人工成本切换凭证导入任务流程执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="研发支出人工成本切换凭证导入任务流程")
        raise
    except Exception as e:
        logger.error(f"研发支出人工成本切换凭证导入任务流程执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg=e, base_pw=base_robot, task_name="研发支出人工成本切换凭证导入任务流程")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
