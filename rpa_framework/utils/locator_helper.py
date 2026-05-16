import json
import os
from pathlib import Path
from typing import Dict, Any, Union
from playwright.sync_api import Page, Locator
from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger


class LocatorHelper:
    """Playwright定位器辅助类"""
    
    def __init__(self, page: Page, selectors_file: str = "selectors.json"):
        """
        初始化定位器辅助类
        
        Args:
            page: Playwright页面对象
            selectors_file: 选择器配置文件路径
        """
        self.page = page
        self.selectors_file = selectors_file
        self.selectors = self._load_selectors()
        
    def _load_selectors(self) -> Dict[str, Any]:
        """加载选择器配置"""
        try:
            config_path = Path("config") / self.selectors_file
            if not config_path.exists():
                logger.warning(f"选择器配置文件不存在: {config_path}")
                return {}
                
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载选择器配置失败: {str(e)}")
            return {}
    
    def get_locator(self, element_name: str, module_name: str = None) -> Locator:
        """
        根据元素名称获取Playwright定位器
        
        Args:
            element_name: 元素名称，如"订单菜单1"
            module_name: 模块名称，如"影刀商城"，如果为None则自动查找
            
        Returns:
            Locator: Playwright定位器对象
            
        Raises:
            ValueError: 当找不到元素配置时
        """
        try:
            # 如果提供了模块名称，直接查找
            if module_name:
                if module_name not in self.selectors:
                    raise ValueError(f"模块 '{module_name}' 不存在于选择器配置中")
                module_config = self.selectors[module_name]
            else:
                # 自动查找包含该元素的模块
                module_config = None
                module_name = None
                for module, config in self.selectors.items():
                    for page_name, page_config in config.items():
                        if element_name in page_config:
                            module_config = config
                            module_name = module
                            break
                    if module_config:
                        break
                
                if not module_config:
                    raise ValueError(f"元素 '{element_name}' 不存在于任何模块的选择器配置中")
            
            # 查找元素配置
            element_config = None
            page_name = None
            for page, page_config in module_config.items():
                if element_name in page_config:
                    element_config = page_config[element_name]
                    page_name = page
                    break
            
            if not element_config:
                raise ValueError(f"元素 '{element_name}' 在模块 '{module_name}' 中未找到")
            
            # 根据配置类型返回定位器
            if isinstance(element_config, str):
                # 简单字符串格式：直接使用page.locator()
                logger.debug(f"使用字符串定位器: {element_config}")
                return self.page.locator(element_config)
            
            elif isinstance(element_config, dict):
                # 字典格式：根据method调用对应的定位方法
                method = element_config.get("method")
                if not method:
                    raise ValueError(f"元素 '{element_name}' 配置缺少 'method' 字段")
                
                return self._get_locator_by_method(element_config, method)
            
            else:
                raise ValueError(f"元素 '{element_name}' 配置格式不支持: {type(element_config)}")
                
        except Exception as e:
            logger.error(f"获取定位器失败 - 元素: {element_name}, 错误: {str(e)}")
            raise
    
    def _get_locator_by_method(self, element_config: Dict[str, Any], method: str) -> Locator:
        """
        根据方法类型获取定位器
        
        Args:
            element_config: 元素配置字典
            method: 定位方法名称
            
        Returns:
            Locator: Playwright定位器对象
        """
        try:
            if method == "get_by_role":
                role = element_config.get("role")
                name = element_config.get("name")
                if not role:
                    raise ValueError("get_by_role方法需要'role'参数")
                if name:
                    return self.page.get_by_role(role, name=name)
                else:
                    return self.page.get_by_role(role)
                    
            elif method == "get_by_alt_text":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_alt_text方法需要'value'参数")
                return self.page.get_by_alt_text(value)
                
            elif method == "get_by_label":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_label方法需要'value'参数")
                return self.page.get_by_label(value)
                
            elif method == "get_by_placeholder":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_placeholder方法需要'value'参数")
                return self.page.get_by_placeholder(value)
                
            elif method == "get_by_test_id":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_test_id方法需要'value'参数")
                return self.page.get_by_test_id(value)
                
            elif method == "get_by_text":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_text方法需要'value'参数")
                return self.page.get_by_text(value)
                
            elif method == "get_by_title":
                value = element_config.get("value")
                if not value:
                    raise ValueError("get_by_title方法需要'value'参数")
                return self.page.get_by_title(value)
                
            else:
                raise ValueError(f"不支持的定位方法: {method}")
                
        except Exception as e:
            logger.error(f"根据方法获取定位器失败 - 方法: {method}, 配置: {element_config}, 错误: {str(e)}")
            raise
    
    def get_locator_with_module(self, module_name: str, page_name: str, element_name: str) -> Locator:
        """
        根据模块名、页面名和元素名获取定位器
        
        Args:
            module_name: 模块名称，如"影刀商城"
            page_name: 页面名称，如"订单页面"
            element_name: 元素名称，如"订单菜单1"
            
        Returns:
            Locator: Playwright定位器对象
        """
        try:
            if module_name not in self.selectors:
                raise ValueError(f"模块 '{module_name}' 不存在")
                
            module_config = self.selectors[module_name]
            if page_name not in module_config:
                raise ValueError(f"页面 '{page_name}' 在模块 '{module_name}' 中不存在")
                
            page_config = module_config[page_name]
            if element_name not in page_config:
                raise ValueError(f"元素 '{element_name}' 在页面 '{page_name}' 中不存在")
                
            element_config = page_config[element_name]
            
            # 根据配置类型返回定位器
            if isinstance(element_config, str):
                logger.debug(f"使用字符串定位器: {element_config}")
                return self.page.locator(element_config)
            
            elif isinstance(element_config, dict):
                method = element_config.get("method")
                if not method:
                    raise ValueError(f"元素 '{element_name}' 配置缺少 'method' 字段")
                return self._get_locator_by_method(element_config, method)
            
            else:
                raise ValueError(f"元素 '{element_name}' 配置格式不支持: {type(element_config)}")
                
        except Exception as e:
            logger.error(f"获取定位器失败 - 模块: {module_name}, 页面: {page_name}, 元素: {element_name}, 错误: {str(e)}")
            raise


# 使用示例
"""
# 创建定位器辅助类
locator_helper = LocatorHelper(page)

# 方式1：自动查找元素（推荐）
try:
    order_menu = locator_helper.get_locator("订单菜单1")
    order_menu.click()
except ValueError as e:
    print(f"找不到元素: {e}")

# 方式2：指定模块和页面
try:
    order_menu = locator_helper.get_locator_with_module("影刀商城", "订单页面", "订单菜单1")
    order_menu.click()
except ValueError as e:
    print(f"找不到元素: {e}")

# 方式3：指定模块名
try:
    order_menu = locator_helper.get_locator("订单菜单1", "影刀商城")
    order_menu.click()
except ValueError as e:
    print(f"找不到元素: {e}")
""" 