# 防御性导入，确保在PyInstaller环境中也能正常工作
try:
    import json
except ImportError:
    print("警告: json模块导入失败，尝试延迟导入")
    json = None

import os
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

logger = None

log_conf = {
    "log_level": logging.DEBUG,
    "log_format": "[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s",
    "file_level": logging.DEBUG,
    "file_format":    "[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s",
    "console_level": logging.DEBUG,
    "console_format": "[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s",
    "qt_level": logging.INFO,
    "qt_format": "[%(asctime)s] -  %(message)s"
}


def setup_logger():
    global log_conf
    logger = logging.getLogger()
    
    # 检查是否在脚手架模式下运行
    if os.environ.get('RPA_SCAFFOLD_MODE') == '1':
        # 脚手架模式下，使用简单的控制台日志
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.debug('running in scaffold mode')
        return logger

    os.makedirs('logs', exist_ok=True)
    log_file = 'logs/rpa.log'

    conf_path = Path('config/logger.json')
    print(f'正在加载日志文件：{conf_path}')
    if conf_path.exists():
        if json is not None:
            with open(conf_path, 'r', encoding='utf-8') as f:
                log_conf = json.load(f)
                print(f"日志配置文件加载成功：{str(log_conf)}")
        else:
            print("json模块不可用，使用默认配置")
    else:
        print(f"日志配置文件不存在：{str(log_conf)}")

    logger.setLevel(log_conf.get("log_level", "DEBUG"))

    formatter = '[%(asctime)s] %(levelname)s - %(filename)s:%(lineno)d: %(message)s'

    # file handler
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=log_conf.get('log_retention_days',30),
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.setLevel(log_conf.get('file_level', logging.DEBUG))
    file_handler.setFormatter(logging.Formatter(log_conf.get('file_formatter', formatter)))
    logger.addHandler(file_handler)

    # stream handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_conf.get('file_level', logging.DEBUG))
    console_handler.setFormatter(logging.Formatter(log_conf.get('console_formatter',formatter)))
    logger.addHandler(console_handler)
    
    return logger

def get_logger():
    """获取logger实例，延迟初始化"""
    global logger
    if logger is None:
        logger = setup_logger()
    return logger

logger = get_logger()