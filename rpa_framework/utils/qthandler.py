from PySide6.QtCore import Signal, QObject
import logging
from typing import Optional
from PySide6.QtCore import QTimer
from rpa_framework.utils.config import config

class UIFormatter(logging.Formatter):
    """UI界面专用的格式化器，只显示错误信息，不显示堆栈"""
    
    def format(self, record):
        # 对于错误级别的日志，只显示基本信息，不显示堆栈
        if record.levelno >= logging.ERROR:
            # 移除堆栈信息，只保留基本错误信息
            if hasattr(record, 'exc_info') and record.exc_info:
                # 如果有异常信息，只显示异常类型和消息
                exc_type, exc_value, exc_traceback = record.exc_info
                if exc_type and exc_value:
                    # 只显示异常类型和消息，不显示堆栈
                    # record.msg = f"{record.msg} -{exc_type.__name__}: {str(exc_value)}"
                    record.msg = f"{exc_type.__name__}: {record.msg} "
                    
                    # 清除堆栈信息
                    record.exc_info = None
                    record.exc_text = None
        
        return super().format(record)

class QTHandler(logging.Handler):
    """Qt日志处理器，将日志输出到Qt信号"""
    
    def __init__(self):
        super().__init__()
        # 从配置文件读取格式化器设置
        qt_formatter = config.get_log_config().get('qt_formatter', '%(message)s')
        # 使用UI专用的格式化器，应用配置文件中的格式
        self.setFormatter(UIFormatter(qt_formatter))
        self._qt_object = QTHandlerObject()
        self._connected = False
        self._connection_attempted = False
        self._debug_logger = None
        
        # 递归防护机制
        self._in_emit = False
        
        # 根据配置决定是否启用调试日志
        if config.get_qthandler_debug():
            self._init_debug_logger()
        
    def _init_debug_logger(self):
        """初始化独立的调试logger，避免循环引用"""
        try:
            # 创建一个独立的logger，不添加到根logger
            self._debug_logger = logging.getLogger('qthandler_debug')
            self._debug_logger.setLevel(logging.DEBUG)
            
            # 创建文件处理器
            file_handler = logging.FileHandler('logs/qthandler_debug.log', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
            self._debug_logger.addHandler(file_handler)
            
            # 防止传播到根logger
            self._debug_logger.propagate = False
        except Exception:
            self._debug_logger = None
        
    def emit(self, record):
        """处理日志记录"""
        try:
            # 使用formatter的format方法，确保调用UIFormatter
            if self.formatter:
                msg = self.formatter.format(record)
            else:
                # 如果formatter为None，使用默认格式化
                msg = self.format(record)
            
            # 如果信号未连接，记录调试信息
            if not self._connected:
                if not self._connection_attempted and self._debug_logger:
                    self._debug_logger.debug(f"QTHandler: 信号未连接，无法发送日志到UI: {msg}")
                return
                
            color = getattr(record, 'color', None)
            level = record.levelno
            # 信号已连接，发送三个参数
            self._qt_object.log_signal.emit(msg, color, record.levelno)
            
        except Exception as e:
            if self._debug_logger:
                self._debug_logger.error(f"QTHandler emit error: {e}")
    

    def connect_signal(self, slot):
        """连接信号到槽函数"""
        try:
            if not self._connected:
                self._qt_object.log_signal.connect(slot)
                self._connected = True
                self._connection_attempted = True
                if self._debug_logger:
                    self._debug_logger.debug("QTHandler: 信号连接成功")
            else:
                if self._debug_logger:
                    self._debug_logger.debug("QTHandler: 信号已经连接")
        except Exception as e:
            if self._debug_logger:
                self._debug_logger.error(f"QTHandler: 信号连接失败: {e}")
            self._connection_attempted = True
            
    def disconnect_signal(self):
        """安全地断开信号"""
        if self._connected:
            try:
                self._qt_object.log_signal.disconnect()
                if self._debug_logger:
                    self._debug_logger.debug("QTHandler: 信号断开成功")
            except Exception as e:
                if self._debug_logger:
                    self._debug_logger.error(f"QTHandler: 信号断开失败: {e}")
            finally:
                self._connected = False
        
    def close(self):
        """清理资源"""
        self.disconnect_signal()
        super().close()


class QTHandlerObject(QObject):
    """Qt对象，用于发送信号"""
    log_signal = Signal(str, str, int)  # message, color, level

# 使用示例
# logger.info('这是一条普通信息')
# handler = QTHandler()
# handler.connect_signal(your_text_edit.append_log)  # 注意：这里需要连接append_log方法
# logger = logging.getLogger()
# logger.addHandler(handler)
# logger.setLevel(logging.DEBUG)