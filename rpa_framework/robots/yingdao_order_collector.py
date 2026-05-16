from rpa_framework.core.base_pw import BasePw
from rpa_framework.utils.log import logger
from playwright.sync_api import sync_playwright
from openpyxl import Workbook
from pathlib import Path
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
import time
from typing import List, Dict, Any, Optional

class YingdaoOrderCollector:
    def __init__(self, base_pw: BasePw, base_url: str):
        self.base_pw = base_pw
        self.base_url = base_url
        self.out_data_file: Optional[Path] = None
        self.processed_orders_count = 0
        self.base_pw.load_selectors("影刀商城")
        logger.debug("影刀商城RPA初始化完成")


    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            if hasattr(self, 'base_pw') and self.base_pw:
                self.base_pw.close()
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}")

    def login(self, username: str, password: str) -> None:
        """登录系统"""
        if not username or not password:
            raise RobotsException("用户名和密码不能为空")
            
        try:
            logger.info("第一步：打开登录页面", extra={'color': 'darkcyan'})
            if not self.base_pw.page:
                raise RobotsException("页面未初始化")
            
            self.base_pw.page.goto(self.base_url)
            
            logger.info("第二步：输入账号密码，登录系统", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_fill("登录页面-账户输入框", username)
            self.base_pw.locate_and_fill("登录页面-密码输入框", password)
            self.base_pw.locate_and_click("登录页面-登录按钮")
            
            # 验证登录是否成功
            self._verify_login_success()
            
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"登录失败: {str(e)}", e)

    def _verify_login_success(self) -> None:
        """验证登录是否成功"""
        try:
            # 等待页面跳转完成
            if self.base_pw.page:
                self.base_pw.page.wait_for_load_state('domcontentloaded')
                
                # 通过检查"工作台"文本来验证登录成功
                workbench_element = self.base_pw.locate_by_page("订单页面-工作台")
                workbench_element.wait_for(state="visible")
                logger.info("登录成功，已进入工作台")
            else:
                raise RobotsException("页面未初始化，无法验证登录状态")
        except Exception as e:
            raise RobotsException(f"登录验证失败，未找到工作台元素: {str(e)}", e)
        
    def navigate_to_order_page(self) -> None:
        """导航到订单页面"""
        try:
            logger.info("第三步：进入订单管理页面", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_click("订单页面-订单菜单")
            # 等待页面加载完成
            if self.base_pw.page:
                self.base_pw.page.wait_for_load_state('domcontentloaded')
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"导航到订单页面失败: {str(e)}", e)

    def search_order(self, order_name: str) -> None:
        """搜索订单"""
        if not order_name.strip():
            raise RobotsException("商品名称不能为空")
            
        try:
            logger.info("第四步：输入商品名称，查询商品", extra={'color': 'darkcyan'})
            self.base_pw.locate_and_fill("订单页面-商品名称-输入框", order_name)
            self.base_pw.locate_and_click("订单页面-查询按钮")
            # 等待搜索结果加载
            if self.base_pw.page:
                self.base_pw.page.wait_for_load_state('domcontentloaded')
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"搜索订单失败: {str(e)}", e)
    
    def collect_order(self) -> None:
        """采集并处理订单"""
        try:
            logger.info("第五步：在查询结果中，对每一条订单，点击操作列的确认发货链接，确认发货", extra={'color': 'darkcyan'})
            
            if not self.base_pw.page:
                raise RobotsException("页面未初始化")
            
            # 提取表头
            table_data = self._extract_table_headers()
            
            # 处理所有页面的订单
            while True:
                page_data = self._process_current_page()
                table_data.extend(page_data)
                
                if not self._navigate_to_next_page():
                    break
                    
            logger.debug(f'共处理{self.processed_orders_count}条订单')
            logger.debug(f'共抓取{len(table_data)}条数据')
            self._save_to_excel(table_data)
            
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"采集订单失败: {str(e)}", e)

    def _extract_table_headers(self) -> List[List[str]]:
        """提取表格头部信息"""
        try:
            table = self.base_pw.locate_by_page("订单页面-商品表格")
            if self.base_pw.page:
                header_row = self.base_pw.page.locator('table tr').first
                header_cells = header_row.locator('th').all_text_contents()
                return [header_cells]
            return []
        except Exception as e:
            raise RobotsException(f"提取表头失败: {str(e)}", e)

    def _process_current_page(self) -> List[List[str]]:
        """处理当前页面的所有订单"""
        page_data = []
        try:
            # 等待表格加载完成
            if self.base_pw.page:
                self.base_pw.page.wait_for_load_state('domcontentloaded')
            
            table = self.base_pw.locate_by_page("订单页面-商品表格")
            rows = self.base_pw.locate_by_locator("订单页面-表格行", table).all()
            
            for row in rows:
                row_data = self._process_single_order(row)
                if row_data:
                    page_data.append(row_data)
                    self.processed_orders_count += 1
                    
            return page_data
            
        except Exception as e:
            raise RobotsException(f"处理当前页面失败: {str(e)}", e)

    def _process_single_order(self, row) -> Optional[List[str]]:
        """处理单个订单行"""
        try:
            cells = self.base_pw.locate_by_locator('订单页面-表格单元格', row)
            
            # 获取订单号用于日志记录
            order_num = cells.nth(0).text_content()
            logger.debug(f"正在处理订单#{order_num}")
            
            # 确认发货
            self._confirm_shipment(cells)
            
            # 获取订单数据
            cells_data = cells.all_text_contents()
            logger.info(f'    订单#{order_num}已确认发货')
            
            # 添加操作间隔
            if self.base_pw.page:
                self.base_pw.page.wait_for_timeout(100)
            
            return cells_data
            
        except Exception as e:
            logger.error(f"处理订单行失败: {str(e)}")
            # 对于单个订单的错误，记录但不中断整个流程
            return None

    def _confirm_shipment(self, cells) -> None:
        """确认发货操作"""
        try:
            # 点击确认发货按钮
            confirm_button = self.base_pw.locate_by_locator('订单页面-确认发货', cells)
            confirm_button.wait_for(state="visible")
            confirm_button.click()
            
            # 处理确认弹窗
            self._handle_confirmation_popup()
            
        except Exception as e:
            raise RobotsException(f"确认发货操作失败: {str(e)}", e)

    def _handle_confirmation_popup(self) -> None:
        """处理确认发货弹窗"""
        try:
            # 等待弹窗出现
            popup = self.base_pw.locate_by_page('订单页面-商品表格_确认发货弹窗')
            popup.wait_for(state="visible")
            
            # 点击确定按钮
            confirm_popup_button = popup.locator(
                self.base_pw.selectors['订单页面-商品表格_确认发货弹窗_确定按钮']
            )
            confirm_popup_button.wait_for(state="visible")
            confirm_popup_button.click()
            
            # 等待弹窗消失
            popup.wait_for(state="hidden")
            
        except Exception as e:
            raise RobotsException(f"处理确认弹窗失败: {str(e)}", e)

    def _navigate_to_next_page(self) -> bool:
        """导航到下一页"""
        try:
            next_button = self.base_pw.locate_by_page("订单页面-下一页按钮", wait=False)
            if next_button.count() == 1:
                next_button.click()
                if self.base_pw.page:
                    self.base_pw.page.wait_for_load_state('domcontentloaded')
                logger.info("翻页处理中...", extra={'color': 'darkcyan'})
                return True
            return False
        except Exception as e:
            logger.warning(f"翻页操作失败: {str(e)}")
            return False

    def _save_to_excel(self, table_data: List[List[str]]) -> None:
        """保存数据到Excel文件"""
        if not table_data:
            logger.warning("没有数据需要保存")
            return
            
        try:
            logger.info("第七步：保存订单数据到Excel", extra={'color': 'darkcyan'})

            wb = Workbook()
            ws = wb.active
            if ws:
                ws.title = "商品订单"
                
                # 写入数据
                for row in table_data:
                    if row:  # 确保行不为空
                        ws.append(row)

            # 确保目录存在
            data_dir = Path("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成带时间戳的文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = data_dir / f"商城订单_{timestamp}.xlsx"

            wb.save(output_path)
            self.out_data_file = output_path.absolute()
            logger.info(f'订单数据已保存到: {self.out_data_file}')

        except Exception as e:
            raise RobotsException(f"保存订单数据失败: {str(e)}", e)

    def run(self, username: str, password: str, order_name: str) -> Dict[str, Any]:
        """执行主要流程"""
        try:
            self.base_pw.init_browser()
            self.login(username, password)
            self.navigate_to_order_page()
            self.search_order(order_name)
            self.collect_order()
            
            result = {
                "success": True,
                "data_file": str(self.out_data_file) if self.out_data_file else None,
                "video_file": self.base_pw.get_video_path(),
                "processed_orders": self.processed_orders_count
            }
            
            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {self.base_pw.get_video_path()}')
                
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
            - username (str): 登录用户名
            - password (str): 登录密码  
            - order_name (str): 要搜索的商品名称
    """
    try:
        logger.info("开始执行影刀商城订单确认发货")
        logger.debug(f'输入参数: {kwargs}')
        logger.debug(f'{config.config=}')
        
        # 从配置或参数中获取登录信息
        username = kwargs.get("username", "admin")
        password = kwargs.get("password", "58T2$!hm")  # 建议从环境变量或配置文件读取
        order_name = kwargs.get("order_name", "短袖T恤")
        
        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", False)
            record_video = kwargs.get("record_video", False)
            
            with BasePw(playwright, show_browser, record_video) as base_pw:
                order_collector = YingdaoOrderCollector(base_pw, "https://shop.yingdao.com")
                result = order_collector.run(username, password, order_name)
                logger.info("影刀商城订单确认发货已完成", extra={'color': 'green'})
                return result
                
    except RobotsException as e:
        logger.error(f"影刀商城订单确认发货执行出错: {e.message}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise
    except Exception as e:
        logger.error(f"影刀商城订单确认发货执行出错: {str(e)}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise


if __name__ == "__main__":
    main()