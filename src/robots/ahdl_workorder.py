from datetime import datetime, timedelta
import re
import os
import time
import json
from pathlib import Path
import pandas as pd
import requests
from urllib.parse import urlparse
from rpa_framework.utils.log import logger
from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.excel_utils import ExcelUtils
from rpa_framework.utils.db_util import DatabaseManager
from rpa_framework.core.base_pw import BasePw
from playwright.sync_api import sync_playwright
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException

# from playwright import Playwright

'''
安徽电力工单
'''


class WorkOrder:
    def __init__(self, base_pw: BasePw, base_url: str, debug_mode: bool = False):
        self.base_pw = base_pw
        self.base_url = base_url
        self.debug_mode = debug_mode
        self.data_retention_days = 10  # 数据保留天数，可配置
        self.base_pw.load_selectors("安徽电力工单")
        
        # 初始化数据库管理器
        db_path = os.getenv('WORKORDER_DB_PATH')
        if db_path is None:
            raise RobotsException('未定义数据库路径：WORKORDER_DB_PATH')
        self.db_manager = DatabaseManager(db_path)
        logger.info(f'数据库保存路径：{db_path}', extra={'color': 'darkorange'})
        logger.info(f"图片保存路径：{os.getenv('WORKORDER_DATA_PATH', '')}\\wo_attachment", extra={'color': 'darkorange'})
        logger.info("安徽电力工单RPA初始化完成")

    def check_database_exists(self):
        """检查数据库和表是否存在"""
        return self.db_manager.check_database_exists()

    def init_database(self):
        """初始化数据库（仅在需要时）"""
        self.db_manager.init_database()

    def get_existing_work_order_numbers(self, days_back=10):
        """获取数据库中已存在的工单号（仅查询最近N天）
        
        Args:
            days_back (int): 查询最近多少天的数据，默认10天
        """
        return self.db_manager.get_existing_work_order_numbers(days_back)



    def load_field_mapping(self):
        """加载字段映射配置"""
        try:
            config_path = config.get_ref_path("config/workorder_field_mapping.json")
            logger.debug(f"load fild mapping from: {str(config_path)}")
            with open(str(config_path), "r", encoding="utf-8") as f:
                config_data = json.load(f)
                return config_data["field_mapping"], config_data["work_order_number_column"]
        except Exception as e:
            logger.warning(f"加载字段映射配置失败: {str(e)}，使用默认映射")
            # 默认映射，假设第一列为工单号
            return {}, None

    def map_dataframe_to_db_fields(self, df):
        """将DataFrame的列映射到数据库字段"""
        try:
            # 加载字段映射配置
            field_mapping, work_order_column = self.load_field_mapping()
            
            # 如果没有配置，使用第一列作为工单号
            if not field_mapping:
                field_mapping = {df.columns[0]: 'work_order_number'}
                
            logger.debug(f"使用字段映射: {field_mapping}")
            logger.debug(f"DataFrame列名: {list(df.columns)}")
            
            # 数据库所有字段（按插入顺序）
            db_fields = [
                'work_order_number', 'status', 'process_status', 'reporter', 'title', 
                'company', 'department', 'operation_group', 'operator', 'acceptor',
                'is_key_supervision', 'report_time', 'urgency_level', 'source',
                'work_order_type', 'process_time', 'callback_time', 'evaluation_type',
                'callback_person', 'is_callback', 'user_evaluation', 'archive_status',
                'is_contact_user', 'is_resolved', 'archiver', 'archive_content',
                'is_workday_calculated', 'operations', 'content', 'attachment'
            ]
            
            # 创建映射后的DataFrame
            mapped_data = []
            for _, row in df.iterrows():
                mapped_row = []
                for db_field in db_fields:
                    # 查找对应的DataFrame列
                    df_column = None
                    for df_col, db_col in field_mapping.items():
                        if db_col == db_field:
                            df_column = df_col
                            break
                    
                    if df_column and df_column in df.columns:
                        mapped_row.append(row[df_column])
                    else:
                        mapped_row.append(None)  # 没有对应数据时插入None
                
                mapped_data.append(tuple(mapped_row))
            
            return mapped_data, db_fields
            
        except Exception as e:
            logger.error(f"数据字段映射失败: {str(e)}")
            raise RobotsException(f"数据字段映射失败: {str(e)}", e)

    def insert_new_workorders(self, df, existing_numbers):
        """插入新的工单数据到数据库"""
        try:
            # 获取工单号列名
            _, work_order_column = self.load_field_mapping()
            if not work_order_column or work_order_column not in df.columns:
                work_order_column = df.columns[0]  # 默认使用第一列
            
            logger.debug(f"使用工单号列: {work_order_column}")
            
            # 过滤出新的工单
            new_df = df[~df[work_order_column].isin(existing_numbers)]
            
            if len(new_df) == 0:
                logger.debug("没有新的工单需要插入")
                return 0
            
            ### 目前new data 的attachment 保存的是附件的URL，现在调用download_files 下载附件，并保存到本地   
            ### 然后更新new data 的attachment 为本地附件的path
            logger.info(f"开始为新工单下载附件，共 {len(new_df)} 条工单")
            
            # 对每个新工单下载附件
            for index, row in new_df.iterrows():
                work_order_number = row[work_order_column]
                attachment_urls = row.get('附件', '')
                
                if attachment_urls:
                    try:
                        # 解析附件URL并下载
                        logger.debug(f'下载图片：工单号={work_order_number}； 图片url= {attachment_urls}')
                        local_paths = self.download_attachments_from_urls(attachment_urls, work_order_number)
                        # 更新DataFrame中的附件路径
                        new_df.at[index, '附件'] = local_paths
                        logger.debug(f"工单 {work_order_number} 附件下载完成; 保存地址：{local_paths}")
                    except Exception as e:
                        logger.error(f"工单 {work_order_number} 附件下载失败: {str(e)}")
                        # 下载失败时保持原URL
            
            # 映射数据字段
            mapped_data, db_fields = self.map_dataframe_to_db_fields(new_df)
            
            if not mapped_data:
                logger.debug("没有有效的数据需要插入")
                return 0
            
            # # 提取工单号列表用于删除操作
            # # 从new_df中提取工单号，因为mapped_data已经重新排序了
            # work_order_numbers = new_df[work_order_column].tolist()
            #
            # # 先删除对应的工单记录，实现数据库更新功能
            # # 这样可以确保新数据完全替换旧数据，而不是简单的去重
            # deleted_count = self.db_manager.delete_workorders_by_numbers(work_order_numbers)
            # logger.debug(f"删除 {deleted_count} 条已存在的工单记录，准备更新数据库")
            
            # 使用数据库管理器插入数据
            return self.db_manager.insert_workorders(mapped_data, db_fields)
            
        except Exception as e:
            logger.error(f"插入工单数据失败: {str(e)}")
            raise RobotsException(f"插入工单数据失败: {str(e)}", e)

    def save_to_excel(self, df):
        """保存数据到Excel文件
        
        Args:
            df (pd.DataFrame): 要保存的数据框
            
        Returns:
            str: 保存的Excel文件路径
            
        Raises:
            RobotsException: 保存失败时抛出异常
        """
        try:
            workorder_data_path = os.getenv('WORKORDER_DATA_PATH','')
            if workorder_data_path=='' or workorder_data_path is None:
                raise RobotsException("未配置WORKORDER_DATA_PATH")

            file_path = Path(f"{workorder_data_path}/excel_data/{datetime.now().strftime('%Y%m%d')}")
            file_path.mkdir(parents=True, exist_ok=True)
            file_path = file_path / f'workorder_{datetime.now().strftime('%H%M%S')}.xlsx'
            file_path = str(file_path)
            df.to_excel(file_path, index=False)
            
            logger.debug(f"Excel文件保存成功：{file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"保存到Excel文件失败: {str(e)}")
            raise RobotsException(f"保存到Excel文件失败: {str(e)}", e)

    def save_to_database(self, df):
        """保存数据到数据库（带时间过滤去重）"""
        try:
            # 初始化数据库（如果不存在）
            self.init_database()
            
            # 获取已存在的工单号（仅查询最近N天）
            existing_numbers = self.get_existing_work_order_numbers(self.data_retention_days)
            
            # 插入新的工单
            inserted_count = self.insert_new_workorders(df, existing_numbers)
            
            logger.debug(f"数据库保存完成，基于最近{self.data_retention_days}天数据去重，新增{inserted_count}条工单", extra={'color': 'darkcyan'})
            return inserted_count
            
        except Exception as e:
            logger.error(f"保存到数据库失败: {str(e)}")
            raise RobotsException(f"保存到数据库失败: {str(e)}", e)

    def download_files(self, file_list, work_order_number):
        """下载文件到指定目录
        
        Args:
            file_list (list): 文件列表，包含url、name等信息
            work_order_number (str): 工单编号，用于日志记录
            
        Returns:
            str: 文件路径列表，用分号分隔
        """
        try:
            if not file_list:
                return ""
            
            # 创建目录：data/wo_attachment/yyyy-mm-dd/
            current_date = datetime.now().strftime('%Y-%m-%d')
            workorder_data_path = os.getenv('WORKORDER_DATA_PATH','')
            if workorder_data_path == '' or workorder_data_path is None:
                raise RobotsException("未配置WORKORDER_DATA_PATH")
            download_dir = f"{workorder_data_path}/wo_attachment/{current_date}"
            os.makedirs(download_dir, exist_ok=True)

            downloaded_files = []
            
            for file_info in file_list:
                try:
                    url = file_info.get('url', '')
                    original_name = file_info.get('name', '')
                    
                    if not url or not original_name:
                        logger.warning(f"工单{work_order_number}: 文件信息不完整，跳过下载")
                        continue
                    
                    # 生成带时间戳的文件名
                    timestamp = datetime.now().strftime('%H%M%S')
                    name_parts = original_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                    else:
                        new_filename = f"{original_name}_{timestamp}"
                    
                    file_path = os.path.join(download_dir, new_filename)
                    
                    # 下载文件
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    # 添加相对路径到列表（从data目录开始）
                    relative_path = f"wo_attachment/{current_date}/{new_filename}"
                    downloaded_files.append(relative_path)
                    
                    logger.debug(f"工单{work_order_number}: 文件下载成功 {original_name} -> {relative_path}")
                    
                except Exception as file_error:
                    logger.error(f"工单{work_order_number}: 下载文件失败 {file_info.get('name', 'unknown')}: {str(file_error)}")
                    continue
            
            # 返回用分号分隔的文件路径列表
            return ';'.join(downloaded_files)
            
        except Exception as e:
            logger.error(f"工单{work_order_number}: 文件下载处理失败: {str(e)}")
            return ""

    def download_attachments_from_urls(self, attachment_urls: str, work_order_number: str) -> str:
        """从附件URL字符串下载文件
        
        Args:
            attachment_urls (str): 附件URL字符串，格式：文件名|URL;文件名|URL
            work_order_number (str): 工单编号
            
        Returns:
            str: 本地文件路径，用分号分隔
        """
        try:
            if not attachment_urls:
                return ""
            
            # 解析附件URL
            attachment_list = attachment_urls.split(';')
            file_list = []
            
            for attachment_info in attachment_list:
                if '|' in attachment_info:
                    name, url = attachment_info.split('|', 1)
                    file_list.append({'name': name, 'url': url})
            
            # 使用现有的download_files方法下载
            return self.download_files(file_list, work_order_number)
            
        except Exception as e:
            logger.error(f"工单{work_order_number}: 解析附件URL失败: {str(e)}")
            return attachment_urls  # 失败时返回原URL

    def extract_workorder_details(self, response_data, work_order_number):
        """从响应数据中提取工单详细信息
        
        Args:
            response_data (dict): API响应数据
            work_order_number (str): 工单编号
            
        Returns:
            tuple: (content, attachment_urls)
        """
        try:
            data = response_data.get('data', {})
            
            # 提取content
            work_order_po = data.get('workOrderPO', {})
            content = work_order_po.get('content', '')
            
            # 提取附件信息并转换为URL字符串格式
            file_list = data.get('fileUploadListedVOS', [])
            attachment_urls = self.convert_file_list_to_urls(file_list, work_order_number)
            
            logger.debug(f"工单{work_order_number}: 提取详情完成 - 内容长度:{len(content)}, 附件数量:{len(file_list)}")
            
            return content, attachment_urls
            
        except Exception as e:
            logger.error(f"工单{work_order_number}: 提取详情失败: {str(e)}")
            return "", ""

    def convert_file_list_to_urls(self, file_list, work_order_number):
        """将文件列表转换为URL字符串格式
        
        Args:
            file_list (list): 文件列表，包含url、name等信息
            work_order_number (str): 工单编号
            
        Returns:
            str: URL字符串，格式：文件名|URL;文件名|URL
        """
        try:
            if not file_list:
                return ""
            
            attachment_urls = []
            
            for file_info in file_list:
                url = file_info.get('url', '')
                name = file_info.get('name', '')
                
                if url and name:
                    # 存储格式：文件名|URL
                    attachment_info = f"{name}|{url}"
                    attachment_urls.append(attachment_info)
                    logger.debug(f"工单{work_order_number}: 提取附件URL {name}")
            
            return ';'.join(attachment_urls)
            
        except Exception as e:
            logger.error(f"工单{work_order_number}: 转换文件列表失败: {str(e)}")
            return ""

    def login(self, username: str, password: str):
        """登录系统"""
        try:
            logger.info("第一步：打开登录页面", extra={'color': 'darkcyan'})
            self.base_pw.page.goto(self.base_url)
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.page.wait_for_load_state("networkidle")

            logger.info("第二步：输入账号密码，登录系统", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_fill("登录页面-账户输入框", username)
            self.base_pw.locate_and_fill("登录页面-密码输入框", password)
            self.base_pw.locate_and_click("登录页面-登录按钮")
            logger.info("登录成功")
        except Exception as e:
            if "net::ERR_NAME_NOT_RESOLVED" in str(e):
                error_msg = f"网络连接错误，不能连接到{self.base_url}，请检查正确的网络连接。"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
            raise RobotsException(f"登录失败: {str(e)}", e)

    def navigate_to_workorder_page(self):
        """导航到运维看板页面"""
        try:
            logger.info("第三步：打开‘我的代办’菜单", extra={'color': 'darkcyan'})
            self.base_pw.set_page(self.base_pw.get_main_page())
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(5000)
            self.base_pw.locate_and_click("页面导航-我的待办")
            self.base_pw.page.wait_for_load_state("networkidle")
            logger.info("成功打开我的代办页面")
        except Exception as e:
            raise RobotsException(f"导航到运维看板页面失败: {str(e)}", e)

    def process_workorder(self):
        """提交请求"""
        try:
            logger.info("第四步：查询工单，提取“工单数据“", extra={'color': 'darkcyan'})
            title = []
            data = []
            # self.base_pw.page.pause()
            self.base_pw.locate_and_click("工单页面-查询按钮")
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)
            thead = self.base_pw.page.locator('div.el-table div.el-table__header-wrapper').nth(0).locator('th')
            title = (thead.all_text_contents())
            # th = thead.locator('th').all()
            # print(thead.locator('th').all_text_contents())
            # for cell in th:
            #     print(cell.text_content())
            # self.base_pw.page.pause()
            self.base_pw.page.wait_for_load_state("networkidle")
            self.base_pw.page.wait_for_timeout(3000)
            next_btn = self.base_pw.page.locator('button.btn-next').first
            # self.base_pw.page.pause()
            while True:
                tbody = self.base_pw.page.locator('div.el-table div.el-table__body-wrapper').nth(0).locator('tr').all()
                for row in tbody:
                    workorder = row.locator('td').all_text_contents()
                    # details = row.locator('i.icon-action:has-text("详情")')
                    with self.base_pw.page.expect_response(lambda response: "/work-order/workOrder/" in response.url) as response_info:
                        self.base_pw.page.locator(
                            f"div.el-table__fixed-right .el-table__fixed-body-wrapper .el-table__body  tr:has-text('{workorder[1].strip()}') .word-order-btn i.icon-action:has-text('详情')").click()

                        # 获取响应
                    response = response_info.value
                    logger.debug(f"响应状态: {response.status}")
                    
                    # 提取工单详细信息
                    try:
                        response_data = response.json()
                        logger.debug(f"响应数据: {response_data}")  # 对于 JSON 响应
                        
                        # 提取content和附件URL
                        content, attachment_urls = self.extract_workorder_details(response_data, workorder[1].strip())
                        
                        # 将content和attachment_urls添加到工单数据中
                        workorder_with_details = list(workorder)
                        workorder_with_details.append(content)  # 添加content
                        workorder_with_details.append(attachment_urls)  # 添加attachment_urls
                        workorder = workorder_with_details
                        
                    except Exception as detail_error:
                        logger.error(f"提取工单详情失败: {str(detail_error)}")
                        # 如果提取失败，添加空值
                        workorder_with_details = list(workorder)
                        workorder_with_details.append("")  # content
                        workorder_with_details.append("")  # attachment
                        workorder = workorder_with_details
                    self.base_pw.page.wait_for_timeout(300)
                    self.base_pw.page.get_by_role("button", name="Close").click()

                    data.append(workorder)
                    logger.debug(workorder)
                    logger.info(f'工单已提取，工单编号：{workorder[1]}; 工单标题：{workorder[4]}')
                if not next_btn.is_disabled():
                    next_btn.click()
                    logger.info('第五步：翻页，提取下一页数据', extra={'color': 'darkcyan'})
                    self.base_pw.page.wait_for_load_state("load")
                    self.base_pw.page.wait_for_timeout(10000)
                else:
                    break
            logger.debug(f'before pop: {len(title)=};  {title=}')
            if title[-1] == '':
                title.pop()
            # 添加新的列标题
            title.append('工单内容')  # content字段对应的列名
            title.append('附件')     # attachment字段对应的列名

            logger.debug(f'{len(title)=};  {title=}')
            logger.debug(f'{len(data[0])=}; {data[0]=}')

            df = pd.DataFrame(data, columns=title)
            
            # 保存到Excel文件
            excel_file_path = self.save_to_excel(df)
            logger.debug(f"工单已写入excel文件：{excel_file_path}")

            # 保存到数据库（带去重）
            logger.info('第六步：过滤新工单，保存到数据库', extra={'color': 'darkcyan'})
            inserted_count = self.save_to_database(df)
            logger.debug(f"{inserted_count}条工单已写入数据库")
            
            # for row in data:
            #     logger.debug(row)
            logger.info(f'共抓取{len(data)}条数据，新增{inserted_count}条到数据库', extra={'color': 'darkcyan'})
            logger.info("第七步：工单提取完成", extra={'color': 'green'})

            # 返回Excel文件路径
            return excel_file_path

            # self.base_pw.page.pause()
        except Exception as e:
            raise RobotsException(f"提交请求失败: {str(e)}", e)

    def run(self, username: str, password: str):
        """运行完整的补采流程"""
        try:
            logger.info("开始运行安徽电力工单流程")
            self.base_pw.init_browser()
            self.login(username, password)
            self.navigate_to_workorder_page()
            
            # 处理工单并获取Excel文件路径
            excel_file_path = self.process_workorder()

            result = {
                "success": True,
                "data_file": excel_file_path,
                "video_file": self.base_pw.get_video_path()
            }

            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')

            logger.info("安徽电力工单流程执行完成")
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

        logger.info("开始执行安徽电力工单")
        # input_file = kwargs.get('input_file')
        input_file = r'data/安徽电力工单系统.xlsx'
        if input_file == '' or input_file is None:
            raise Exception('输入文件为空, 请选择正确的输入文件')

        excel_utils = ExcelUtils(input_file)
        data = excel_utils.read_excel()
        if len(data) < 1:
            raise RobotsException(f'“{input_file}” 第一个页签缺少登录信息')


        username = data[0].get('登录账号', '')
        password = data[0].get('登录密码', '')
        base_url = data[0].get('登录地址', '')

        logger.debug(f'登陆信息：{username=};{password=};{base_url=}')
        if password == '' or username == '' or base_url == '':
            raise RobotsException("Excel第一个页签中的登录信息不能为空！请检查！")

        encryptor = Encryptor()
        password = encryptor.decrypt(password)

        # username = 'chuww5821'
        # password = 'andl.1234'
        # base_url = "http://iscsso.ah.sgcc.com.cn/isc_sso/login?service=http://20.50.83.72:80"

        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)

            with BasePw(playwright, show_browser, record_video) as base_pw:
                robot = WorkOrder(base_pw, base_url)
                result = robot.run(username, password)
                logger.info("安徽电力工单已完成", extra={'color': 'green'})
                logger.debug(f"result: {result}")
                return result

    except RobotsException as e:
        logger.error(f"安徽电力工单执行出错: {e.message}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        raise
    except Exception as e:
        logger.error(f"安徽电力工单执行出错: {str(e)}",
                     exc_info=config.get_exc_info(),
                     stack_info=config.get_stack_info())
        raise
    finally:
        logger.debug(f'============ end {__name__} ===========')


if __name__ == "__main__":
    main()
