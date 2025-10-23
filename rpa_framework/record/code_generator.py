"""
代码生成器

负责根据录制的操作生成Playwright自动化代码
"""

from pathlib import Path
from typing import List, Dict, Any
from rpa_framework.utils.log import logger


class CodeGenerator:
    """Playwright代码生成器"""
    
    def __init__(self):
        """初始化代码生成器"""
        logger.debug("代码生成器初始化完成")
    
    def generate_playwright_code(self, actions: List[Dict], package_name: str) -> str:
        """
        生成基于BasePw的Playwright自动化代码
        :param actions: 操作列表
        :param package_name: 包名称
        :return: 生成的代码
        """
        try:
            logger.info(f"开始生成BasePw代码，操作数量: {len(actions)}")
            
            class_name = self._get_class_name(package_name)
            selector_name = package_name.lower().replace(' ', '_')
            
            # 生成完整代码
            code = self._create_header_section(package_name, class_name, selector_name, len(actions))
            code += self._create_class_definition(class_name, package_name, selector_name)
            code += self._create_navigation_methods(actions)
            code += self._create_step_methods(actions)
            code += self._create_run_method(actions)
            code += self._create_main_function(package_name, class_name, actions)
            code += self._create_selector_config(selector_name, actions)
            
            logger.info("BasePw代码生成完成")
            return code
            
        except Exception as e:
            logger.error(f"生成BasePw代码失败: {str(e)}")
            raise Exception(f"生成代码失败: {str(e)}")
    
    def _create_header_section(self, package_name: str, class_name: str, selector_name: str, actions_count: int) -> str:
        """创建代码头部"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f'''"""
{package_name} - 基于BasePw的自动化脚本

由RPA录制器自动生成
生成时间: {current_time}
操作步骤: {actions_count}

注意：此脚本需要根据实际环境进行调整和测试
"""

from rpa_framework.core.base_pw import BasePw
from rpa_framework.utils.log import logger
from playwright.sync_api import sync_playwright
from pathlib import Path
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException
import time
from typing import List, Dict, Any, Optional


'''
    
    def _create_class_definition(self, class_name: str, package_name: str, selector_name: str) -> str:
        """创建类定义"""
        return f'''class {class_name}:
    """
    {package_name} 自动化执行类（基于BasePw架构）
    """
    
    def __init__(self, base_pw: BasePw, base_url: str):
        self.base_pw = base_pw
        self.base_url = base_url
        self.result_data = {{}}
        # 加载选择器配置 - 需要在config/selectors.json中配置
        self.base_pw.load_selectors("{selector_name}")
        logger.debug("{package_name}RPA初始化完成")

    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            if hasattr(self, 'base_pw') and self.base_pw:
                self.base_pw.close()
        except Exception as e:
            logger.error(f"释放资源时出错: {{str(e)}}")

'''
    
    def _create_navigation_methods(self, actions: List[Dict]) -> str:
        """创建导航方法"""
        navigation_code = ""
        
        # 查找第一个URL
        for action in actions:
            page_info = action.get('page_info', {})
            url = page_info.get('url', '')
            title = page_info.get('title', '页面')
            
            if url:
                navigation_code = f'''    def navigate_to_page(self) -> None:
        """导航到页面: {title}"""
        logger.info("导航到页面: {title}", extra={{"color": "darkcyan"}})
        if not self.base_pw.page:
            raise RobotsException("页面未初始化")
        
        self.base_pw.page.goto("{url}")
        self.base_pw.page.wait_for_load_state('networkidle')

'''
                break
        
        return navigation_code
    
    def _create_step_methods(self, actions: List[Dict]) -> str:
        """创建步骤方法"""
        methods_code = ""
        step_count = 0
        generated_methods = set()
        current_page_id = None
        
        for action in actions:
            action_type = action.get('type', 'unknown')
            page_id = action.get('page_id', 'page_01_main')
            
            # 检查页面切换
            if page_id != current_page_id:
                if current_page_id is not None:
                    # 添加页面切换逻辑
                    methods_code += self._create_page_switch_method(step_count, current_page_id, page_id)
                current_page_id = page_id
            
            if action_type in ['click', 'input', 'select', 'popup_open']:
                step_count += 1
                element_name = self._generate_element_name(action, step_count)
                method_name = f"step_{step_count}_{action_type}_{self._clean_name(element_name)}"
                
                if method_name not in generated_methods:
                    generated_methods.add(method_name)
                    action_desc = self._get_action_description(action)
                    
                    # 生成方法
                    method_code = f'    def {method_name}(self'
                    
                    # 添加参数
                    if action_type == 'input':
                        default_value = str(action.get('value', '')).replace('"', '\\"')
                        method_code += f', input_value: str = "{default_value}"'
                    elif action_type == 'select':
                        default_value = str(action.get('value', ''))
                        method_code += f', select_value: str = "{default_value}"'
                    
                    method_code += f') -> None:\n'
                    method_code += f'        """{action_desc}"""\n'
                    method_code += f'        logger.info("步骤 {step_count}: {action_desc}", extra={{"color": "darkcyan"}})\n'
                    
                    # 添加操作
                    if action_type == 'popup_open':
                        # 处理新页面打开
                        method_code += f'        # 新页面已打开，当前页面: {page_id}\n'
                        method_code += f'        # 等待新页面加载完成\n'
                        method_code += f'        time.sleep(1)\n'
                    elif action_type == 'click':
                        # 检查是否是弹窗触发
                        special_flags = action.get('special_flags', {})
                        if special_flags.get('is_popup_trigger', False):
                            method_code += f'        # 点击会打开新页面的元素\n'
                            method_code += f'        with self.base_pw.page.expect_popup() as popup_info:\n'
                            method_code += f'            self.base_pw.locate_and_click("{element_name}")\n'
                            method_code += f'        popup_page = popup_info.value\n'
                            method_code += f'        popup_page.wait_for_load_state("networkidle")\n'
                            method_code += f'        # 切换到新页面进行操作\n'
                            method_code += f'        self.base_pw.page = popup_page\n'
                        else:
                            method_code += f'        self.base_pw.locate_and_click("{element_name}")\n'
                    elif action_type == 'input':
                        method_code += f'        self.base_pw.locate_and_fill("{element_name}", input_value)\n'
                    elif action_type == 'select':
                        method_code += f'        self.base_pw.locate_and_select("{element_name}", select_value)\n'
                    
                    method_code += '\n'  # 只添加空行分隔，不需要等待代码
                    
                    methods_code += method_code
        
        return methods_code
    
    def _create_page_switch_method(self, step_count: int, from_page_id: str, to_page_id: str) -> str:
        """创建页面切换方法"""
        return f'''    def step_{step_count}_switch_to_page_{to_page_id.replace("page_", "").replace("_", "_")}(self) -> None:
        """切换到页面: {to_page_id}"""
        logger.info("步骤 {step_count}: 切换到页面 {to_page_id}", extra={{"color": "darkcyan"}})
        # 页面切换逻辑 - 根据实际情况调整
        time.sleep(0.5)  # 等待页面切换完成

'''
    
    def _create_run_method(self, actions: List[Dict]) -> str:
        """创建主执行方法"""
        # 生成参数列表
        input_count = 0
        select_count = 0
        param_list = []
        
        for action in actions:
            if action.get('type') == 'input' and action.get('value'):
                input_count += 1
                param_list.append(f'input_value_{input_count}: str = ""')
            elif action.get('type') == 'select' and action.get('value'):
                select_count += 1
                param_list.append(f'select_value_{select_count}: str = ""')
        
        # 生成方法签名
        if param_list:
            method_sig = f"self, {', '.join(param_list)}"
        else:
            method_sig = "self"
        
        run_code = f'''    def run({method_sig}) -> Dict[str, Any]:
        """执行主要流程"""
        try:
            self.base_pw.init_browser()
            
            # 执行业务流程步骤
'''
        
        # 添加导航调用
        has_url = any(action.get('page_info', {}).get('url') for action in actions)
        if has_url:
            run_code += '            self.navigate_to_page()\n'
        
        # 添加步骤调用
        step_count = 0
        input_counter = 0
        select_counter = 0
        current_page_id = None
        
        for action in actions:
            action_type = action.get('type', 'unknown')
            page_id = action.get('page_id', 'page_01_main')
            
            # 检查页面切换
            if page_id != current_page_id:
                if current_page_id is not None:
                    step_count += 1
                    switch_method = f"step_{step_count}_switch_to_page_{page_id.replace('page_', '').replace('_', '_')}"
                    run_code += f'            self.{switch_method}()\n'
                current_page_id = page_id
            
            if action_type in ['click', 'input', 'select', 'popup_open']:
                step_count += 1
                element_name = self._generate_element_name(action, step_count)
                method_name = f"step_{step_count}_{action_type}_{self._clean_name(element_name)}"
                
                if action_type == 'click':
                    run_code += f'            self.{method_name}()\n'
                elif action_type == 'input':
                    input_counter += 1
                    run_code += f'            self.{method_name}(input_value_{input_counter})\n'
                elif action_type == 'select':
                    select_counter += 1
                    run_code += f'            self.{method_name}(select_value_{select_counter})\n'
                elif action_type == 'popup_open':
                    run_code += f'            self.{method_name}()\n'
        
        # 完成方法
        steps_executed = len([a for a in actions if a.get('type') in ['click', 'input', 'select', 'popup_open']])
        
        run_code += f'''            
            result = {{
                "success": True,
                "data": self.result_data,
                "video_file": self.base_pw.get_video_path(),
                "steps_executed": {steps_executed}
            }}
            
            if self.base_pw.get_video_path():
                logger.info(f'视频已保存到: {{self.base_pw.get_video_path()}}')
                
            return result
            
        except RobotsException:
            raise
        except Exception as e:
            raise RobotsException(f"执行RPA任务失败: {{str(e)}}", e)

'''
        
        return run_code
    
    def _create_main_function(self, package_name: str, class_name: str, actions: List[Dict]) -> str:
        """创建main函数"""
        # 获取默认URL
        default_url = 'https://example.com'
        for action in actions:
            page_info = action.get('page_info', {})
            if page_info.get('url'):
                default_url = page_info.get('url')
                break
        
        return f'''def main(**kwargs):
    """主函数
    
    Args:
        **kwargs: 参数字典，包含以下键：
            - show_browser (bool): 是否显示浏览器
            - record_video (bool): 是否录制视频
            # 添加其他业务参数
    """
    try:
        logger.info("开始执行{package_name}")
        logger.debug(f'输入参数: {{kwargs}}')
        logger.debug(f'{{config.config=}}')
        
        # 从参数中获取配置信息
        base_url = kwargs.get("base_url", "{default_url}")
        
        with sync_playwright() as playwright:
            show_browser = kwargs.get("show_browser", True)
            record_video = kwargs.get("record_video", False)
            
            with BasePw(playwright, show_browser, record_video) as base_pw:
                automation = {class_name}(base_pw, base_url)
                result = automation.run(**kwargs)
                logger.info("{package_name}已完成", extra={{"color": "green"}})
                return result
                
    except RobotsException as e:
        logger.error(f"{package_name}执行出错: {{e.message}}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise
    except Exception as e:
        logger.error(f"{package_name}执行出错: {{str(e)}}", 
                    exc_info=config.get_exc_info(), 
                    stack_info=config.get_stack_info())
        raise


if __name__ == "__main__":
    main(
        show_browser=True,
        record_video=False,
        # 添加其他必要参数
    )

'''
    
    def _create_selector_config(self, selector_name: str, actions: List[Dict]) -> str:
        """创建选择器配置"""
        config_code = f'''
# ===========================================
# 建议的selectors.json配置示例
# ===========================================
"""
需要在config/selectors.json中添加以下配置：

{{
  "{selector_name}": {{
'''
        
        # 生成选择器配置
        step_count = 0
        for action in actions:
            if action.get('type') in ['click', 'input', 'select']:
                step_count += 1
                element_name = self._generate_element_name(action, step_count)
                selectors = action.get('selectors', [])
                special_flags = action.get('special_flags', {})
                
                if selectors and len(selectors) > 0:
                    # 使用录制时的最佳选择器
                    primary_selector = selectors[0]
                    selector_type = primary_selector.get('type', 'css')
                    
                    # 根据不同的selector类型生成正确的配置
                    if selector_type == 'role':
                        role = primary_selector.get('role', 'button')
                        name = primary_selector.get('name', '')
                        
                        # 特殊处理菜单项
                        if role == 'menuitem' or special_flags.get('is_menu_item', False):
                            if name:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "menuitem", "value": "{name}"}},\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "menuitem", "value": ""}},\n'
                        # 特殊处理弹窗触发元素
                        elif special_flags.get('is_popup_trigger', False):
                            if name:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": "{name}"}},  # 弹窗触发元素\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": ""}},  # 弹窗触发元素\n'
                        else:
                            if name:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": "{name}"}},\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": ""}},\n'
                    elif selector_type == 'text':
                        text_value = primary_selector.get('value', '')
                        # 检查是否是菜单项文本
                        if special_flags.get('is_menu_item', False):
                            config_code += f'    "{element_name}": {{"method": "get_by_text", "value": "{text_value}"}},  # 菜单项\n'
                        else:
                            config_code += f'    "{element_name}": {{"method": "get_by_text", "value": "{text_value}"}},\n'
                    elif selector_type == 'label':
                        label_value = primary_selector.get('value', '')
                        config_code += f'    "{element_name}": {{"method": "get_by_label", "value": "{label_value}"}},\n'
                    elif selector_type == 'placeholder':
                        placeholder_value = primary_selector.get('value', '')
                        config_code += f'    "{element_name}": {{"method": "get_by_placeholder", "value": "{placeholder_value}"}},\n'
                    elif selector_type == 'testId':
                        testid_value = primary_selector.get('value', '')
                        config_code += f'    "{element_name}": {{"method": "get_by_test_id", "value": "{testid_value}"}},\n'
                    elif selector_type == 'title':
                        title_value = primary_selector.get('value', '')
                        config_code += f'    "{element_name}": {{"method": "get_by_title", "value": "{title_value}"}},\n'
                    elif selector_type == 'css':
                        css_value = primary_selector.get('value', '')
                        # 对于CSS选择器，直接使用字符串格式
                        if special_flags.get('is_popup_trigger', False):
                            config_code += f'    "{element_name}": "{css_value}",  # 弹窗触发元素\n'
                        else:
                            config_code += f'    "{element_name}": "{css_value}",\n'
                    elif selector_type == 'xpath':
                        xpath_value = primary_selector.get('value', '')
                        config_code += f'    "{element_name}": {{"method": "xpath", "value": "{xpath_value}"}},\n'
                    else:
                        # 未知类型，使用CSS作为fallback
                        selector_value = primary_selector.get('value', f'[data-element="{element_name}"]')
                        config_code += f'    "{element_name}": "{selector_value}",\n'
                else:
                    # 没有选择器数据时，生成基于元素信息的合理默认配置
                    element_info = action.get('element_info', {})
                    action_type = action.get('type', 'unknown')
                    
                    if action_type == 'input':
                        # 输入框优先使用placeholder或name
                        placeholder = element_info.get('placeholder', '')
                        name = element_info.get('name', '')
                        if placeholder:
                            config_code += f'    "{element_name}": {{"method": "get_by_placeholder", "value": "{placeholder}"}},\n'
                        elif name:
                            config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "textbox", "value": "{name}"}},\n'
                        else:
                            config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "textbox", "value": ""}},\n'
                    elif action_type == 'click':
                        # 按钮优先使用文本内容
                        text = element_info.get('text', '').strip()
                        
                        # 检查是否是菜单项
                        if special_flags.get('is_menu_item', False):
                            if text and len(text) < 30:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "menuitem", "value": "{text}"}},\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "menuitem", "value": ""}},\n'
                        # 检查是否是弹窗触发
                        elif special_flags.get('is_popup_trigger', False):
                            if text and len(text) < 30:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "button", "value": "{text}"}},  # 弹窗触发元素\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "button", "value": ""}},  # 弹窗触发元素\n'
                        else:
                            if text and len(text) < 30:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "button", "value": "{text}"}},\n'
                            else:
                                config_code += f'    "{element_name}": {{"method": "get_by_role", "role": "button", "value": ""}},\n'
                    else:
                        # 其他类型，生成空配置供用户填写
                        config_code += f'    "{element_name}": "",\n'
        
        config_code += '''  }
}

# 多页面场景的额外配置建议：
"""
对于包含弹窗的多页面场景，建议在代码中添加以下处理：

1. 弹窗检测和处理：
   - 使用 page.expect_popup() 等待新页面打开
   - 使用 popup_info.value 获取新页面对象
   - 在新页面中执行操作后，根据需要切换回原页面

2. 页面切换管理：
   - 记录当前活跃页面
   - 在页面间切换时更新 page 对象
   - 确保操作在正确的页面上执行

3. 错误处理：
   - 添加页面加载超时处理
   - 处理页面关闭或不可访问的情况
"""
'''
        
        return config_code
    
    def _generate_element_name(self, action: Dict, step_count: int) -> str:
        """生成元素名称"""
        action_type = action.get('type', 'unknown')
        element_info = action.get('element_info', {})
        
        text = element_info.get('text', '').strip()
        placeholder = element_info.get('placeholder', '').strip()
        name = element_info.get('name', '').strip()
        id_attr = element_info.get('id', '').strip()
        
        if action_type == 'click':
            if text and len(text) < 20:
                clean_text = self._clean_name(text)
                return f"按钮-{clean_text}"
            else:
                return f"按钮-步骤{step_count}"
        elif action_type == 'input':
            if placeholder:
                clean_placeholder = self._clean_name(placeholder)
                return f"输入框-{clean_placeholder}"
            elif name:
                clean_name = self._clean_name(name)
                return f"输入框-{clean_name}"
            elif id_attr:
                clean_id = self._clean_name(id_attr)
                return f"输入框-{clean_id}"
            else:
                return f"输入框-步骤{step_count}"
        elif action_type == 'select':
            if name:
                clean_name = self._clean_name(name)
                return f"下拉框-{clean_name}"
            else:
                return f"下拉框-步骤{step_count}"
        else:
            return f"元素-步骤{step_count}"
    
    def _generate_selector_config(self, element_name: str, selector_value: str, selector_type: str, action: dict) -> str:
        """
        根据JavaScript selector生成正确的配置格式
        :param element_name: 元素名称
        :param selector_value: JavaScript selector字符串
        :param selector_type: selector类型
        :param action: 操作数据
        :return: 配置字符串
        """
        import re
        
        try:
            # 解析JavaScript选择器字符串
            if 'getByRole(' in selector_value:
                # 解析 getByRole('button', { name: '登录' }) 或 getByRole('textbox')
                role_match = re.match(r"getByRole\(['\"]([^'\"]+)['\"](?:,\s*\{\s*name:\s*['\"]([^'\"]*)['\"].*?\})?\)", selector_value)
                if role_match:
                    role = role_match.group(1)
                    name = role_match.group(2) or ""
                    if name:
                        return f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": "{name}"}},\n'
                    else:
                        return f'    "{element_name}": {{"method": "get_by_role", "role": "{role}", "value": ""}},\n'
            
            elif 'getByText(' in selector_value:
                # 解析 getByText('账户admin')
                text_match = re.match(r"getByText\(['\"]([^'\"]*)['\"]", selector_value)
                if text_match:
                    text = text_match.group(1)
                    return f'    "{element_name}": {{"method": "get_by_text", "value": "{text}"}},\n'
            
            elif 'getByLabel(' in selector_value:
                # 解析 getByLabel('pink')
                label_match = re.match(r"getByLabel\(['\"]([^'\"]*)['\"]", selector_value)
                if label_match:
                    label = label_match.group(1)
                    return f'    "{element_name}": {{"method": "get_by_label", "value": "{label}"}},\n'
            
            elif 'getByPlaceholder(' in selector_value:
                # 解析 getByPlaceholder('请输入用户名')
                placeholder_match = re.match(r"getByPlaceholder\(['\"]([^'\"]*)['\"]", selector_value)
                if placeholder_match:
                    placeholder = placeholder_match.group(1)
                    return f'    "{element_name}": {{"method": "get_by_placeholder", "value": "{placeholder}"}},\n'
            
            elif 'getByTestId(' in selector_value:
                # 解析 getByTestId('login-button')
                testid_match = re.match(r"getByTestId\(['\"]([^'\"]*)['\"]", selector_value)
                if testid_match:
                    testid = testid_match.group(1)
                    return f'    "{element_name}": {{"method": "get_by_test_id", "value": "{testid}"}},\n'
            
            elif 'getByTitle(' in selector_value:
                # 解析 getByTitle('标题')
                title_match = re.match(r"getByTitle\(['\"]([^'\"]*)['\"]", selector_value)
                if title_match:
                    title = title_match.group(1)
                    return f'    "{element_name}": {{"method": "get_by_title", "value": "{title}"}},\n'
            
            # 如果无法解析，使用CSS选择器作为fallback
            logger.warning(f"无法解析选择器 {selector_value}，使用CSS选择器作为fallback")
            return f'    "{element_name}": "{selector_value}",\n'
            
        except Exception as e:
            logger.warning(f"解析选择器失败 {selector_value}: {str(e)}")
            # 出错时使用CSS选择器作为fallback
            return f'    "{element_name}": "{selector_value}",\n'
    
    def _clean_name(self, name: str) -> str:
        """清理名称，生成合法的变量名"""
        import re
        clean = re.sub(r'[^\w\u4e00-\u9fff]', '', name)
        return clean[:20] if clean else "元素"
    
    def _get_class_name(self, package_name: str) -> str:
        """根据包名生成类名"""
        import re
        clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', package_name)
        words = clean_name.split('_')
        class_name = ''.join(word.capitalize() for word in words if word)
        return class_name + 'Automation'
    
    def _get_action_description(self, action: Dict) -> str:
        """获取操作的中文描述"""
        action_type = action.get('type', 'unknown')
        if action_type == 'click':
            if action.get('element_info', {}).get('text'):
                return f"点击 '{action['element_info']['text'][:30]}' 按钮/链接"
            else:
                return f"点击 {action.get('tagName', '元素')}"
        elif action_type == 'input':
            element_info = action.get('element_info', {})
            field_name = element_info.get('placeholder') or element_info.get('name') or element_info.get('id') or '输入框'
            return f"在 '{field_name}' 中输入: {action.get('value', '')}"
        elif action_type == 'select':
            return f"在下拉框中选择: {action.get('selectedText', action.get('value', ''))}"
        else:
            return f"执行 {action_type} 操作"
    
    def save_code(self, package_dir: Path, code: str):
        """保存生成的代码"""
        try:
            code_dir = package_dir / "generated_code"
            code_dir.mkdir(exist_ok=True)
            
            with open(code_dir / "playwright_automation.py", 'w', encoding='utf-8') as f:
                f.write(code)
            
            logger.info(f"代码已保存到: {code_dir / 'playwright_automation.py'}")
            
        except Exception as e:
            logger.error(f"保存代码失败: {str(e)}") 