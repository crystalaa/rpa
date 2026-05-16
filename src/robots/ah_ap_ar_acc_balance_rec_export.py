import os.path
import re
import time
from datetime import datetime
import os
import pandas as pd
from pathlib import Path

from playwright.sync_api import sync_playwright

from rpa_framework.core.base_pw import BasePw
from rpa_framework.utils.config import config
from rpa_framework.utils.email_util import send_rpa_success_notification, send_rpa_error_notification
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.utils.log import logger
from rpa_framework.utils.robot_exception import RobotsException

KEY_WORD = "期初往来数据与账务余额核对"
def generate_current_month(export_month: str = None) -> str:
    """
    获取指定日期数组的月份（默认当前日期），返回YYYYMM格式字符串数组

    参数:
        export_month : 指定日期字符串，元素格式为 'YYYYMM'

    返回:
        str: 月份字符串，格式为 'YYYYMM'

    异常:
        ValueError: 格式类型不支持，或数组元素非'YYYYMM'格式
    """

    # 定义YYYYMM格式的正则表达式（4位年份+2位月份，月份范围01-12）
    export_month_pattern = re.compile(r'^\d{4}(0[1-9]|1[0-2])$')

    # 处理默认值：返回当前日期的YYYYMM格式字符串
    if export_month is None == 0:
        current_date = datetime.now()
        current_month = f"{current_date.year}{current_date.month:02d}"
        return current_month


    # 再校验YYYYMM格式
    # 存在格式错误的元素，抛出异常并提示
    if not export_month_pattern.match(export_month):
        raise ValueError(f"数组元素格式错误，仅支持'YYYYMM'格式（4位年份+2位月份，月份01-12）：{export_month}（非YYYYMM格式）")

    # 格式全部合法，返回原数组
    return export_month


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
            '单位信息': {'header_row': 0}
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

# -------------------------- 合并EXCEL文件 核心逻辑 --------------------------
def find_merge_files():
    """
    合并所有下载文件（当data文件夹不存在时向上级目录查找）
    """
    try:
        # 1. 查找目标Excel文件
        file_keyword = KEY_WORD

        # 逐级向上查找data目录（最多查5级，避免无限循环）
        max_level = 5  # 最大向上查找层级
        current_dir = os.path.abspath(os.getcwd())  # 当前工作目录
        folder_path = None

        for level in range(max_level + 1):
            # 构建当前层级的data目录路径
            test_path = os.path.join(current_dir, 'data', file_keyword) if level == 0 else \
                os.path.join(current_dir, *['..']*level, 'data', file_keyword)
            test_path = os.path.abspath(test_path)

            if os.path.exists(test_path) and os.path.isdir(test_path):
                folder_path = test_path
                logger.info(f"在层级 {level} 找到目标目录: {folder_path}")
                break

        # 如果未找到包含关键词子文件夹，尝试直接在各级data目录查找文件
        if not folder_path:
            logger.warning(f"未找到包含关键词的子文件夹，尝试直接在data目录查找文件")
            for level in range(max_level + 1):
                test_data_dir = os.path.join(current_dir, 'data') if level == 0 else \
                    os.path.join(current_dir, *['..']*level, 'data')
                test_data_dir = os.path.abspath(test_data_dir)

                if os.path.exists(test_data_dir) and os.path.isdir(test_data_dir):
                    # 检查该data目录下是否有关键词文件
                    temp_files = find_target_excel_files(test_data_dir, file_keyword)
                    if temp_files:
                        folder_path = test_data_dir
                        logger.info(f"在层级 {level} 的data目录找到文件: {folder_path}")
                        break

        if not folder_path:
            raise FileNotFoundError(f"向上级查找{max_level}层后仍未找到data目录")

        target_files = find_target_excel_files(folder_path, file_keyword)

        # 2. 合并文件
        date_time_now = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = os.path.join(folder_path, f"{file_keyword}（合并）{date_time_now}.xlsx")
        merge_excel_files(target_files, output_path)

        logger.info(f"合并完成！合并文件保存至：{output_path}")
        logger.info(f"共合并 {len(target_files)} 个Excel文件")

    except Exception as e:
        logger.info(f"合并文件执行失败：{str(e)}")

def find_target_excel_files(folder_path: str, keyword: str):
    """查找指定文件夹下名称包含关键词的所有Excel文件"""
    target_files = []
    # 遍历文件夹
    for file in Path(folder_path).glob("*"):
        # 筛选Excel文件（.xlsx/.xls）且文件名包含关键词
        if file.suffix in [".XLSX", ".XLS"] and keyword in file.name:
            target_files.append(str(file))
            logger.info(f"找到目标文件: {file.name}")
    logger.info(f"共目标文件 {len(target_files)} 个。")
    if not target_files:
        raise FileNotFoundError(f"未找到包含关键词「{keyword}」的Excel文件")
    return target_files

def merge_excel_files(file_list, output_path):
    """合并多个Excel文件为一个（保留所有sheet，同名sheet内容纵向合并）"""
    # 创建字典用于存储所有工作表数据
    all_sheets = {}

    # 读取所有文件的所有工作表
    for file_path in file_list:
        file_name = os.path.basename(file_path)
        logger.info(f"开始读取文件: {file_name}")
        file_name_arr = file_name.split("-")
        # 读取当前Excel的所有sheet
        excel_file = pd.ExcelFile(file_path)
        for sheet_name in excel_file.sheet_names:
            # 读取单个sheet数据
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            # 添加导出单位名列（可选，用于追溯数据来源）
            df['导出单位'] = file_name_arr[0]
            # 添加导出月份名列（可选，用于追溯数据来源）
            df['导出月份'] = file_name_arr[1]

            # 如果工作表已存在则追加，否则新建
            if sheet_name in all_sheets:
                all_sheets[sheet_name] = pd.concat([all_sheets[sheet_name], df], ignore_index=True)
            else:
                all_sheets[sheet_name] = df

        logger.info(f"完成读取文件: {file_name}")

    # 将所有工作表写入到输出文件
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in all_sheets.items():
            # 写入合并后的数据，不保留索引
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        logger.info(f"所有文件合并完成，共 {len(all_sheets)} 个工作表")
# -------------------------- 合并EXCEL文件 核心逻辑 结束--------------------------



class LoginAndDirect:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽期初往来数据与账务余额核对导出")
        logger.debug("安徽期初往来数据与账务余额核对导出RPA初始化完成")

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

    def switch_department(self, export_comp_code: str, export_comp_name: str):
        """切换单位"""
        try:
            logger.info("第四步：切换登录单位", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("切换单位页面-下拉框", sleep=3000)

            # 定位搜索输入框，并填充
            unit = f"{export_comp_code} {export_comp_name}"
            self.base_pw.locate_and_fill("切换单位页面-搜索输入框", unit)
            # 动态生成选择器
            selector = f"div.header-unit-dialog div.unit-tree-item span:has-text('{export_comp_code}')"
            self.base_pw.page.locator(selector).click()
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)
            logger.info(f"单位 {export_comp_name} 切换成功")
        except Exception as e:
            logger.error(f"切换单位 {export_comp_name} 失败: {str(e)}")
            raise Exception(f"切换单位 {export_comp_name} 失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到”往来清账“页面"""
        try:
            logger.info("第三步：导航到”往来清账“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=3000)
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=3000)
            # 跳转到新的tab页
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-往来清账", sleep=1000)
                logger.debug(f'往来清账 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)

            logger.info("成功打开”往来清账“页面")
        except Exception as e:
            raise RobotsException(f"导航到”往来清账“页面失败: {str(e)}", e)

    def navigate_to_target_page(self):
        """导航到”期初往来数据与账务余额核对“页面"""
        try:
            logger.info("第五步：导航到”期初往来数据与账务余额核对“页面", extra={'color': 'darkcyan'})
            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-往来与账务余额核对-数据中台", sleep=3000)
            self.base_pw.set_page(page2.value)

            logger.info("成功打开”期初往来数据与账务余额核对“页面")
        except Exception as e:
            raise RobotsException(f"导航到”期初往来数据与账务余额核对“页面失败: {str(e)}", e)


class OperateQueryAndExportRobots:
    def __init__(self, base_robot: LoginAndDirect):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None
        logger.info("安徽期初往来数据与账务余额核对导出RPA初始化完成")

    def process_data(self, export_month_str: str, export_comp_name: str):
        """提交请求"""
        try:
            logger.info("第五步：处理”期初往来数据与账务余额核对“查询并导出数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")

            export_month = generate_current_month(export_month_str)
            self.base_pw.locate_and_fill("查询面板-核对基准月", export_month)
            self.base_pw.locate_and_click("查询面板-是否有差异", sleep=500)
            self.base_pw.locate_and_click("查询面板-是否有差异全部选项", sleep=500)

            """点击列设置按钮，设置列为全部显示"""

            # 1. 定位列设置按钮并点击
            self.base_pw.locate_and_click("查询面板-列设置", sleep=1000)

            # 2. 定位显示设置弹窗中“显示”选项并选中
            self.base_pw.locate_and_click("显示设置弹窗-显示", sleep=500)

            # 3. 定位显示设置弹窗中“确定”按钮并点击
            self.base_pw.locate_and_click("显示设置弹窗-确定", sleep=500)
            self.query_and_download(export_month, export_comp_name)

        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def query_and_download(self, export_month: str = None, export_comp_name: str = None):
        """
        查询并下载指定月份的期初往来数据与账务余额核对文件
        :raises RobotsException: 关键步骤超时/定位失败时抛出异常（含详细日志）
        """
        # 定义核心配置（便于维护）
        max_wait_time = 600  # 等待导出记录最大超时（秒）
        max_wait_export_success = 300  # 等待导出成功最大超时（秒）
        check_interval = 2  # 轮询检查间隔（秒）

        try:
            # 步骤1：点击查询按钮
            logger.info(f"开始执行查询操作...")
            self.base_pw.locate_and_click("查询面板-查询按钮", sleep=5000)

            # 步骤2：获取数据条数（兼容定位失败场景）
            try:
                total_count_selector = self.base_pw.selectors.get('查询面板-数据条数')
                logger.debug(f"数据条数定位符：{total_count_selector}")
                data_count_locator = self.base_pw.page.locator(total_count_selector)
                data_count = data_count_locator.count()
                logger.info(f"查询结果数据条数定位元素数量：{data_count}")
            except Exception as e:
                logger.error(f"获取数据条数定位失败，详情：{str(e)}", exc_info=True)
                data_count = 0  # 定位失败默认按有数据处理

            # 步骤3：执行导出操作
            if data_count == 0:
                logger.info(f"开始执行导出操作...")
                # 点击导出按钮
                try:
                    self.base_pw.locate_and_click("查询面板-导出", sleep=1000)
                except Exception as e:
                    logger.error(f"点击「查询面板-导出」按钮失败，详情：{str(e)}", exc_info=True)
                    raise RobotsException(f"点击导出按钮失败") from e

                # 点击导出确认
                try:
                    self.base_pw.locate_and_click("导出弹窗-导出确认", sleep=1000)
                except Exception as e:
                    logger.error(f"点击「导出弹窗-导出确认」按钮失败，详情：{str(e)}", exc_info=True)
                    raise RobotsException(f"点击导出确认按钮失败") from e

                # 点击导出管理
                try:
                    self.base_pw.locate_and_click("导出弹窗-导出管理", sleep=1000)
                except Exception as e:
                    logger.error(f"点击「导出弹窗-导出管理」按钮失败，详情：{str(e)}", exc_info=True)
                    raise RobotsException(f"点击导出管理按钮失败") from e

                # 等待导出管理页面加载完成
                try:
                    self.base_pw.page.wait_for_load_state("networkidle")
                    logger.info(f"导出管理页面加载完成")
                except Exception as e:
                    logger.error(f"导出管理页面加载超时/失败，详情：{str(e)}", exc_info=True)
                    raise RobotsException(f"导出管理页面加载失败（超时30秒）") from e

                # 步骤4：等待导出记录生成（带超时+参数化定位）
                export_flag = False
                row_locator = None
                formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                start_time = time.time()
                logger.info(f"开始等待导出记录生成（最大等待{max_wait_time}秒），目标时间：{formatted_time}")
                target_time = formatted_time[:16]
                while time.time() - start_time < max_wait_time:
                    try:
                        # 方式1：精确匹配任务名称+时间（到分钟）
                        row_locator = self.base_pw.page.locator(f"tr:has(td:nth-child(2) > div:has-text('{KEY_WORD}')):has(td:nth-child(3) > div:has-text('{target_time}'))")

                        if row_locator.count() > 0:
                            logger.info(f"通过「任务名称+时间」匹配到导出记录，数量：{row_locator.count()}")
                            export_flag = True
                            break

                        # 方式2：降级匹配（仅任务名称，取第一条）
                        all_target_rows = self.base_pw.page.locator(f"tr:has(td:nth-child(2) > div:has-text('{KEY_WORD}'))")
                        if all_target_rows.count() > 0:
                            row_locator = all_target_rows.first
                            logger.info(f"降级匹配：仅通过任务名称找到导出记录（取第一条）")
                            export_flag = True
                            break

                    except Exception as e:
                        logger.debug(f"本轮查找导出记录异常（忽略，继续轮询）：{str(e)}")

                    # 轮询间隔
                    time.sleep(check_interval)
                    elapsed = int(time.time() - start_time)
                    logger.debug(f"导出记录等待中，已耗时{elapsed}秒（剩余{max_wait_time - elapsed}秒）")

                # 导出记录超时判断
                if not export_flag:
                    error_msg = f"导出记录生成超时（{max_wait_time}秒），未匹配到目标记录"
                    logger.error(error_msg, exc_info=True)
                    raise RobotsException(error_msg)

                logger.info(f"导出记录定位成功")

                # 步骤5：等待文件导出成功（增加超时控制，避免无限等待）
                success = False
                success_start = time.time()
                logger.info(f"开始等待文件导出成功（最大等待{max_wait_export_success}秒）")

                while time.time() - success_start < max_wait_export_success:
                    try:
                        # 检查导出成功标识
                        success_locator = self.base_pw.locate_by_locator('导出弹窗-导出成功标识', row_locator).first
                        if success_locator.count() > 0:
                            # 验证元素可见（避免隐藏元素误判）
                            success_locator.wait_for(state="visible", timeout=5000)
                            logger.info(f"检测到导出成功标识，文件准备完成")
                            success = True
                            break
                    except Exception as e:
                        logger.debug(f"本轮未检测到导出成功标识：{str(e)}")

                    time.sleep(check_interval)
                    elapsed = int(time.time() - success_start)
                    logger.debug(f"导出成功等待中，已耗时{elapsed}秒（剩余{max_wait_export_success - elapsed}秒）")

                # 导出成功超时判断
                if not success:
                    error_msg = f"文件导出成功状态等待超时（{max_wait_export_success}秒）"
                    logger.error(error_msg, exc_info=True)
                    raise RobotsException(error_msg)

                # 步骤6：下载文件
                logger.info(f"开始下载文件...")
                try:
                    # 定位下载按钮（带等待）
                    export_button = self.base_pw.locate_by_locator(
                        "导出弹窗-下载", row_locator, timeout=10000, wait=True
                    )
                    # 等待下载事件
                    with self.base_pw.page.expect_download(timeout=30000) as download_info:
                        export_button.click()
                        logger.info(f"点击下载按钮，等待文件下载...")

                    # 等待下载完成
                    download = download_info.value
                    self.base_pw.page.wait_for_timeout(60000)  # 等待下载完成（超时60秒）

                    # 重命名并保存文件
                    original_file_name = download.suggested_filename
                    file_name_parts = os.path.splitext(original_file_name)
                    new_file_name = f"{export_comp_name}-{export_month}-{file_name_parts[0]}{file_name_parts[1]}".replace('\\', '_')
                    save_dir = 'data'
                    os.makedirs(save_dir, exist_ok=True)
                    save_path = os.path.join(save_dir, new_file_name)

                    # 保存文件
                    download.save_as(save_path)
                    logger.info(f"文件下载完成，保存路径：{save_path}")

                except Exception as e:
                    logger.error(f"文件下载失败，详情：{str(e)}", exc_info=True)
                    raise RobotsException(f"文件下载失败") from e

                # 步骤7：清理导出记录+关闭弹窗
                self.base_pw.page.wait_for_timeout(3000)
                # 点击清理按钮
                try:
                    clean_locator = self.base_pw.locate_by_locator("导出弹窗-清理", row_locator)
                    clean_locator.click()
                    logger.info(f"点击导出记录清理按钮成功")
                    self.base_pw.page.wait_for_timeout(3000)
                except Exception as e:
                    logger.error(f"点击清理按钮失败，详情：{str(e)}", exc_info=True)

                # 关闭导出管理弹窗
                try:
                    export_manage_close_locator = self.base_pw.page.locator(
                        self.base_pw.selectors.get('导出弹窗-导出管理关闭按钮')
                    ).last
                    export_manage_close_locator.wait_for(state="visible", timeout=5000)
                    export_manage_close_locator.click()
                    logger.info(f"关闭导出管理弹窗成功")

                    self.base_pw.locate_and_click("导出弹窗-导出关闭")
                    logger.info(f"关闭导出弹窗成功")
                except Exception as e:
                    logger.error(f"关闭导出弹窗失败，详情：{str(e)}", exc_info=True)

            else:
                logger.info(f"查询结果有数据（条数：{data_count}），无需导出")

        # 全局异常捕获：兜底所有未处理的异常，确保日志完整
        except RobotsException as e:
            logger.error(f"查询/下载流程执行失败（业务异常）：{str(e)}", exc_info=True)
            raise  # 重新抛出，不中断上层逻辑
        except Exception as e:
            error_msg = f"查询/下载流程执行失败（系统异常）：{str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RobotsException(error_msg) from e

    def run(self, username: str, password: str, export_comp_info: list, export_month: str):
        """运行完整的流程"""
        try:
            logger.debug("开始运行安徽期初往来数据与账务余额核对导出流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.navigate_to_trans_page()
            # 保存往来清账页面引用，用于循环中切换回来
            trans_page = self.base_pw.page
            for export_comp in export_comp_info:
                export_comp_code = export_comp.get("单位ID", "")
                export_comp_name = export_comp.get("单位名称", "")
                logger.debug(f'单位信息：{export_comp_code=};{export_comp_name=}')
                if export_comp_code == '' or export_comp_name == '':
                    continue
                self.base_robot.switch_department(export_comp_code, export_comp_name)
                self.base_robot.navigate_to_target_page()
                # 保存当前目标页面引用
                target_page = self.base_pw.page
                try:
                    self.process_data(export_month, export_comp_name)
                finally:
                    # 关闭当前目标页面
                    if target_page and not target_page.is_closed():
                        target_page.close()
                        logger.info(f"已关闭单位 {export_comp_name} 的导出页面")
                    # 切换回往来清账页面，准备处理下一个单位
                    self.base_pw.set_page(trans_page)
                    # 等待页面稳定
                    trans_page.wait_for_load_state("networkidle")
                    self.base_pw.page.wait_for_timeout(5000)

            # 将下载文件合并
            find_merge_files()

            result = {
                "success": True,
                # "data_file": excel_file_path,
                "result_screenshot": self.result_screenshot,
                "result_remark": self.result_remark,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')

            logger.debug("安徽期初往来数据与账务余额核对导出-查询导出流程执行完成")
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

        logger.info("开始执行安徽期初往来数据与账务余额核对导出")
        input_file = kwargs.get('input_file')
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        # 配置要读取的工作表
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
            '单位信息': {'header_row': 0},  # 第二个页签-单位信息(单位id, 单位名称)
        }
        all_data = read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        if len(login_info) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')
        username = login_info[0].get('登录账号', '')
        password = login_info[0].get('登录密码', '')
        base_url = login_info[0].get('登录地址', '')
        export_month = login_info[0].get('核对基准月', '')
        email_notif = login_info[0].get('发送通知邮件', '').strip().lower()

        logger.debug(f'登陆信息：{username=};{password=};{base_url=}')
        if password == '' or username == '' or base_url == '':
            raise RobotsException("Excel第一个页签中的登录信息不能为空！请检查！")
        export_comp_info = all_data['单位信息']
        if len(export_comp_info) < 1:
            raise RobotsException(f'“{input_file}” 第二个页签缺少单位信息')

        encryptor = Encryptor()
        password = encryptor.decrypt(password)

        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)

            with BasePw(playwright, show_browser, record_video) as base_pw:
                base_robot = LoginAndDirect(base_pw, base_url)
                operate_robot = OperateQueryAndExportRobots(base_robot)
                result = operate_robot.run(username, password, export_comp_info, export_month)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽期初往来数据与账务余额核对导出")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽期初往来数据与账务余额核对导出已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽期初往来数据与账务余额核对导出执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽期初往来数据与账务余额核对导出")
        raise
    except Exception as e:
        logger.error(f"安徽期初往来数据与账务余额核对导出执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽期初往来数据与账务余额核对导出")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
