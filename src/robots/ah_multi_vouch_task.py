from datetime import datetime
from typing import Dict, Any

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
        self.base_pw.load_selectors("安徽多维凭证宽表增量派生任务")
        logger.debug("安徽多维凭证宽表增量派生任务RPA初始化完成")

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
            self.base_pw.locate_and_click("切换单位页面-选择单位")
            logger.info("单位切换成功")
        except Exception as e:
            logger.error(f"切换单位失败: {str(e)}")
            raise Exception(f"切换单位失败: {str(e)}")

    def navigate_to_trans_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第四步：开始导航到载体维度明细页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=1000)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.set_page(self.base_pw.context.pages[self.base_pw.context.pages.__len__() - 1])
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=1000)
            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-账务处理及查询",sleep=1000)
                logger.debug(f'账务处理及查询 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)

            # 尝试点击载体维度明细，可能是弹窗也可能是当前页面跳转
            try:
                # 首先尝试作为弹窗处理
                with self.base_pw.page.expect_popup(timeout=50000) as page2:
                    self.base_pw.locate_and_click("页面导航-载体维度明细",sleep=2000)
                self.base_pw.set_page(page2.value)
                logger.info("成功通过弹窗打开载体维度明细页面")
            except Exception as popup_error:
                logger.warning(f"未检测到弹窗，尝试在当前页面处理: {popup_error}")
                # 如果没有弹窗，可能是当前页面跳转
                self.base_pw.page.wait_for_timeout(20000)
                # 检查是否有新页面打开
                if len(self.base_pw.context.pages) > 1:
                    # 使用最新打开的页面
                    self.base_pw.set_page(self.base_pw.context.pages[-1])
                    logger.info("切换到最新打开的页面")
                else:
                    # 使用当前页面
                    logger.info("在当前页面继续操作")

            logger.info("成功打开载体维度明细页面")
        except Exception as e:
            raise RobotsException(f"导航到载体维度明细页面失败: {str(e)}", e)


class ProcessRobots:
    def __init__(self, base_robot: ReatedPartyTrans):
        self.base_robot = base_robot
        self.base_pw = base_robot.base_pw
        self.base_url = base_robot.base_url
        self.debug_mode = base_robot.debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.result_screenshot = None
        self.result_remark = None

        logger.info("安徽多维凭证宽表增量派生任务——修改载体维度 RPA初始化完成")

    def modify_carrier_dimension(self, dim_info: list, modify_time_str: str):
        """循环处理修改载体维度数据"""
        try:
            logger.info("第四步：处理修改载体维度数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.locate_and_click("修改载体维度-载体维度类型", sleep=1000)
            self.base_pw.locate_and_click("修改载体维度-工程项目", sleep=1000)
            if not dim_info:
                logger.warning("载体维度明细数据为空，跳过处理")
                return

            for index, dim_item in enumerate(dim_info):
                logger.info(f"正在处理第 {index + 1}/{len(dim_info)} 条载体维度明细")
                try:
                    self._process_single_dimension(index, dim_item, modify_time_str)
                except Exception as e:
                    logger.error(f"处理第 {index + 1} 条载体维度明细失败: {str(e)}")
                    raise

            logger.info("安徽多维凭证宽表增量派生任务——修改载体维度明细全部完成")
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def _process_single_dimension(self, index, dim_item: dict, modify_time_str: str):
        """提交请求"""
        try:
            project_code = dim_item.get('项目编码', '')
            if not project_code:
                logger.warning(f"载体维度明细记录缺少项目编码，跳过: {dim_item}")
                return
            logger.info(f"开始处理项目编码: {project_code}", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")

            self.base_pw.locate_and_click("修改载体维度-载体对象列表", sleep=1000)
            resp_url_more = "getPopDxData"
            with self.base_pw.page.expect_response(lambda response: resp_url_more in response.url,
                                                   timeout=30000) as response_more_info:
                self.base_pw.locate_and_click("修改载体维度-更多链接", sleep=1000)

            self.base_pw.locate_and_click("修改载体维度-载体对象名称", sleep=1000)
            self.base_pw.locate_and_click("修改载体维度-项目编码", sleep=1000)
            self.base_pw.locate_and_click("修改载体维度-输入关键字", sleep=1000)
            self.base_pw.locate_and_fill("修改载体维度-输入关键字", project_code, sleep=1000)

            resp_url_dx = "getPopDxData"
            responses_dx = []

            def on_response(response):
                if resp_url_dx in response.url:
                    responses_dx.append(response)

            self.base_pw.page.on("response", on_response)
            self.base_pw.locate_and_click("修改载体维度-管理对象查询按钮", sleep=5000)
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.remove_listener("response", on_response)

            if responses_dx:
                last_response = responses_dx[-1]
                # logger.info(f"last_response：{last_response}")
                response_dx_text = last_response.text()
                # logger.info(f"查询当前共享项目返回值response_dx_text：{response_dx_text}")
                # 清理可能存在的控制字符
                def clean_json_string(json_str):
                    # 移除JSON字符串中的控制字符
                    return ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')

                response_dx_text = clean_json_string(response_dx_text)
                response_dx_json = json.loads(response_dx_text)
                # logger.info(f"查询当前共享项目返回值response_dx_json：{response_dx_json}")

                gldx_list = response_dx_json.get('data')
                project_name = gldx_list[0].get('dxmc')
                self.base_pw.page.get_by_label("修改记录的开始时间").get_by_role("row", name="序号", exact=True).locator("div").nth(1).click()
                logger.info("已选中查询结果")

                self.base_pw.locate_and_click("修改载体维度-管理对象确定", sleep=3000)
                resp_url_sync = "syncAccDimValRelByMap"
                with self.base_pw.page.expect_response(lambda response: resp_url_sync in response.url,
                                                       timeout=30000) as response_sync_info:
                    self.base_pw.locate_and_click("修改载体维度-同步按钮", sleep=3000)
                if response_sync_info.is_done():
                    self.base_pw.locate_and_click("修改载体维度-关闭", sleep=1000)
                    if index == 0:
                        self.base_pw.locate_and_click("修改载体维度-不显示", sleep=1000)
                        self.base_pw.locate_and_click("修改载体维度-显示选项", sleep=1000)
                    resp_url = "listDimValRel"
                    with self.base_pw.page.expect_response(lambda response: resp_url in response.url,
                                                           timeout=30000) as response_info1:
                        self.base_pw.locate_and_click("修改载体维度-查询按钮", sleep=1000)
                    if response_info1.is_done():
                        res_result_text = response_info1.value.text()
                        response_json = json.loads(res_result_text)
                        response_data = response_json.get('data').get('datas')
                        logger.info(f"当前查询结果数据：{response_data}")
                        response_count = response_json.get('data').get('total')
                        now = datetime.now()
                        #当月第一天
                        first_day = now.replace(day=1)
                        first_day_str= first_day.strftime("%Y-%m-%d")
                        if response_count != 0:
                            dxmc = response_data[0].get('dxmc')
                            for i in range(response_count):
                                try:
                                    close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                    if close_loc.count() > 0:
                                        close_loc.click()
                                    row_loc_count = self.base_pw.page.get_by_text(str(i + 1), exact=True).count()
                                    logger.warning(str(i + 1))
                                    if row_loc_count == 1:
                                        self.base_pw.page.get_by_text(str(i + 1), exact=True).click()
                                        logger.warning("111")
                                    elif row_loc_count > 1:
                                        self.base_pw.page.get_by_text(str(i + 1), exact=True).first.click()
                                        logger.warning("222")
                                    current_data = response_data[i]
                                    wd_type = current_data.get('wd_type')
                                    etime = current_data.get('etime')
                                    stime = current_data.get('stime')
                                    if str(wd_type) == "0" and etime == "3000-01-01":
                                        # 将同类型的载体属性停用时间为3000-1-1的这条数据，开始时间修改为当月1日
                                        if stime <= modify_time_str:
                                            logger.warning("场景1，当前数据开始时间早于要修改的时间，不做处理")
                                            # close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                            # if close_loc.count() > 0:
                                            #     close_loc.click()
                                            continue

                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#ydate").get_by_text(stime).click()
                                        self.base_pw.page.locator("#ydate").get_by_role("textbox").fill(modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    elif str(wd_type) == "0" and etime != "3000-01-01":
                                        # 将同类型的载体属性停用时间非3000-1-1的这条数据，结束时间修改为当月1日
                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#endDate").get_by_text(etime).click()
                                        self.base_pw.page.get_by_role("row", name=etime, exact=True).locator("div").nth(
                                            2).click()
                                        self.base_pw.page.locator("#endDate").get_by_role("textbox").fill(
                                            modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    elif str(wd_type) == "1" and etime == "3000-01-01":
                                        # 将不存在多条同类型的载体属性的，停用时间为3000 - 1 - 1 的这条数据，开始时间修改为当月1日
                                        if stime <= modify_time_str:
                                            logger.warning("场景3，当前数据开始时间早于要修改的时间，不做处理")
                                            # close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                            # if close_loc.count() > 0:
                                            #     close_loc.click()
                                            continue
                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#ydate").get_by_text(stime).click()
                                        self.base_pw.page.locator("#ydate").get_by_role("textbox").fill(modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    else:
                                        continue
                                except Exception as e:
                                    logger.warning("使用playwright locator触发选择失败，，")
                                    row_num = i + 1
                                    row_num_str = str(row_num)
                                    self.click_grid_cell("WdRelationMxQueryGrid", i, "dxmc")
                                    current_data = {}
                                    current_data = self.base_pw.page.evaluate(
                                        """         () => $("#WdRelationMxQueryGrid").qzzquerygrid(true).getSelectedRowData()     """)

                                    logger.info(f"当前查询表格选中数据，第{row_num_str}行：：{current_data}")

                                    # 1业务分类不同类型， 0管理对象同类型
                                    wd_type = current_data.get('wd_type')
                                    etime = current_data.get('etime')
                                    stime = current_data.get('stime')
                                    if str(wd_type) == "0" and etime == "3000-01-01":
                                        # 将同类型的载体属性停用时间为3000-1-1的这条数据，开始时间修改为当月1日
                                        if stime <= modify_time_str:
                                            logger.warning("场景1，当前数据开始时间早于要修改的时间，不做处理")
                                            # close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                            # if close_loc.count() > 0:
                                            #     close_loc.click()
                                            continue

                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#ydate").get_by_text(stime).click()
                                        self.base_pw.page.locator("#ydate").get_by_role("textbox").fill(modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    elif str(wd_type) == "0" and etime != "3000-01-01":
                                        # 将同类型的载体属性停用时间非3000-1-1的这条数据，结束时间修改为当月1日
                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#endDate").get_by_text(etime).click()
                                        self.base_pw.page.get_by_role("row", name=etime, exact=True).locator("div").nth(
                                            2).click()
                                        self.base_pw.page.locator("#endDate").get_by_role("textbox").fill(
                                            modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    elif str(wd_type) == "1" and etime == "3000-01-01":
                                        # 将不存在多条同类型的载体属性的，停用时间为3000 - 1 - 1 的这条数据，开始时间修改为当月1日
                                        if stime <= modify_time_str:
                                            logger.warning("场景3，当前数据开始时间早于要修改的时间，不做处理")
                                            # close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                            # if close_loc.count() > 0:
                                            #     close_loc.click()
                                            continue
                                        self.base_pw.page.get_by_role("button", name="修改时间").click()
                                        self.base_pw.page.locator("#ydate").get_by_text(stime).click()
                                        self.base_pw.page.locator("#ydate").get_by_role("textbox").fill(modify_time_str)
                                        self.base_pw.page.locator("#saveTime").click()
                                        self.base_pw.page.wait_for_load_state("networkidle")
                                        close_loc = self.base_pw.page.get_by_role("button", name="关闭")
                                        close_loc.click()
                                    else:
                                        continue

                            logger.info(f"当前编码{project_code}第{i + 1}条记录修改时间已完成")
                            logger.info("当前编码所有数据已处理完，开始清除查询条件项目名称")
                            self.base_pw.page.get_by_role("cell", name=dxmc).get_by_role("link").click()
                        else:
                            logger.info("当前编码未查出数据，不做处理")
                            self.base_pw.page.get_by_role("cell", name=project_name).get_by_role("link").click()

            logger.info("安徽多维凭证宽表增量派生任务——修改载体维度明细完成")
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def extract_grid_data(self, table_id: str = None) -> Dict[str, Any]:
        """
        提取ECP Grid表格数据

        Args:
            table_id: 表格ID，如 'WdRelationMxQueryGrid'；为None时自动查找 class=treeListGrid 的表格

        Returns:
            {
                "success": bool,
                "table_id": str,
                "columns": [{"fieldname": str, "title": str}, ...],
                "rows": [{"fina_org_nm": "组织1501", ..., "_dom_row_index": 2}, ...],
                "total_rows": int,
                "error": str  # 仅失败时
            }

        行数据中 _dom_row_index 记录该行在 table.querySelectorAll('tbody > tr') 中的索引，
        用于后续 click_grid_serial / click_grid_cell 定位。
        """
        # if not self._page:
        #     logger.error("浏览器未启动")
        #     return {"success": False, "error": "浏览器未启动"}

        # js_extract = """(tableId) => {
        #             // 查找表格
        #             const table = tableId
        #                 ? document.getElementById(tableId)
        #                 : document.querySelector('table.treeListGrid');
        #             if (!table) return { error: '表格未找到', rows: [] };
        #
        #             // ====== 第一步: 从第一行(tr)的 td[fieldname] 提取列定义 ======
        #             // 第一行结构: td[0]=占位, td[1]=勾选, td[2]=序号(无fieldname), td[3+]=数据列(有fieldname)
        #             const columns = [];
        #             const firstRowCells = table.querySelectorAll('tr:first-child td');
        #             const fieldnameMap = {}; // td索引 -> fieldname
        #             firstRowCells.forEach((td, idx) => {
        #                 const fname = td.getAttribute('fieldname');
        #                 if (fname) {
        #                     fieldnameMap[idx] = fname;
        #                     columns.push({ idx: idx, fieldname: fname });
        #                 }
        #             });
        #
        #             // ====== 第二步: 从第二行(tr)获取标题文本 ======
        #             // 标题行结构: td[0]=占位, td[1]=勾选标题, td[2]=序号标题, td[3+]=列标题
        #             const headerRow = table.querySelector('tr:nth-child(2)');
        #             const titleCells = headerRow.querySelectorAll('.treeListTitle');
        #             const fieldTitles = {};
        #             // titleCells 从第3个开始对应数据列 (0=勾选标题, 1=序号标题, 2+=列标题)
        #             // 但实际 titleCells 只包含 .treeListTitle 的td，需要和columns对齐
        #             let colIdx = 0;
        #             titleCells.forEach((cell, i) => {
        #                 // 跳过前两个: 勾选标题和序号标题
        #                 if (i < 2) return;
        #                 if (colIdx < columns.length) {
        #                     fieldTitles[columns[colIdx].fieldname] = cell.textContent.trim();
        #                     colIdx++;
        #                 }
        #             });
        #
        #             // ====== 第三步: 遍历数据行 ======
        #             // 数据行中, 数据列的td索引与第一行fieldname的td索引一致
        #             const rows = [];
        #             const allRows = table.querySelectorAll('tbody > tr');
        #             for (let i = 2; i < allRows.length; i++) {
        #                 const tr = allRows[i];
        #                 const cells = tr.querySelectorAll('td');
        #                 const rowData = {};
        #                 let hasData = false;
        #
        #                 // 直接用 fieldnameMap 中记录的 td 索引来提取值
        #                 // fieldnameMap: { td索引: fieldname }，如 {3: "fina_org_nm", 4: "dxlxname", ...}
        #                 for (const [tdIdx, fname] of Object.entries(fieldnameMap)) {
        #                     const td = cells[parseInt(tdIdx)];
        #                     if (!td) continue;
        #                     // 优先取 .text_table_ellipsis 内的文本
        #                     const textDiv = td.querySelector('.text_table_ellipsis');
        #                     const text = textDiv
        #                         ? textDiv.textContent.trim()
        #                         : td.textContent.trim();
        #                     rowData[fname] = text;
        #                     if (text) hasData = true;
        #                 }
        #
        #                 if (hasData) {
        #                     rowData._dom_row_index = i;
        #                     rows.push(rowData);
        #                 }
        #             }
        #
        #             return {
        #                 table_id: table ? table.id : '',
        #                 columns: columns.map(c => ({
        #                     fieldname: c.fieldname,
        #                     title: fieldTitles[c.fieldname] || c.fieldname
        #                 })),
        #                 rows: rows,
        #                 total_rows: rows.length
        #             };
        #         }"""
        js_extract = """(tableId) => {
                    const table = tableId
                        ? document.getElementById(tableId)
                        : document.querySelector('table.treeListGrid');
                    if (!table) return { error: '表格未找到', rows: [] };

                    // 从首行 td[fieldname] 建立列映射: td索引 -> fieldname
                    const columns = [];
                    const fieldnameMap = {};
                    // const firstRowCells = table.querySelectorAll('tr:first-child td');
                    const firstRowCells = table.querySelector('tr:first-child').querySelectorAll(':scope > td');

                    firstRowCells.forEach((td, idx) => {
                        const fname = td.getAttribute('fieldname');
                        if (fname) {
                            fieldnameMap[idx] = fname;
                            columns.push({ idx, fieldname: fname });
                        }
                    });

                    // 从第二行获取标题文本
                    const headerRow = table.querySelector('tr:nth-child(2)');
                    const titleCells = headerRow.querySelectorAll('.treeListTitle');
                    const fieldTitles = {};
                    let colIdx = 0;
                    titleCells.forEach((cell, i) => {
                        if (i < 2) return;
                        if (colIdx < columns.length) {
                            fieldTitles[columns[colIdx].fieldname] = cell.textContent.trim();
                            colIdx++;
                        }
                    });

                    // 遍历数据行
                    const rows = [];
                    const allRows = table.querySelectorAll('tbody > tr');
                    let dataIdx = 0;
                    for (let i = 2; i < allRows.length; i++) {
                        const tr = allRows[i];
                        const cells = tr.querySelectorAll(':scope > td');
                        const rowData = {};
                        let hasData = false;

                        for (const [tdIdx, fname] of Object.entries(fieldnameMap)) {
                            const td = cells[parseInt(tdIdx)];
                            if (!td) continue;
                            const textDiv = td.querySelector('.text_table_ellipsis');
                            const text = textDiv ? textDiv.textContent.trim() : td.textContent.trim();
                            rowData[fname] = text;
                            if (text) hasData = true;
                        }

                        if (hasData) {
                            rowData._dom_row_index = i;
                            rowData._data_index = dataIdx;
                            rows.push(rowData);
                            dataIdx++;
                        }
                    }

                    return {
                        table_id: table ? table.id : '',
                        columns: columns.map(c => ({
                            fieldname: c.fieldname,
                            title: fieldTitles[c.fieldname] || c.fieldname
                        })),
                        rows: rows,
                        total_rows: rows.length
                    };
                }"""

        try:
            result = self.base_pw.page.evaluate(js_extract, table_id)
            if "error" in result and not result.get("rows"):
                logger.error(f"提取表格数据失败: {result['error']}")
                return {"success": False, "error": result["error"]}

            logger.info(f"✔ 提取到 {result['total_rows']} 行数据, {len(result['columns'])} 列")
            return {"success": True, **result}
        except Exception as e:
            logger.error(f"提取表格数据异常: {str(e)}")
            return {"success": False, "error": str(e)}

    def click_grid_cell(self, table_id: str, row_dom_index: int, fieldname: str) -> bool:
        """
        点击表格中指定行的指定列单元格

        Args:
            table_id: 表格ID
            row_dom_index: 行在DOM中的索引 (从_extract_grid_data获取的_domRowIndex)
            fieldname: 列字段名
        """
        # if not self._page:
        #     return False

        # js_click = """(params) => {
        #             const table = document.getElementById(params.tableId);
        #             if (!table) return false;
        #
        #             // 根据 DOM 行索引获取该行
        #             const tr = table.querySelectorAll('tbody > tr')[params.rowIndex];
        #             if (!tr) return false;
        #
        #             // 序号列是第3个td, 索引2
        #             const serialCell = tr.querySelectorAll('td')[2];
        #             if (serialCell) {
        #                 serialCell.click();
        #                 return true;
        #             }
        #             return false;
        #         }"""

        js_mark_target = """(params) => {
                // 清除旧标记
                document.querySelectorAll('[data-ecp-click-target]').forEach(el => {
                    el.removeAttribute('data-ecp-click-target');
                });

                const table = document.getElementById(params.tableId);
                if (!table) return false;

                // 找目标行
                const allRows = table.querySelectorAll('tbody > tr');
                let foundDataIdx = 0;
                let targetTr = null;
                for (let i = 2; i < allRows.length; i++) {
                    const tr = allRows[i];
                    const cells = tr.querySelectorAll(':scope > td');
                    let hasData = false;
                    for (let c = 3; c < cells.length; c++) {
                        const textDiv = cells[c].querySelector('.text_table_ellipsis');
                        if (textDiv && textDiv.textContent.trim()) {
                            hasData = true;
                            break;
                        }
                    }
                    if (hasData) {
                        if (foundDataIdx === params.dataIndex) {
                            targetTr = tr;
                            break;
                        }
                        foundDataIdx++;
                    }
                }

                if (!targetTr) return false;

                // 滚动到可见
                targetTr.scrollIntoView({ block: 'center', behavior: 'instant' });

                // ★ :scope > td 取序号列 = 直接子td[2]
                const serialTd = targetTr.querySelectorAll(':scope > td')[2];
                if (!serialTd) return false;

                serialTd.setAttribute('data-ecp-click-target', 'true');
                return true;
            }"""

        grid_data = self.extract_grid_data(table_id)
        if not grid_data.get("success"):
            return False

        rows = grid_data["rows"]
        # columns = grid_data["columns"]
        # data_index = rows[row_dom_index]['_dom_row_index']
        try:
            # result = self.base_pw.page.evaluate(js_click, {
            #     "tableId": table_id,
            #     "rowIndex": index,
            # })

            marked = self.base_pw.page.evaluate(js_mark_target, {
                "tableId": table_id,
                "dataIndex": row_dom_index,
            })

            locator = self.base_pw.page.locator('[data-ecp-click-target]').first
            locator.click(force=True, timeout=5000)
            try:
                self.base_pw.page.evaluate(
                    "document.querySelectorAll('[data-ecp-click-target]').forEach(el => el.removeAttribute('data-ecp-click-target'))"
                )
            except Exception:
                pass
            return True
            # if result:
            #     logger.info(f"✔ 点击单元格: 行{row_dom_index}, 列{fieldname}")
            # else:
            #     logger.error(f"✗ 未找到单元格: 行{row_dom_index}, 列{fieldname}")
            # return result
        except Exception as e:
            logger.error(f"点击单元格异常: {str(e)}")
            return False

    def add_vouch_task(self, task_info: list):
        try:
            if not task_info:
                logger.warning("派生任务数据为空，跳过处理")
                return
            logger.info("第五步：增加多维凭证宽表增量派生任务", extra={'color': 'darkcyan'})
            # current_url = self.base_pw.page.url
            # parsed_url = urlparse(current_url)
            # base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            # new_url = f"{base_url}/fmp-grm/fmp-fts-standard/necp/mapp/standardserviceweb/assets/components/monitor/HzJob/HzJob.html#"
            # new_page = self.base_pw.context.new_page()
            # new_page.goto(new_url)
            with self.base_pw.page.expect_popup(timeout=50000) as popup_info:
                self.base_pw.page.evaluate("window.open('/fmp-grm/fmp-fts-standard/necp/mapp/standardserviceweb/assets/components/monitor/HzJob/HzJob.html#')")

            new_page = popup_info.value
            self.base_pw.set_page(new_page)
            self.base_pw.locate_and_click("增加派生任务-汇总任务查询", sleep=3000)
            for index, task_item in enumerate(task_info):
                logger.info(f"正在处理第 {index + 1}/{len(task_info)} 条派生任务")
                comp_name = str(task_item.get('单位名称', ''))
                voucher_year = str(task_item.get('凭证年份', ''))
                voucher_comp = str(task_item.get('凭证单位', ''))
                voucher_id = str(task_item.get('凭证ID', ''))
                acc_book = str(task_item.get('账簿', ''))

                self.base_pw.locate_and_click("增加派生任务-增加任务", sleep=3000)
                # self.base_pw.page.get_by_role("row", name="任务类别： 请选择").get_by_role("link").click()
                # self.base_pw.page.get_by_role("option", name="多维凭证宽表增量派生").click()
                # self.base_pw.page.get_by_role("link", name="请选择").click()
                # self.base_pw.page.get_by_role("option", name=comp_name).click()
                # self.base_pw.page.locator("#para_inputer_1").click()
                # self.base_pw.page.locator("#para_inputer_1").fill(voucher_year)
                # self.base_pw.page.locator("#para_inputer_3").click()
                # self.base_pw.page.locator("#para_inputer_3").fill(voucher_comp)
                # self.base_pw.page.locator("#para_inputer_2").click()
                # self.base_pw.page.locator("#para_inputer_2").fill(voucher_id)
                # self.base_pw.page.locator("#para_inputer_4").click()
                # self.base_pw.page.locator("#para_inputer_4").fill(acc_book)
                # self.base_pw.page.get_by_role("button", name="是").click()
                self.base_pw.locate_and_click("增加派生任务-任务类别下拉", sleep=1000)
                self.base_pw.locate_and_click("增加派生任务-多维凭证宽表增量派生选项", sleep=2000)
                self.base_pw.locate_and_click("增加派生任务-单位选择下拉", sleep=1000)
                self.base_pw.page.get_by_role("option", name=comp_name).click()
                self.base_pw.locate_and_click("增加派生任务-凭证年份输入框", sleep=1000)
                self.base_pw.locate_and_fill("增加派生任务-凭证年份输入框", voucher_year, sleep=1000)
                self.base_pw.locate_and_click("增加派生任务-凭证单位输入框", sleep=1000)
                self.base_pw.locate_and_fill("增加派生任务-凭证单位输入框", voucher_comp, sleep=1000)
                self.base_pw.locate_and_click("增加派生任务-凭证ID输入框", sleep=1000)
                self.base_pw.locate_and_fill("增加派生任务-凭证ID输入框", voucher_id, sleep=1000)
                self.base_pw.locate_and_click("增加派生任务-账簿输入框", sleep=1000)
                self.base_pw.locate_and_fill("增加派生任务-账簿输入框", acc_book, sleep=1000)
                self.base_pw.locate_and_click("增加派生任务-确认按钮", sleep=1000)
            logger.info("增加多维凭证宽表增量派生任务成功")

        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)


    def run(self, username: str, password: str, dim_info: list, task_info: list, modify_time_str: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽电力资金协同审核（培训中心）协同流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            self.base_pw = self.base_robot.base_pw
            self.modify_carrier_dimension(dim_info, modify_time_str)
            self.add_vouch_task(task_info)
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

            logger.debug("安徽多维凭证宽表增量派生任务流程执行完成")
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

        logger.info("开始执行安徽多维凭证宽表增量派生任务流程")
        base_robot = None
        input_file = kwargs.get('input_file')
        # input_file = r'data/安徽电力资金协同审核.xlsx'
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        sheet_configs = {
            '登录信息': {'header_row': 0},  # 第一个页签-登录信息
            '载体维度明细': {'header_row': 0},  # 第二个页签-单位信息(单位id, 单位名称)
            '派生任务': {'header_row': 0}  # 第三个页签-核算科目(科目id, 科目名称)
        }
        all_data = ExcelUtils.read_multiple_sheets(excel_utils, sheet_configs)
        # 访问各页签数据
        login_info = all_data['登录信息']
        dim_info = all_data['载体维度明细']
        task_info = all_data['派生任务']
        if len(login_info) < 1:
            raise RobotsException(f'"{input_file}" 第一个页签缺少登录信息')

        username = login_info[0].get('登录账号', '')
        password = login_info[0].get('登录密码', '')
        base_url = login_info[0].get('登录地址', '')
        modify_time = login_info[0].get('载体维度修改时间', '')
        modify_time_str = modify_time.strftime('%Y-%m-%d') if isinstance(modify_time, datetime) else (
            modify_time if isinstance(modify_time, str) else ''
        )
        email_notif = login_info[0].get('发送通知邮件', '').strip().lower()

        logger.debug(f'登陆信息：{username=};{password=};{base_url=};{modify_time=};{modify_time_str=}')
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
                result = process_robot.run(username, password, dim_info, task_info,modify_time_str)

                if email_notif not in ['','否', 'n', 'no', '不发送']:
                    send_email_notification(result=result, task_name="安徽多维凭证宽表增量派生任务流程")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽多维凭证宽表增量派生任务流程已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽多维凭证宽表增量派生任务流程执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽多维凭证宽表增量派生任务流程")
        raise
    except Exception as e:
        logger.error(f"安徽多维凭证宽表增量派生任务流程执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽多维凭证宽表增量派生任务流程")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
