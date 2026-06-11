from datetime import datetime, timedelta
from typing import Dict, Any
import re

from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification,send_rpa_error_notification
from urllib.parse import urlparse
import json


'''
1、修改载体维度明细
2、安徽多维凭证宽表增量派生任务
'''

class ReatedPartyTrans:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("西电配比支付")
        logger.debug("西电配比支付RPA初始化完成")

    def login(self, username: str, password: str):
        """登录系统"""
        try:
            logger.info("第一步：打开登录页面", extra={'color': 'darkcyan'})
            self.base_pw.page.goto(self.base_url)
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.page.wait_for_load_state("networkidle")
            logger.info("第二步：切换数据中心", extra={'color': 'darkcyan'})
            self.base_pw.page.get_by_role("textbox", name="请选择机构").click()
            self.base_pw.page.get_by_role("listitem").filter(has_text="中国西电电气股份有限公司").click()
            logger.info("第三步：输入账号密码，登录系统", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_fill("登录页面-用户名输入框", username)
            self.base_pw.locate_and_fill("登录页面-密码输入框", password)
            self.base_pw.locate_and_click("登录页面-登录单位", sleep=5000)
            self.base_pw.locate_and_click("登录页面-登录按钮", sleep=3000)
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            raise RobotsException(f"登录失败: {str(e)}", e)

    def switch_department(self, login_org_name: str):
        """切换单位"""
        try:
            logger.info("第三步：切换登录单位", extra={'color': 'darkcyan'})
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.locate_and_click("切换单位页面-下拉框", sleep=3000)
            unit_count = self.base_pw.page.locator(f"div span:has-text('{login_org_name}')").count()
            if unit_count == 1:
                self.base_pw.page.locator(f"div span:has-text('{login_org_name}')").click()
            elif unit_count > 1:
                self.base_pw.page.locator(f"div span:has-text('{login_org_name}')").first.click()
            else:
                raise Exception(f"未找到单位名称: {login_org_name}")
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第四步：开始导航到资金配比支付页面", extra={'color': 'darkcyan'})
            with self.base_pw.page.expect_popup(timeout=50000) as popup_info:
                self.base_pw.page.evaluate(
                    "window.open('/fmp-grm/fmp-cap-paysettle/gris/mapp/std-paysettle-web/dailyschedule/zjzfrpc.html')")
            new_page = popup_info.value
            self.base_pw.set_page(new_page)
            logger.info("成功打开资金配比支付页面")
        except Exception as e:
            raise RobotsException(f"导航到资金配比支付页面失败: {str(e)}", e)


class ProcessRobots:
    def __init__(self, base_robot: ReatedPartyTrans):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("西电配比支付RPA初始化完成")

    def process_data(self):
        """循环处理修改载体维度数据"""
        try:
            logger.info("第五步：处理配比支付流程", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("配比页面-更多链接")
            # 设置时间范围为当月
            logger.info("设置时间范围为当月", extra={'color': 'darkcyan'})
            self.base_pw.set_page(self.base_pw.get_main_page())

            # 获取当前日期，计算当月第一天和最后一天
            today = datetime.now()
            first_day = today.replace(day=1).strftime('%Y-%m-%d')
            # 获取当月最后一天
            if today.month == 12:
                last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            last_day_str = last_day.strftime('%Y-%m-%d')

            logger.info(f"设置开始时间: {first_day}, 结束时间: {last_day_str}")

            # 填充开始时间
            stime_locator = self.base_pw.locate_by_page("查询条件-开始时间输入框")
            stime_locator.fill(first_day)
            stime_locator.press("Enter")

            # 填充结束时间
            etime_locator = self.base_pw.locate_by_page("查询条件-结束时间输入框")
            etime_locator.fill(last_day_str)
            etime_locator.press("Enter")
            logger.info("时间范围设置完成")

            # 选择业务类型为员工报销
            logger.info("选择业务类型为员工报销", extra={'color': 'darkcyan'})
            ywlx_locator = self.base_pw.locate_by_page("查询条件-业务类型下拉")
            ywlx_locator.select_option(label="员工报销")
            logger.info("业务类型选择完成")

            # 选择支付方式为转账支付
            logger.info("选择支付方式为转账支付", extra={'color': 'darkcyan'})
            zffs_locator = self.base_pw.locate_by_page("查询条件-支付方式下拉")
            zffs_locator.select_option(label="转账支付")
            logger.info("支付方式选择完成")

            # 点击查询按钮，等待接口返回
            logger.info("点击查询按钮，等待数据加载", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("配比页面-查询按钮")
            self.base_pw.page.wait_for_load_state("networkidle")
            logger.info("查询接口已完成, 数据加载完毕")

            # 勾选收款银行账户名称少于4个汉字的数据行，每次最多勾选20条，并在方法内点击配比支付按钮
            self._check_filtered_rows()

            logger.info("西电配比支付RPA流程完成")
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def _count_chinese_chars(self, text: str) -> int:
        """统计字符串中的中文汉字数量

        使用正则匹配 Unicode 汉字区间 [\\u4e00-\\u9fff]，
        仅统计汉字字符数，不包括标点、数字、字母等。

        Args:
            text: 待统计的字符串

        Returns:
            中文汉字的个数
        """
        return len(re.findall(r'[\u4e00-\u9fff]', text))

    def _get_col_indices(self, table_id: str) -> dict:
        """从 ECP treeListGrid 表头动态获取关键列的索引

        ECP 表格的列顺序不固定，不同业务场景或配置下列的位置可能变化，
        因此需要在运行时从表头 DOM 中读取 fieldname 属性来定位列。
        本方法查找表格第2行（标题行）中所有带 fieldname 属性的 td，
        分别匹配 ROW_NO（序号）和 SKFYHZHMC（收款银行账户名称）两列，
        返回它们在可见列中的顺序索引，用于后续按索引取单元格内容。

        Args:
            table_id: 表格元素的 id，如 "zfpcTab"

        Returns:
            dict: {"rowNoIdx": int, "skfyzhmcIdx": int}
                  索引为 -1 表示未找到对应列
        """
        page = self.base_pw.page
        return page.evaluate(f'''() => {{
            const table = document.getElementById("{table_id}");
            if (!table) return null;
            // 第2行是标题行（tr:nth-child(2)），其中 td[fieldname] 标识了各列的字段名
            const headerCells = table.querySelectorAll("tr:nth-child(2) td[fieldname]");
            let rowNoIdx = -1, skfyzhmcIdx = -1;
            for (let i = 0; i < headerCells.length; i++) {{
                const fn = headerCells[i].getAttribute("fieldname");
                if (fn === "ROW_NO") rowNoIdx = i;
                if (fn === "SKFYHZHMC") skfyzhmcIdx = i;
            }}
            return {{ rowNoIdx, skfyzhmcIdx }};
        }}''')

    def _scroll_grid_to_top(self, table_id: str):
        """将 ECP treeListGrid 的滚动容器滚动到顶部

        ECP 的 treeListGrid 采用虚拟滚动，只有可视区域内的行才渲染到 DOM。
        每批次筛选前需要回到顶部，确保从头开始遍历所有数据行。
        滚动容器的定位策略：从表格元素的 parentElement 向上逐层查找，
        找到第一个 overflowY 为 auto/scroll 且 scrollHeight > clientHeight
        的元素即为滚动容器，将其 scrollTop 置 0；若未找到则回退到 window.scrollTo。

        Args:
            table_id: 表格元素的 id，如 "zfpcTab"
        """
        page = self.base_pw.page
        page.evaluate(f'''() => {{
            const table = document.getElementById("{table_id}");
            let el = table.parentElement;
            while (el) {{
                const style = window.getComputedStyle(el);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                    && el.scrollHeight > el.clientHeight) {{
                    el.scrollTop = 0;
                    return true;
                }}
                el = el.parentElement;
            }}
            // 未找到独立滚动容器，回退到页面级滚动
            window.scrollTo(0, 0);
            return false;
        }}''')
        page.wait_for_timeout(500)

    def _scroll_grid_down(self, table_id: str, scroll_step: int = 300) -> bool:
        """将 ECP treeListGrid 的滚动容器向下滚动一步

        配合虚拟滚动使用：向下滚动后，之前不可见的行会被渲染到 DOM 中，
        从而可以继续读取和勾选。滚动容器定位策略同 _scroll_grid_to_top。
        通过比较滚动前后的 scrollTop 判断是否已到达底部：
        - scrollTop 未变化 → 已到底部，返回 True
        - scrollTop 有变化 → 还可以继续滚动，返回 False

        Args:
            table_id: 表格元素的 id，如 "zfpcTab"
            scroll_step: 每次向下滚动的像素数，默认300px（约一行高度）

        Returns:
            bool: True 表示已到底部无法继续滚动，False 表示还可以继续滚动
        """
        page = self.base_pw.page
        return page.evaluate(f'''() => {{
            const table = document.getElementById("{table_id}");
            let el = table.parentElement;
            while (el) {{
                const style = window.getComputedStyle(el);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                    && el.scrollHeight > el.clientHeight) {{
                    const before = el.scrollTop;
                    el.scrollTop += {scroll_step};
                    // scrollTop 未变化说明已到底部
                    return el.scrollTop === before;
                }}
                el = el.parentElement;
            }}
            // 未找到独立滚动容器，回退到页面级滚动
            const before = window.pageYOffset;
            window.scrollBy(0, {scroll_step});
            return window.pageYOffset === before;
        }}''')

    def _get_visible_rows_info(self, table_id: str, row_no_idx: int, skfyzhmc_idx: int) -> list:
        """获取当前可视区域中未勾选的数据行信息

        由于 ECP treeListGrid 的虚拟滚动特性，DOM 中只包含当前可视区域内的行，
        需要配合 _scroll_grid_down 逐步滚动才能遍历所有数据。
        本方法读取当前 DOM 中所有可见行（跳过 display:none 的行和单元格），
        提取序号（ROW_NO，用于跨屏去重）、收款银行账户名称（SKFYHZHMC）的文本、
        复选框状态等信息。已勾选的行（存在 qzz_checked 类名）会被跳过。

        Args:
            table_id: 表格元素的 id，如 "zfpcTab"
            row_no_idx: 序号列在可见列中的索引（由 _get_col_indices 获取）
            skfyzhmc_idx: 收款银行账户名称列在可见列中的索引（由 _get_col_indices 获取）

        Returns:
            list[dict]: 每个元素包含:
                - rowIndex (int): 行在 table.querySelectorAll("tr") 中的索引
                - rowNo (str): 序号文本，用作跨屏去重的唯一键
                - cellText (str): 收款银行账户名称列的文本
                - hasCheckbox (bool): 是否有未勾选的复选框
        """
        page = self.base_pw.page
        return page.evaluate(f'''() => {{
            const table = document.getElementById("{table_id}");
            if (!table) return [];
            const rows = table.querySelectorAll("tr");
            const result = [];
            // 从第3行开始遍历（前2行分别是占位行和标题行）
            for (let i = 2; i < rows.length; i++) {{
                const row = rows[i];
                // 跳过整行隐藏的行
                if (row.style.display === "none") continue;

                // 只收集非 display:none 的可见单元格，按顺序建立索引
                // 因为 ECP 表格中部分列通过 display:none 隐藏，可见列顺序与全部列顺序不同
                const visibleCells = [];
                const allCells = row.querySelectorAll("td");
                for (let j = 0; j < allCells.length; j++) {{
                    if (allCells[j].style.display !== "none") {{
                        visibleCells.push(allCells[j]);
                    }}
                }}

                // 读取序号列文本，用于跨屏去重
                let rowNo = "";
                if ({row_no_idx} >= 0 && visibleCells.length > {row_no_idx}) {{
                    rowNo = visibleCells[{row_no_idx}].textContent.trim();
                }}

                // 读取收款银行账户名称列文本
                if (visibleCells.length <= {skfyzhmc_idx}) continue;
                const targetCell = visibleCells[{skfyzhmc_idx}];
                const cellText = targetCell ? targetCell.textContent.trim() : "";

                // 判断复选框状态：qzz_unchecked=未勾选，qzz_checked=已勾选
                const checkbox = row.querySelector(".checkBoxDiv .qzz_unchecked");
                const checkedBox = row.querySelector(".checkBoxDiv .qzz_checked");

                // 已勾选的行跳过，避免重复操作
                if (checkedBox) continue;

                result.push({{
                    rowIndex: i,
                    rowNo: rowNo,
                    cellText: cellText,
                    hasCheckbox: !!checkbox
                }});
            }}
            return result;
        }}''')

    def _click_row_checkbox(self, table_id: str, row_index: int):
        """点击指定行的复选框进行勾选

        通过 rowIndex 在表格所有 tr 中定位目标行，
        然后查找该行中 class 为 qzz_unchecked 的复选框元素并触发 click 事件。
        勾选后复选框的 class 会由 ECP 框架自动从 qzz_unchecked 变为 qzz_checked。

        Args:
            table_id: 表格元素的 id，如 "zfpcTab"
            row_index: 目标行在 table.querySelectorAll("tr") 中的索引位置
        """
        page = self.base_pw.page
        page.evaluate(f'''() => {{
            const table = document.getElementById("{table_id}");
            const row = table.querySelectorAll("tr")[{row_index}];
            const checkbox = row.querySelector(".checkBoxDiv .qzz_unchecked");
            if (checkbox) {{
                checkbox.click();
            }}
        }}''')

    def _check_filtered_rows(self):
        """
        勾选收款银行账户名称少于4个汉字的数据行，每次最多勾选20条。
        支持虚拟滚动：逐屏滚动表格，边滚动边筛选勾选。
        如果符合条件的行数超过20，则分批勾选并点击配比支付。
        收款银行账户名称列的下标不固定，需动态从表头获取。
        """
        page = self.base_pw.page
        table_id = "zfpcTab"
        max_per_batch = 20

        # 1. 从表头动态获取列索引
        col_indices = self._get_col_indices(table_id)
        if not col_indices or col_indices['skfyzhmcIdx'] == -1:
            raise RobotsException("未在表格表头中找到fieldname=SKFYHZHMC的列，无法筛选数据")

        row_no_idx = col_indices['rowNoIdx']
        skfyzhmc_col_index = col_indices['skfyzhmcIdx']
        logger.info(f"列索引 - 序号(ROW_NO): {row_no_idx}, 收款银行账户名称(SKFYHZHMC): {skfyzhmc_col_index}")

        # 2. 分批处理：每批最多勾选20条，点击配比支付后再处理下一批
        batch_count = 0
        while True:
            batch_count += 1
            logger.info(f"===== 第 {batch_count} 批次筛选数据 =====")

            # 滚动到顶部开始
            self._scroll_grid_to_top(table_id)
            page.wait_for_timeout(500)

            checked_count = 0
            seen_row_nos = set()
            no_new_rows_attempts = 0
            max_no_new_attempts = 5  # 连续多次滚动无新行时停止

            # 3. 逐屏滚动，边滚动边筛选勾选
            while checked_count < max_per_batch:
                # 获取当前可视区域的行信息
                rows_info = self._get_visible_rows_info(table_id, row_no_idx, skfyzhmc_col_index)

                # 过滤掉已处理过的行（通过序号去重）
                new_rows = []
                for info in rows_info:
                    row_key = info['rowNo'] or str(info['rowIndex'])
                    if row_key not in seen_row_nos:
                        seen_row_nos.add(row_key)
                        new_rows.append(info)

                if new_rows:
                    no_new_rows_attempts = 0
                    # 筛选并勾选符合条件的行
                    for info in new_rows:
                        if checked_count >= max_per_batch:
                            break
                        chinese_count = self._count_chinese_chars(info['cellText'])
                        if chinese_count < 4 and info['hasCheckbox']:
                            self._click_row_checkbox(table_id, info['rowIndex'])
                            checked_count += 1
                            logger.debug(
                                f"已勾选第{checked_count}条 - 行{info['rowIndex']}: "
                                f"收款银行账户名称='{info['cellText']}', 中文汉字数={chinese_count}"
                            )
                else:
                    no_new_rows_attempts += 1
                    if no_new_rows_attempts >= max_no_new_attempts:
                        logger.info(f"连续{max_no_new_attempts}次滚动无新行，当前屏数据已遍历完毕")
                        break

                if checked_count >= max_per_batch:
                    break

                # 向下滚动加载更多行
                reached_bottom = self._scroll_grid_down(table_id)
                page.wait_for_timeout(300)  # 等待虚拟滚动渲染新行

                if reached_bottom:
                    # 到底部后再做一次最终检查
                    final_rows = self._get_visible_rows_info(table_id, row_no_idx, skfyzhmc_col_index)
                    for info in final_rows:
                        row_key = info['rowNo'] or str(info['rowIndex'])
                        if row_key not in seen_row_nos:
                            seen_row_nos.add(row_key)
                            if checked_count < max_per_batch:
                                chinese_count = self._count_chinese_chars(info['cellText'])
                                if chinese_count < 4 and info['hasCheckbox']:
                                    self._click_row_checkbox(table_id, info['rowIndex'])
                                    checked_count += 1
                                    logger.debug(
                                        f"已勾选第{checked_count}条 - 行{info['rowIndex']}: "
                                        f"收款银行账户名称='{info['cellText']}', 中文汉字数={chinese_count}"
                                    )
                    logger.info("已滚动到表格底部，遍历完成")
                    break

            logger.info(f"第 {batch_count} 批次共勾选 {checked_count} 条数据")

            # 4. 点击配比支付按钮
            if checked_count > 0:
                self.base_pw.locate_and_click("配比页面-配比支付按钮", sleep=1000)
                logger.info(f"第 {batch_count} 批次配比支付按钮已点击")

                # 等待配比支付请求完成（请求耗时不确定，等待网络空闲）
                page.wait_for_load_state("networkidle")
                logger.info(f"第 {batch_count} 批次配比支付请求已完成")

                # 请求结束后会弹出提示弹窗，点击确定按钮关闭
                # 弹窗按钮文本可能是"确定"或"确 定"（中间有空格），用正则忽略空格
                try:
                    confirm_btn = page.get_by_role(
                        "button", name=re.compile(r"确\s*定")
                    )
                    confirm_btn.wait_for(state="visible", timeout=10000)
                    confirm_btn.click()
                    logger.info(f"第 {batch_count} 批次弹窗确定按钮已点击")
                except Exception as e:
                    logger.warning(f"第 {batch_count} 批次未找到弹窗确定按钮: {e}")
            else:
                logger.info("没有符合条件的行（收款银行账户名称少于4个汉字），处理完成")
                break

            # 如果本批勾选不足20条，说明已无更多符合条件的数据
            if checked_count < max_per_batch:
                logger.info("所有符合条件的数据已处理完成")
                break

            # 等待页面刷新后继续下一批
            page.wait_for_load_state("networkidle")
            logger.info(f"第 {batch_count} 批次处理完成，准备下一批次")

    def run(self, username: str, password: str, login_org_name: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行西电配比支付RPA流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.switch_department(login_org_name)
            self.base_robot.navigate_to_trans_page()
            self.base_pw = self.base_robot.base_pw
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

            logger.debug("西电配比支付RPA执行完成")
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
    """
    try:
        logger.debug(f'============ start {__name__} ===========')
        logger.debug(f"start ahdl_workorder robots with parameters:{kwargs}")

        logger.info("开始执行西电配比支付流程")
        base_robot = None
        input_file = kwargs.get('input_file')
        # input_file = r'data/安徽电力资金协同审核.xlsx'
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        data = excel_utils.read_excel()
        # 访问各页签数据

        if len(data) < 1:
            raise RobotsException(f'"{input_file}" 第一个页签缺少登录信息')

        username = data[0].get('登录账号', '')
        password = data[0].get('登录密码', '')
        base_url = data[0].get('登录地址', '')
        email_notif = data[0].get('发送通知邮件', '').strip().lower()
        login_org_name = data[0].get('登录单位名称', '')

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
                process_robot = ProcessRobots(base_robot)
                result = process_robot.run(username, password, login_org_name)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="西电配比支付")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("西电配比支付RPA已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"西电配比支付流程执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "西电配比支付")
        raise
    except Exception as e:
        logger.error(f"西电配比支付流程执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "西电配比支付")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
