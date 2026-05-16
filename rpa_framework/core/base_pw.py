import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from playwright.sync_api import Playwright, Page, Browser, BrowserContext, TimeoutError, Locator
from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.core.page_helper import PageHelper

class BasePw:
    def __init__(self, playwright: Playwright, show_browser:bool=False, record_video:bool=False):
        """
        初始化 BasePw 实例。
        :param playwright: Playwright 实例
        :param show_browser: 是否显示浏览器窗口
        :param record_video: 是否录制视频
        """
        self.check_playwright_env()
        self.playwright = playwright
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.page_helper = None
        self.selectors: Dict = {}
        self.show_browser = show_browser
        self.record_video = record_video
        self.error_screenshot = None

    def __enter__(self):
        """
        进入上下文管理器。
        :return: self
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文管理器，确保资源被正确释放。
        :param exc_type: 异常类型
        :param exc_val: 异常值
        :param exc_tb: 异常追踪
        :return: False
        """
        self.close()
        return False

    def __del__(self):
        """
        析构函数，确保资源被正确释放。
        """
        self.close()

    def init_browser(self):
        """
        初始化浏览器、上下文和页面。
        :raises RobotsException: 初始化失败时抛出
        """
        try:
            logger.info(f"初始化浏览器")
            browser_config = config.get_browser_config()
            context_config = config.get_context_config()

            browser_config['headless'] = not self.show_browser
            self.setup_record_video(self.record_video)
        
            logger.debug(f'{browser_config=}')
            logger.debug(f'{context_config=}')
            self.browser = self.playwright.chromium.launch( **browser_config )
            self.context = self.browser.new_context(**context_config)

            self.context.set_default_timeout(config.get_timeout_config().get('default_timeout',30000))
            self.context.set_default_navigation_timeout(config.get_timeout_config().get('default_navigation_timeout',30000))

            self.page = self.context.new_page()
            self.page_helper = PageHelper(self.page)
            logger.debug(f"浏览器初始化完成:{self.page.title()}")
        except Exception as e:
            raise RobotsException('初始化浏览器错误', e)



    def setup_record_video(self, video_enabled:bool) -> None:
        """
        配置视频录制目录。
        :param video_enabled: 是否启用视频录制
        """
        if video_enabled:
            config_video_dir = config.get_context_config().get('record_video_dir', 'videos')
            if config_video_dir is None:
                config_video_dir = 'videos'
            video_dir = Path(config_video_dir)
            if not str(video_dir).endswith(datetime.now().strftime("%Y-%m-%d")):
                video_dir = video_dir / datetime.now().strftime("%Y-%m-%d")
            video_dir.mkdir(parents=True, exist_ok=True)
            # 更新配置中的视频目录
            context_config = config.get_context_config()
            context_config['record_video_dir'] = str(video_dir)
        else:
            # 清空视频目录配置
            context_config = config.get_context_config()
            context_config['record_video_dir'] = None
        logger.debug(f'{context_config["record_video_dir"]=}')  

    def get_video_path(self) -> str|None:
        """
        获取当前页面的视频文件路径。
        :return: 视频文件路径或 None
        """
        if self.page and self.record_video:
            return str(self.page.video.path())
        else:
            return None

    def set_page(self, page: Page):
        """
        设置当前活动页面。
        :param page: 需要设置为当前活动的页面对象
        """
        self.page = page
        logger.debug(f"切换当前页面: {page.url}")

    def get_main_page(self) -> Page:
        """
        获取主页面（第一个打开的页面）。
        :return: 主页面对象
        :raises ValueError: 如果浏览器上下文未初始化
        """
        if not self.context:
            raise ValueError("浏览器上下文未初始化")
        return self.context.pages[0]

    def locate_and_fill(self, element_name: str, value: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None,
                 sleep: Optional[int] = 0,
                 press_key: Optional[str] = None) -> Locator:
        """
        定位元素并填充内容。
        :param element_name: 元素名称
        :param value: 填充的内容
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或填充失败时抛出
        """
        try:
            locator = self.locate_by_page(element_name, wait, exact, timeout)
            locator.fill(value)
            if press_key:
                locator.press(press_key)
            # self.page.wait_for_load_state("networkidle")
            # self.page.wait_for_load_state("domcontentloaded")
            if sleep>0:
                self.page.wait_for_timeout(sleep)

            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并填充元素失败,元素名称: “{element_name}”', e)


    def locate_and_click(self, element_name: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None,
                 sleep:Optional[int]=0) -> Locator:
        """
        定位元素并点击。
        :param element_name: 元素名称
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或点击失败时抛出
        """
        try:
            locator = self.locate_by_page(element_name, wait, exact, timeout)
            locator.click()
            # try:
            #     self.page.wait_for_load_state("networkidle")
            #     self.page.wait_for_load_state("domcontentloaded")
            # except TimeoutError as e:
            #     logger.warning(f"time out error when click: “{element_name}” ， {e}")
            if sleep>0:
                self.page.wait_for_timeout(sleep)
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并点击元素失败,元素名称: “{element_name}”', e)

    def locate_and_check(self, element_name: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        定位元素并勾选（checkbox）。
        :param element_name: 元素名称
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或勾选失败时抛出
        """
        try:
            locator = self.locate_by_page(element_name, wait, exact, timeout)
            locator.check()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并勾选元素失败,元素名称: “{element_name}”', e)

    def locate_and_uncheck(self, element_name: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        定位元素并取消勾选（checkbox）。
        :param element_name: 元素名称
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或取消勾选失败时抛出
        """
        try:
            locator = self.locate_by_page(element_name, wait, exact, timeout)
            locator.uncheck()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并取消勾选元素失败,元素名称: “{element_name}”', e)

    def locate_and_select(self, element_name: str, value: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        定位元素并选择下拉选项。
        :param element_name: 元素名称
        :param value: 选择的值
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或选择失败时抛出
        """
        try:
            locator = self.locate_by_page(element_name, wait, exact, timeout)
            locator.select_option(value)
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并选择元素失败,元素名称: “{element_name}”', e)
    
    def locate_and_fill_by_locator(self, element_name: str, locator:Locator, value: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过已知定位器定位并填充内容。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param value: 填充的内容
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或填充失败时抛出
        """
        try:
            locator = self.locate_by_locator(element_name, locator, wait, exact, timeout) # type: ignore
            locator.fill(value)
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并填充元素失败,元素名称: “{element_name}”', e)
    
    def locate_and_click_by_locator(self, element_name: str, locator:Locator,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过已知定位器定位并点击。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或点击失败时抛出
        """
        try:
            locator = self.locate_by_locator(element_name, locator, wait, exact, timeout) # type: ignore
            locator.click()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并点击元素失败,元素名称: “{element_name}”', e)
    
    def locate_and_check_by_locator(self, element_name: str, locator:Locator,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过已知定位器定位并勾选。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或勾选失败时抛出
        """
        try:
            locator = self.locate_by_locator(element_name, locator, wait, exact, timeout) # type: ignore
            locator.check()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并勾选元素失败,元素名称: “{element_name}”', e)

    def locate_and_uncheck_by_locator(self, element_name: str, locator:Locator,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过已知定位器定位并取消勾选。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或取消勾选失败时抛出
        """
        try:
            locator = self.locate_by_locator(element_name, locator, wait, exact, timeout) # type: ignore
            locator.uncheck()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并取消勾选元素失败,元素名称: “{element_name}”', e)

    def locate_and_select_by_locator(self, element_name: str, locator:Locator, value: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过已知定位器定位并选择下拉选项。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param value: 选择的值
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位或选择失败时抛出
        """
        try:
            locator = self.locate_by_locator(element_name, locator, wait, exact, timeout) # type: ignore
            locator.select_option(value)
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_load_state("domcontentloaded")
            return locator
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f'定位并选择元素失败,元素名称: “{element_name}”', e)

    def locate_by_page(self, element_name: str,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        在当前页面定位元素。
        :param element_name: 元素名称
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位失败时抛出
        """
        if not self.page:
            msg = "当前没有活动页面，请先设置活动页面"
            logger.error(msg)
            raise RobotsException(msg)
        return self._locator(element_name, self.page, wait, exact, timeout)

    def locate_by_locator(self, element_name: str, locator:Locator,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        通过父定位器定位元素。
        :param element_name: 元素名称
        :param locator: 父定位器
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位失败时抛出
        """
        return self._locator(element_name, locator, wait, exact, timeout)


    def _locator(self, element_name: str, par_locator:Page|Locator,
                 wait:Optional[bool]=True,
                 exact:Optional[bool]=False,
                 timeout: Optional[int] = None) -> Locator:
        """
        内部方法：根据元素名称和父定位器获取定位器对象。
        :param element_name: 元素名称
        :param par_locator: 父定位器或页面对象
        :param wait: 是否等待元素出现
        :param exact: 是否精确匹配
        :param timeout: 超时时间（毫秒）
        :return: 定位器对象
        :raises RobotsException: 定位失败时抛出
        """
        try:
            selector = self.selectors.get(element_name)
            if not selector:
                raise RobotsException(f'未找到元素定位配置: {element_name} , selector = "{selector}"')

            logger.debug(f'尝试定位元素: {element_name}, selector = "{selector}"')
            if isinstance(selector, str):
                locator = par_locator.locator(selector) if par_locator else self.page.locator(selector)
            elif isinstance(selector, dict):
                loc_method = selector.get('method','').strip().lower()
                if loc_method is None or loc_method=='':
                    raise RobotsException(f'元素"{element_name}"未配置method参数')
                value = str(selector.get('value'))
                if value is None or value=='':
                    raise RobotsException(f'元素"{element_name}"未配置value参数')
                match loc_method.strip().lower():
                    case 'get_by_role':
                        role_name = str(selector.get('role')).strip().lower()
                        if role_name is None or role_name == '':
                            raise RobotsException(f'元素"{element_name}"未配置role参数')
                        locator = par_locator.get_by_role(role=role_name, name=value,exact=exact) # type: ignore
                    case 'get_by_label':
                        locator = par_locator.get_by_label(value, exact=exact)
                    case 'get_by_placeholder':
                        locator = par_locator.get_by_placeholder(value, exact=exact)
                    case 'get_by_text':
                        locator = par_locator.get_by_text(value, exact=exact)
                    case 'get_by_alt_text':
                        locator = par_locator.get_by_alt_text(value, exact=exact)
                    case 'get_by_title':
                        locator = par_locator.get_by_title(value, exact=exact)
                    case 'get_by_test_id':
                        locator = par_locator.get_by_test_id(value)
                    case _:
                        raise RobotsException(f'元素{element_name}的定位方法配置错误,方法名称: "{loc_method}"')
            else:
                raise RobotsException(f'元素{element_name}的定位{selector}配置错误')

            if wait:
                locator.first.wait_for(state="attached", timeout=timeout)

            logger.debug(f"成功定位元素: {element_name}")
            return locator
        except TimeoutError as e:
            self.take_screenshot(f'timeout_{element_name}', save_page=True, tag='errors')
            raise RobotsException(f'定位元素超时,元素名称: "{element_name}", 元素定位: "{selector}"', e)
        except Exception as e:
            self.take_screenshot(f'error_{element_name}', save_page=True, tag='errors')
            raise RobotsException(f'定位元素失败,元素名称: "{element_name}", 元素定位: "{selector}"', e)


    def take_screenshot(self, name: str, save_page:Optional[bool]=False, tag:Optional[str]='errors'):
        """
        保存当前页面截图。
        :param name: 截图文件名（不含扩展名）
        """
        try:
            if not config.get_screenshot().get('enabled', False):
                logger.debug('take_screenshot: config disabled; {name}')
                return

            if not self.page:
                logger.debug('take_screenshot: page is None; {name}')
                return
            logger.debug(f"taking screenshot: {name}")
            filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            screenshot_config = config.get_screenshot()
            screenshot_dir = Path(screenshot_config.get('save_dir', 'screenshots'))
            screenshot_dir =screenshot_dir /  datetime.now().strftime("%Y-%m-%d") / tag
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            screenshot_path = screenshot_dir / f"{filename}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)

            if self.page_helper and save_page:
                self.page_helper.save_page(filepath=str(screenshot_path))

            if tag == 'errors':
                self.error_screenshot = screenshot_path
            
            logger.info(f"页面截屏已保存到：{screenshot_path}")
            return str(screenshot_path)
        except Exception as e:
            logger.error(f"保存截图失败: {str(e)}")

    def load_selectors(self, app_name: str) -> Dict:
        """
        从JSON文件加载定位器配置。
        :param app_name: 应用名称（用于查找对应的定位器配置）
        :return: 展平后的定位器字典
        :raises RobotsException: 加载或解析失败时抛出
        """
        try:
            # selectors_file = Path(__file__).parent.parent / "config" / "selectors.json"
            selectors_file = config.get_config_path("selectors.json")
            logger.debug(f"load selectors from: {str(selectors_file)}")
            if not selectors_file.exists():
                raise FileNotFoundError(f"定位器配置文件不存在: {selectors_file}")

            logger.debug(f"开始加载定位器配置: {selectors_file}")
            with open(selectors_file, 'r', encoding='utf-8') as f:
                selectors_data = json.load(f)

            # 获取指定名称的定位器
            target_selectors = selectors_data.get(app_name)
            if not target_selectors:
                raise ValueError(f"未找到'{app_name}'的定位器配置")

            # 将嵌套的字典展平为一个字典，并添加类别前缀
            flat_selectors = {}
            for category, elements in target_selectors.items():
                # 为每个元素添加类别前缀
                prefixed_elements = {
                    f"{category}-{key}": value for key, value in elements.items()
                }
                flat_selectors.update(prefixed_elements)

            self.selectors = flat_selectors
            logger.debug(f"加载的定位器配置: {flat_selectors}")
            logger.debug(f"成功加载定位器配置，共 {len(flat_selectors)} 个元素")
            return flat_selectors
        except json.JSONDecodeError as e:
            raise RobotsException(f"定位器配置文件格式错误: {str(e)}", e)
        except Exception as e:
            raise RobotsException(f"加载定位器配置失败: {str(e)}", e)

    def check_playwright_env(self):
        """
        检查 Playwright 浏览器驱动环境变量。
        :raises RobotsException: 未配置或未找到浏览器驱动时抛出
        """
        pw_root = os.getenv('PLAYWRIGHT_BROWSERS_PATH')
        logger.debug(f'{pw_root=}')
        if pw_root is None:
            raise RobotsException('浏览器驱动未配置, 请联系技术支持')
        elif not os.path.isdir(pw_root):
            raise RobotsException('未找到浏览器驱动, 请联系技术支持')

    def close(self):
        """
        关闭浏览器和上下文，释放所有相关资源。
        """
        try:
            if self.context:
                for page in self.context.pages:
                    try:
                        page.close()
                    except Exception as e:
                        logger.debug(f"关闭page时出错：{str(e)}")
                    finally:
                        page = None

                try:
                    self.context.close()
                except Exception as e:
                    logger.error(f"关闭浏览器上下文时出错: {str(e)}")
                finally:
                    self.context = None

            if self.browser:
                try:
                    self.browser.close()
                except Exception as e:
                    logger.error(f"关闭浏览器时出错: {str(e)}")
                finally:
                    self.browser = None

            if self.page_helper:
                self.page_helper = None

            logger.debug("浏览器资源已释放")
        except Exception as e:
            logger.error(f"释放浏览器资源时出错: {str(e)}")


    def fill_vue_input(self, element_name: str, value: str, sleep: int = 2000):
        """
        在Vue应用中定位input框并填充值

        Args:
            element_name: 元素名称（在selectors.json中配置）
            value: 要填充的值
            sleep: 填充后的等待时间（毫秒）
        """
        try:
            # 使用已有的locate_and_fill方法定位并填充input
            self.locate_and_fill(element_name, value, sleep=sleep)

            # 触发Vue的input和change事件，确保Vue能正确捕获值的变化
            locator = self.locate_by_page(element_name)
            locator.evaluate("""(element, value) => {
                element.value = value;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }""", value)

            logger.info(f"成功填充Vue input框: {element_name} = {value}")
        except Exception as e:
            raise RobotsException(f"填充Vue input框失败: {element_name}", e)

