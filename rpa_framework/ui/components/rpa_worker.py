from PySide6.QtCore import QObject, Signal, QThread
from typing import Callable, Dict, Any, Optional
from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException


class RPAWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)  # 添加进度信号

    def __init__(self, task_method: Callable, task_params: Dict[str, Any]):
        super().__init__()
        self.task_method = task_method
        self.task_params = task_params
        self.result = None
        self._thread: Optional[QThread] = None
        self._is_running = False
        
    def start(self):
        """启动工作线程"""
        if self._is_running:
            return

        logger.debug(f'start in worker with: self.task_method={self.task_method.__name__}, {self.task_params=}')
            
        self._thread = QThread()
        self.moveToThread(self._thread)
        
        # 连接信号
        self._thread.started.connect(self.run)
        self.finished.connect(self._thread.quit)
        self.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        
        self._is_running = True
        self._thread.start()
        
    def stop(self):
        """停止工作线程"""
        if not self._is_running:
            return
            
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

    def run(self):
        """执行任务"""
        try:
            self.result = self.task_method(**self.task_params)
            self.finished.emit(self.result)
        except RobotsException as re:
            self.error.emit(str(re))
        except Exception as e:
            error_msg = "robot worker error: " + str(e)
            logger.error(error_msg, exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self.error.emit(error_msg)
        finally:
            self._is_running = False
            
    def _cleanup(self):
        """清理资源"""
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
        self._is_running = False