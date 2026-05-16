from datetime import datetime,timedelta, timezone
import json
import os
import re
import time

from rpa_framework.utils.base64_decoder import Base64Decoder
from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright, Page
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.email_util import send_rpa_success_notification,send_rpa_error_notification


'''
1、安徽电力资金协同审核
产业单位或直属单位与供电公司的电费业务
筛选“对方单位” 为 “国网安徽省电力有限公司本部” ，摘要包含“电费”的记录并全部同意
'''

class ReatedPartyTrans:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽电力资金协同审核")
        logger.debug("安徽电力资金协同审核RPA初始化完成")

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
            logger.info("第四步：导航到”关联交易监控“页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("页面导航-共享财务中心", sleep=1000)
            self.base_pw.set_page(self.base_pw.context.pages[self.base_pw.context.pages.__len__() - 1])
            self.base_pw.locate_and_click("页面导航-会计核算报告", sleep=1000)
            # 跳转到新的tab页

            with self.base_pw.page.expect_popup() as page1:
                self.base_pw.locate_and_click("页面导航-关联交易监控", sleep=1000)
                # self.base_pw.locate_and_click("页面导航-卡片翻页按钮-右")
                logger.debug(f'关联交易监控 popped up , {page1.value}')

            self.base_pw.set_page(page1.value)

            with self.base_pw.page.expect_popup() as page2:
                self.base_pw.locate_and_click("页面导航-资金协同审核", sleep=2000)
            self.base_pw.set_page(page2.value)

            try:
                logger.debug("准备设置分页为每页2000条")
                # self.base_pw.locate_and_click("页面导航-分页下拉框", sleep=500)
                # self.base_pw.locate_and_click("页面导航-选项2000", sleep=1000)
                # 链式定位（更简洁的写法）
                self.base_pw.page.locator('#qzzTableWFUpDiv >> .componet_ui_input_dropBotton').click()
                self.base_pw.page.get_by_text("2000 条/页").click()
                logger.debug("分页设置完成")
            except Exception as e:
                logger.warning(f"设置分页错误：{e}")

            logger.info("成功打开资金协同审核页面")
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
        self.data_file = os.path.join(f'data/资金协同处理导出数据_{datetime.now().strftime("%Y年%m月")}.xlsx')

        logger.info("安徽电力关联交易协同（培训中心）RPA初始化完成")

    def convert_date_string_to_datetime(self, date_str):
        """
        将 \/date(毫秒时间戳+时区)\/ 格式的字符串转换为 yyyy-mm-dd hh:mi:ss 格式的日期时间字符串

        参数:
            date_str (str): 输入的日期字符串，格式如 \/date(1754469648000+0800)\/

        返回:
            str: 格式化后的日期时间字符串，格式为 yyyy-mm-dd hh:mi:ss
        """
        # 使用正则表达式提取时间戳和时区信息
        # 使用正则表达式提取时间戳和时区信息
        pattern1 = r'\\\/Date\((\d+)([+-]\d+)\)\\\/'
        pattern2 = r'/Date\((\d+)([+-]\d+)\)/'

        match1 = re.search(pattern1, date_str)
        match2 = re.search(pattern2, date_str)

        if match1:
            match = match1
        elif match2:
            match = match2
        else:
            return date_str

        # 提取时间戳和时区
        timestamp_ms = int(match.group(1))  # 毫秒时间戳
        timezone_str = match.group(2)  # 时区字符串，如 +0800

        # 将毫秒时间戳转换为秒
        timestamp_s = timestamp_ms / 1000.0

        # 创建 UTC 时间的 datetime 对象
        utc_time = datetime.utcfromtimestamp(timestamp_s)

        # 解析时区偏移
        tz_sign = 1 if timezone_str[0] == '+' else -1
        tz_hours = int(timezone_str[1:3])
        tz_minutes = int(timezone_str[3:5])

        # 计算时区偏移量
        tz_offset = timedelta(hours=tz_hours, minutes=tz_minutes)

        # 应用时区偏移，获取本地时间
        if tz_sign > 0:
            local_time = utc_time + tz_offset
        else:
            local_time = utc_time - tz_offset

        # 格式化为 yyyy-mm-dd hh:mi:ss
        return local_time.strftime('%Y-%m-%d %H:%M:%S')

    def write_excel_json(self, data_map, rows, sheet_name: str, now: str):
        try:
            excel_utils = ExcelUtils(self.data_file)
            if sheet_name not in excel_utils.get_sheet_names():
                columns = ['下载时间', '序号'] + list(data_map.keys())
                excel_utils.create_sheet(sheet_name)
                excel_utils.remove_sheet('Sheet')
                excel_utils.write_row(columns, sheet_name=sheet_name)

            keys = data_map.values()
            data = []
            # logger.debug(f"关联交易审核查询数据: {rows}")
            j = 1
            for i in range(0, len(rows)):
                row = [now, j]
                # if '培训中心' in rows[i].get('conCompName', ''):
                for key in keys:
                    cell_value = rows[i].get(key, '')
                    if key in ('osetVouDat', 'btime'):
                        cell_value = self.convert_date_string_to_datetime(cell_value)
                    row.append(cell_value)
                data.append(row)
                j += 1

            excel_utils.write_excel(data, sheet_name=sheet_name)
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)
        finally:
            try:
                excel_utils.close()
            except Exception as e:
                logger.debug(f'关闭Excel出错: {str(e)}')

    def get_cell_disp_name(self, cur_cell_value, zt_type):
        """
        根据单元格值和状态类型获取显示名称

        参数:
            cur_cell_value (int/str): 单元格值（可以是字符串或整数）
            zt_type (int): 状态类型 (1表示抵销状态，其他表示关联状态)

        返回:
            str: 显示名称
        """
        try:
            # 转换为整数，如果已经是整数则不变
            cur_cell_value = int(cur_cell_value)
        except (ValueError, TypeError):
            # 如果转换失败，返回原始值或"状态未知"
            return str(cur_cell_value) if cur_cell_value is not None else "状态未知"

        if zt_type == 1:
            # 抵销状态
            status_map = {
                14: "已抵销",
                15: "已抵销",
                18: "已抵销",
                16: "本单位协同",
                17: "本单位协同",
                11: "未抵销",
                12: "未抵销",
                13: "未抵销",
                19: "未抵销",
                23: "未抵销",
                24: "未抵销",
                25: "单边抵销"
            }
            return status_map.get(cur_cell_value, "状态未知")
        else:
            # 关联状态
            status_map = {
                15: "手工关联",
                13: "手工关联",
                17: "手工关联",
                12: "自动关联",
                14: "自动关联",
                16: "自动关联",
                25: "自动关联",
                11: "未关联",
                18: "强制关联",
                19: "凭证回退",
                23: "不需关联申请",
                24: "不需关联"
            }
            return status_map.get(cur_cell_value, "状态未知")

    def process_data(self):
        """提交请求"""
        try:
            logger.info("第四步：处理资金协同审核（电费）数据", extra={'color': 'darkcyan'})
            self.base_pw.page.wait_for_load_state("networkidle")
            # self.base_pw.page.pause()
            self.base_pw.locate_and_click("资金协同审核-筛选条件", sleep=1000)
            self.base_pw.locate_and_click("资金协同审核-我方单位下拉框", sleep=1000)
            self.base_pw.locate_and_click("资金协同审核-我方单位更多", sleep=1000)
            time.sleep(1)
            selected_units = self.base_pw.page.locator('.jstree-anchor.jstree-clicked')
            if selected_units.count() == 0:
                logger.debug("未选择任何单位,开始全选我方单位")
                self.base_pw.page.locator(self.base_pw.selectors.get("资金协同审核-我方单位全选")).first.click()
            logger.debug(f"已选择单位数：{selected_units.count()}")
            self.base_pw.locate_and_click("资金协同审核-我方单位确认", sleep=1000)
            self.base_pw.locate_and_fill("资金协同审核-对方单位下拉框", "国网安徽省电力有限公司本部")
            self.base_pw.page.locator('div#select2-drop .select2-result-label:has-text("国网安徽省电力有限公司本部")').click()
            self.base_pw.page.keyboard.press("Escape")
            self.base_pw.locate_and_click("资金协同审核-筛选条件更多", sleep=1000)

            self.base_pw.locate_and_fill("资金协同审核-摘要", "电费")
            # self.base_pw.locate_and_click("资金协同审核-筛选条件确认", sleep=1000)
            resp_url = "pageDataForFound"
            with self.base_pw.page.expect_response(lambda response: resp_url in response.url,
                                                   timeout=30000) as response_info:
                self.base_pw.locate_and_click("资金协同审核-筛选条件确认", sleep=1000)
            if response_info.is_done():
                response = response_info.value
                response_text = response.text()
                # 使用Base64解码
                try:
                    # 先解码Base64
                    decoded_text = Base64Decoder.decode_base64(response_text, True)
                    logger.debug(f"Base64解码后的文本: {decoded_text[:200]}...")  # 只打印前200个字符避免日志过长

                    # 将解码后的字符串转换为JSON对象
                    response_json = json.loads(decoded_text)
                    logger.debug("成功将解码后的文本转换为JSON对象")
                    response_data = response_json.get('groupCheckingProcessResultVO').get('oursideResult')
                    if len(response_data) > 0:
                        for item in response_data:
                            # 转换关联状态：item.glzt = that.getCellDispName(item.chkState, 2)
                            if 'chkState' in item:
                                item['glzt'] = self.get_cell_disp_name(item['chkState'], 2)
                            # 转换抵销状态名称：item.dxztName = that.getCellDispName(item.chkState, 1)
                            if 'chkState' in item:
                                item['dxztName'] = self.get_cell_disp_name(item['chkState'], 1)

                        logger.info(f"已处理 {len(response_data)} 条数据的状态字段转换")

                        data_map = {
                            "抵销状态": "dxztName",
                            "关联状态": "glzt",
                            "业务关键字": "chkKey",
                            "单位": "compidname",
                            "内部往来单位": "wlcompidname",
                            "凭证日期": "osetVouDat",
                            "凭证流水号": "vouSerNo",
                            "抵销凭证编号": "dxBillNo",
                            "第三方凭证编号": "sapDocumentNo",
                            "摘要": "entrySumy",
                            "科目": "subjectName",
                            "现金流量分类": "caFlowClasNm",
                            "入账状态": "accoStatus",
                            "方向": "jdms",
                            "金额": "stdCurAmt",
                            "说明": "reason",
                            "协同前凭证日期": "btime"
                        }
                        self.write_excel_json(data_map, response_data, sheet_name='电费',
                                              now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    logger.error(f"解码后的文本内容: {decoded_text}")
                    # raise Exception(f"响应数据JSON解析失败: {str(e)}")
                except Exception as e:
                    logger.error(f"Base64解码失败: {e}")
                    # raise Exception(f"响应数据处理失败: {str(e)}")

                count_str = self.base_pw.page.locator('#qzzTableWFUpDiv td#common_td', has_text='共').first.inner_text().strip()
                logger.info(f'当前条件查询结果共有数据：{count_str}', extra={'color': 'blue'})
                if count_str != "共0条":
                    # self.base_pw.page.locator(self.base_pw.selectors.get("资金协同审核-表格数据全选")).click(force=True)
                    logger.info("尝试Javascript触发全选。")
                    self.base_pw.page.evaluate("""
                                () => {
                                    if (typeof $ !== 'undefined' && $.fn.qzzquerygrid !== 'undefined') {
                                        try {
                                           $('#qzzTableWFUp').qzzquerygrid(true).selectAll();
                                           $('#qzzTableWFUp').qzzquerygrid(true).trigger("onSelectAll");
                                           return true;
                                        } catch(e) {
                                            return false;
                                        }
                                    } else {
                                        return false;
                                    } 
                                }
                           """)
                    self.base_pw.page.wait_for_timeout(1000)
                    self.base_pw.locate_and_click("资金协同审核-不需关联批复", sleep=1000)
                    self.base_pw.locate_and_click("资金协同审核-同意按钮", sleep=1000)
                    try:
                        self.base_pw.page.wait_for_selector(".colorModal.modal.fade.in", timeout=10000)
                        logger.info("资金协同审核-电费（有记录）-弹出框已打开")
                        confirm_button = self.base_pw.page.locator(".colorModal.modal.fade.in .modal-footer button[buttonindex='1'].btn-primary")
                        logger.debug(f"资金协同审核-电费（有记录）-确认按钮：{confirm_button}")
                        confirm_button.click()
                    except Exception as e:
                        logger.warning(f"资金协同审核-电费（有记录）-弹出框打开失败：{e}")
                        self.result_screenshot = self.base_pw.take_screenshot("1、资金协同审核-电费（有记录）", tag='运行日志')
                        raise RobotsException(f"资金协同审核-电费（有记录）-弹出确认失败: {str(e)}", e)
                else:
                    self.result_screenshot = self.base_pw.take_screenshot("1、资金协同审核-电费（无记录）", tag='运行日志')
                    self.result_remark = "没有“电费”数据，不做任何处理"
                    logger.info(f'没有“电费”数据，不做任何处理', extra={'color': 'blue'})
            # self.base_pw.page.pause()
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str):
        """运行完整的补采流程"""
        try:
            logger.debug("开始运行安徽电力资金协同审核（电费）协同流程")
            self.base_robot.base_pw.init_browser()
            self.base_robot.login(username, password)
            self.base_robot.switch_department()
            self.base_robot.navigate_to_trans_page()
            self.base_pw = self.base_robot.base_pw
            # self.base_pw.load_selectors("安徽电力资金协同审核-电费与社保公积金")
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

            # self.base_pw.page.pause()

            logger.debug("安徽电力资金协同审核（电费）协同流程执行完成")
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

        logger.info("开始执行安徽电力资金协同审核（电费）协同")
        base_robot = None
        input_file = kwargs.get('input_file')
        # input_file = r'data/安徽电力资金协同审核.xlsx'
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
                    send_email_notification(result=result, task_name="安徽电力资金协同审核（电费）")
                else:
                    logger.debug("通知邮件已关闭")

                logger.info("安徽电力资金协同审核已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽电力资金协同审核（电费）协同执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw = base_robot, task_name= "安徽电力资金协同审核（电费）")
        raise
    except Exception as e:
        logger.error(f"安徽电力资金协同审核（电费）协同执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        send_email_alert(errmsg= e, base_pw= base_robot, task_name= "安徽电力资金协同审核（电费）")
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
