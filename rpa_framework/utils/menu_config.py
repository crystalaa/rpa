"""
菜单配置管理器
用于从config.json加载菜单配置并转换为程序可用的格式
支持动态导入Python文件
"""
import importlib.util
import sys
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path

from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger


class MenuConfigManager:
    """菜单配置管理器"""
    
    def __init__(self):
        self._menu_data = None
        self._method_mapping = {}
        self._loaded_modules = {}  # 缓存已加载的模块
    
    def register_method(self, method_name: str, method_func: Callable):
        """注册方法映射"""
        self._method_mapping[method_name] = method_func
    
    def dynamic_import_module(self, file_path: str) -> Optional[Any]:
        """动态导入Python模块"""
        try:
            logger.debug(f'file path in danamic_import_module: {file_path}')
            file_path_obj = Path(file_path)
            
            # 检查文件是否存在
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path_obj}")
                return None
            
            # 检查文件扩展名
            if file_path_obj.suffix not in ['.py', '.pyc']:
                logger.error(f"不支持的文件类型: {file_path_obj.suffix}")
                return None
            
            # 如果已经加载过，直接返回
            if str(file_path_obj) in self._loaded_modules:
                return self._loaded_modules[str(file_path_obj)]
            
            # 获取模块名称
            module_name = file_path_obj.stem
            
            # 创建模块规范
            spec = importlib.util.spec_from_file_location(module_name, file_path_obj)
            if spec is None:
                logger.error(f"无法创建模块规范: {file_path_obj}")
                return None
            
            # 创建模块
            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                logger.error(f"模块加载器为空: {file_path_obj}")
                return None
            
            # 将模块添加到sys.modules
            sys.modules[module_name] = module
            
            # 执行模块
            spec.loader.exec_module(module)
            
            # 缓存模块
            self._loaded_modules[str(file_path_obj)] = module
            
            logger.info(f"成功动态导入模块: {file_path_obj}")
            return module
            
        except Exception as e:
            logger.error(f"动态导入模块失败 {file_path}: {str(e)}")
            return None
    
    def get_method_from_module(self, module: Any, method_name: str) -> Optional[Callable]:
        """从模块中获取方法函数"""
        try:
            if not hasattr(module, method_name):
                logger.error(f"模块中不存在方法: {method_name}")
                return None
            
            method = getattr(module, method_name)
            if not callable(method):
                logger.error(f"方法不是可调用的: {method_name}")
                return None
            
            return method
            
        except Exception as e:
            logger.error(f"获取方法失败 {method_name}: {str(e)}")
            return None
    
    def load_menu_config(self) -> List[Dict[str, Any]]:
        """从配置文件加载菜单配置"""
        try:
            if self._menu_data is None:
                # 从配置文件加载菜单数据
                menu_config = config.get_config().get("menu", {})
                robots_config = menu_config.get("robots", [])
                
                # 转换为程序可用的格式
                self._menu_data = []
                app_root = config.get_app_root()
                
                for robot_config in robots_config:
                    # 构建完整路径
                    icon_path = str(app_root / robot_config.get("icon", ""))
                    doc_path = str(app_root / robot_config.get("doc", ""))

                    if not Path(icon_path).exists():
                        icon_path = str(app_root / r'src\ui\resources\figma-component.svg')

                    if not Path(doc_path).exists():
                        doc_path = str(app_root / r'docs\暂无文档.html')
                    
                    # 获取方法函数
                    method_name = robot_config.get("method", "")
                    method_func = None
                    
                    # 检查是否有动态导入配置
                    if "file_path" in robot_config:
                        # 动态导入模式
                        file_path = robot_config.get("file_path", "")
                        if file_path:
                            # 构建完整文件路径
                            # full_file_path = app_root / file_path
                            module = self.dynamic_import_module(file_path)
                            if module:
                                method_func = self.get_method_from_module(module, method_name)
                    else:
                        # 传统模式：从预注册的方法映射中获取
                        method_func = self._method_mapping.get(method_name)
                    
                    if method_func is None:
                        logger.warning(f"未找到方法映射: {method_name}")
                        continue
                    
                    # 构建菜单项
                    menu_item = {
                        "code": robot_config.get("code", ""),
                        "name": robot_config.get("name", ""),
                        "icon": icon_path,
                        "method": method_func,
                        "doc": doc_path,
                        "file_input": robot_config.get("file_input", False),
                        "description": robot_config.get("description", ""),
                        "file_path": robot_config.get("file_path", "")  # 保存文件路径信息
                    }
                    
                    self._menu_data.append(menu_item)
                
                logger.info(f"成功加载 {len(self._menu_data)} 个菜单项")
            
            return self._menu_data
            
        except Exception as e:
            logger.error(f"加载菜单配置失败: {str(e)}")
            return []
    
    def get_robot_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据代码获取robot配置"""
        menu_data = self.load_menu_config()
        for item in menu_data:
            if item["code"] == code:
                return item
        return None
    
    def get_robot_codes(self) -> List[str]:
        """获取所有robot代码列表"""
        menu_data = self.load_menu_config()
        return [item["code"] for item in menu_data]
    
    def get_robot_choices(self) -> List[str]:
        """获取robot选择列表（包含custom选项）"""
        codes = self.get_robot_codes()
        codes.append("custom")
        return codes
    
    def get_robots_info(self) -> str:
        """获取robot信息字符串（用于帮助信息）"""
        menu_data = self.load_menu_config()
        robot_list = []
        for item in menu_data:
            robot_list.append(f"  {item['name']:<25} {item['code']}")
        return "\n".join(robot_list)
    
    def reload_config(self):
        """重新加载配置"""
        self._menu_data = None
        logger.info("菜单配置已重新加载")


# 全局菜单配置管理器实例
menu_manager = MenuConfigManager()


def register_all_methods():
    """注册所有方法映射（传统模式）"""
    try:
        from rpa_framework.robots.bank_account_collector import main as bank_account_main
        from rpa_framework.robots.yingdao_order_collector import main as yingdao_main
        from rpa_framework.ui.components.settings_dialog import show_settings_dialog as settings_main
        
        menu_manager.register_method("bank_account_main", bank_account_main)
        menu_manager.register_method("yingdao_main", yingdao_main)
        menu_manager.register_method("settings_main", settings_main)
        
        logger.info("成功注册所有方法映射")
        
    except ImportError as e:
        logger.error(f"导入方法失败: {str(e)}")


def get_menu_data() -> List[Dict[str, Any]]:
    """获取菜单数据（兼容旧接口）"""
    return menu_manager.load_menu_config()


def get_robot_data() -> List[Dict[str, Any]]:
    """获取robot数据（兼容旧接口，仅CLI相关）"""
    menu_data = menu_manager.load_menu_config()
    # 过滤掉toolkit，只返回robot相关项
    return [item for item in menu_data if item["code"] != "toolkit"]


def reload_menu_config():
    """重新加载菜单配置"""
    menu_manager.reload_config() 


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # PyInstaller 环境
        base_path = sys._MEIPASS
    else:
        # 开发环境
        base_path = Path.cwd()
    
    return Path(base_path) / relative_path
