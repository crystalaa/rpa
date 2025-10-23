import json
import os
from typing import Dict, Any
from rpa_framework.utils.path_manager import path_manager
from rpa_framework.utils.log import logger, log_conf

class Config:
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self._path_manager = path_manager
        
        if os.environ.get('RPA_SCAFFOLD_MODE') == '1':
            logger.debug("脚手架模式：跳过配置管理器初始化")
            return
            
        logger.debug("初始化配置管理器...")
        self._print_path_info()
        self._load_app_config()

    def get_app_src_root(self):
        return self._path_manager.app_src_root

    def get_app_root(self):
        return self._path_manager.app_root

    def _load_app_config(self):
        try:
            config_path = self._path_manager.get_config_path("config.json")
            logger.debug(f"尝试加载配置文件: {config_path}")
            if not config_path.exists():
                logger.debug(f"配置文件不存在: {config_path}")
                self._load_default_config()
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                main_config = json.load(f)
                self.config.update(main_config)
                logger.debug("配置文件加载成功")
        except json.JSONDecodeError as e:
            logger.debug(f"配置文件格式错误: {str(e)}")
            self._load_default_config()
        except Exception as e:
            logger.debug(f"加载应用配置文件失败: {str(e)}")
            self._load_default_config()

    def _load_default_config(self):
        logger.debug("使用默认配置")
        self.config = {
            "app": {},
            "menu": {
                "robots": [
                    {
                        "code": "default",
                        "name": "默认功能",
                        "icon": "ui/resources/robot.svg",
                        "method": "default_main",
                        "doc": "docs/暂无文档.html",
                        "file_input": False,
                        "description": "默认功能"
                    }
                ]
            },
            "browser": {
                "headless": True,
                "args": [],
                "slow_mo": 1000,
                "timeout": 30000
            },
            "context": {
                "no_viewport": False,
                "viewport": {
                    "width": 1800,
                    "height": 800
                },
                "record_video_dir": "videos",
                "record_video_size": {
                    "width": 1800,
                    "height": 800
                }
            },
            "page": {},
            "timeout": {
                "default_navigation_timeout": 30000,
                "default_timeout": 10000
            },
            "screenshot": {
                "enabled": True,
                "save_dir": "screenshots"
            },
            "logger": {
                "log_level": "INFO",
                "file_level": "DEBUG",
                "file_formatter": "[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s",
                "console_level": "INFO",
                "console_formatter": "[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s",
                "qt_level": "INFO",
                "qt_formatter": "%(asctime)s - %(message)s",
                "qt_debug": False,
                "stack_info": False,
                "exc_info": True,
                "log_retention_days": 30
            }
        }

    def get_config(self) -> Dict:
        return self.config

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_app_config(self) -> Dict[str, Any]:
        return self.config.get("app", {})

    def get_log_config(self) -> Dict[str, Any]:
        return log_conf

    def get_browser_config(self) -> Dict[str, Any]:
        return self.config.get("browser", {})

    def get_context_config(self) -> Dict[str, Any]:
        return self.config.get("context", {})

    def get_page_config(self) -> Dict[str, Any]:
        return self.config.get("page", {})

    def get_timeout_config(self) -> Dict[str, Any]:
        return self.config.get("timeout", {})

    def get_screenshot(self) -> Dict[str, Any]:
        return self.config.get("screenshot", {})

    def get_exc_info(self):
        return self.get_log_config().get('exc_info', False)

    def get_stack_info(self):
        return self.get_log_config().get('stack_info', False)

    def get_qthandler_debug(self) -> bool:
        return self.get_log_config().get('qt_debug', False)

    def _print_path_info(self):
        """打印路径信息"""
        logger.debug(f"应用根目录: {self._path_manager.app_root}")
        logger.debug(f"配置目录: {self._path_manager.app_root / 'config'}")
        logger.debug(f"数据目录: {self._path_manager.app_root / 'data'}")
        logger.debug(f"文档目录: {self._path_manager.app_root / 'docs'}")
        logger.debug(f"UI资源目录: {self._path_manager.app_root / 'ui' / 'resources'}")
        logger.debug(f"机器人目录: {self._path_manager.app_root / 'robots'}")

    # 路径相关接口
    def get_config_path(self, filename: str):
        return self._path_manager.get_config_path(filename)

    def get_data_path(self, filename: str):
        return self._path_manager.get_data_path(filename)

    def get_doc_path(self, filename: str):
        return self._path_manager.get_doc_path(filename)

    def get_ui_resource_path(self, filename: str):
        return self._path_manager.get_ui_resource_path(filename)

    def get_robot_path(self, filename: str):
        return self._path_manager.get_robot_path(filename)

    def ensure_project_dirs(self):
        return self._path_manager.ensure_project_dirs()

    def copy_default_files(self):
        return self._path_manager.copy_default_files()

config = Config()
