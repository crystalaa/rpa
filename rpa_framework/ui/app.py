import os
import logging
import webbrowser
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog, QTabWidget
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer, Signal, Slot, QUrl

# 尝试导入WebEngine，如果不可用则回退到QTextEdit
WEBENGINE_AVAILABLE = False
# try:
#     from PySide6.QtWebEngineWidgets import QWebEngineView
#     from PySide6.QtWebEngineCore import QWebEnginePage
#     WEBENGINE_AVAILABLE = True
# except ImportError:
#     WEBENGINE_AVAILABLE = False
#     print("警告: PySide6-WebEngine不可用，将使用QTextEdit作为替代")
#     WEBENGINE_AVAILABLE = False

from rpa_framework.ui.components.sidebar import Sidebar
from rpa_framework.ui.components.message_box import MessageBox
from rpa_framework.ui.styles.main_style import (
    START_BUTTON_STYLE, STOP_BUTTON_STYLE, OPEN_BUTTON_STYLE,
    TEXT_EDIT_STYLE, ROOT_STYLE, CONTENT_STYLE, TOP_PANEL_STYLE, TAB_WIDGET_STYLE
)
from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger
from rpa_framework.utils.qthandler import QTHandler
from rpa_framework.ui.components.rpa_worker import RPAWorker
from rpa_framework.ui.components.toggle_switch import ToggleSwitch
from rpa_framework.utils.robot_exception import RobotsException

class App(QMainWindow):
    """主应用窗口类"""
    
    # 定义信号
    log_signal = Signal(str, str, int)  # message, color, level
    
    def __init__(self, menu_data: list):
        super().__init__()
        self.menu_data = menu_data
        logger.debug(f'{self.menu_data=}')
        logger.debug("初始化主窗口")

        # 初始化状态
        self._init_state()
        
        # 初始化UI
        self._init_ui()
        
        # 初始化日志处理器
        self._init_logger()
        
        # 设置窗口图标
        icon_path = str(config.get_app_src_root() / "rpa_framework/ui/resources/RPA.png")
        logger.debug(f'{icon_path=}')
        self.setWindowIcon(QIcon(icon_path))

        logger.info("主窗口初始化完成")
        
    def _init_state(self):
        """初始化状态变量"""
        self.is_running = False
        self.current_menu_item = self.menu_data[0]  # 确保在使用前初始化
        self.worker = None
        self.worker_thread = None
        self.data_file = ''
        self.video_file = ''
        
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("RPA自动化工具 ver1.0")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(ROOT_STYLE)
        
        # 创建中央部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建主布局
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 创建左侧菜单
        self.sidebar = Sidebar(self.menu_data)
        self.sidebar.menu_list.currentRowChanged.connect(self.on_item_changed)
        
        # 创建内容区域
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(CONTENT_STYLE)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # 创建并添加各个区域
        self.content_layout.addWidget(self._create_top_widget())
        self.content_layout.addWidget(self._create_middle_widget(), 1)
        self.bottom_widget = self._create_bottom_widget()
        self.content_layout.addWidget(self.bottom_widget)
        
        # 添加到主布局
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_widget)
        
        # 创建消息框
        self.message_box = MessageBox(self)
        
    def _init_logger(self):
        """初始化日志处理器"""
        logger.debug(f"log config in __init_logger:{config.get_log_config()=}" )
        self.qt_handler = QTHandler()
        self.qt_handler.connect_signal(self.append_log)
        logger.debug(f'{config.get_log_config().get('qt_level','INFO')=}')
        self.qt_handler.setLevel(config.get_log_config().get('qt_level','INFO'))
        logger.addHandler(self.qt_handler)
        logger.debug("exit __init_logger")
        
    def _create_top_widget(self):
        """创建顶部面板"""
        top_widget = QWidget()
        top_widget.setFixedHeight(55)
        top_widget.setStyleSheet(TOP_PANEL_STYLE)
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 0, 0, 0)

        # 左侧组件 - 显示当前选中的菜单标题
        self.menu_title_label = QLabel(self.current_menu_item["name"])
        self.menu_title_label.setStyleSheet("font-weight: bold; margin-left: 10px;")
        top_layout.addWidget(self.menu_title_label)
        top_layout.addStretch()

        # 右侧组件
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 20, 0)
        right_layout.setSpacing(16)

        # 显示浏览器
        browser_label = QLabel("显示浏览器")
        self.browser_toggle = ToggleSwitch()
        self.browser_toggle.state = True
        self.browser_toggle.update()
        browser_layout = QHBoxLayout()
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(4)
        browser_layout.addWidget(browser_label)
        browser_layout.addWidget(self.browser_toggle)
        browser_widget = QWidget()
        browser_widget.setLayout(browser_layout)

        # 自动录像
        record_label = QLabel("自动录像")
        self.record_toggle = ToggleSwitch()
        self.record_toggle.state = False
        self.record_toggle.update()
        record_layout = QHBoxLayout()
        record_layout.setContentsMargins(0, 0, 0, 0)
        record_layout.setSpacing(4)
        record_layout.addWidget(record_label)
        record_layout.addWidget(self.record_toggle)
        record_widget = QWidget()
        record_widget.setLayout(record_layout)

        # 创建开始按钮
        self.start_button = QPushButton("启动任务")
        self.start_button.setStyleSheet(START_BUTTON_STYLE)
        self.start_button.clicked.connect(self.start_rpa)

        right_layout.addWidget(browser_widget)
        right_layout.addWidget(record_widget)
        right_layout.addWidget(self.start_button)

        top_layout.addWidget(right_widget)
        return top_widget

    def _create_middle_widget(self):
        """创建中间面板"""
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)  # 左对齐
        middle_layout.setSpacing(10)

        # 创建Tab控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(TAB_WIDGET_STYLE)

        # 创建功能说明页面
        instruction_widget = QWidget()
        instruction_layout = QVBoxLayout(instruction_widget)
        
        # 根据WebEngine可用性选择组件
        if WEBENGINE_AVAILABLE:
            # 使用QWebEngineView替代QTextEdit以支持完整HTML
            self.instruction_web = QWebEngineView()
            self.instruction_web.setHtml("""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body { 
                        font-family: 'Microsoft YaHei', Arial, sans-serif; 
                        margin: 20px; 
                        line-height: 1.6;
                        color: #333;
                    }
                    h1, h2, h3 { color: #2c3e50; }
                    .placeholder { 
                        text-align: center; 
                        color: #7f8c8d; 
                        font-size: 16px; 
                        margin-top: 50px; 
                    }
                </style>
            </head>
            <body>
                <div class="placeholder">在这里显示功能说明...</div>
            </body>
            </html>
            """)
            instruction_layout.addWidget(self.instruction_web)
            self.instruction_text = None  # 标记不使用QTextEdit
        else:
            # 回退到QTextEdit
            self.instruction_text = QTextEdit()
            self.instruction_text.setPlaceholderText("在这里显示功能说明...")
            self.instruction_text.setStyleSheet(TEXT_EDIT_STYLE)
            self.instruction_text.setReadOnly(True)
            instruction_layout.addWidget(self.instruction_text)
            self.instruction_web = None  # 标记不使用QWebEngineView
        
        # 创建运行日志页面
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self.textedit_log = QTextEdit()
        self.textedit_log.setPlaceholderText("在这里显示运行日志...")
        self.textedit_log.setStyleSheet(TEXT_EDIT_STYLE)
        self.textedit_log.setReadOnly(True)
        log_layout.addWidget(self.textedit_log)
        
        # 添加标签页
        self.tab_widget.addTab(instruction_widget, "📋 功能说明")
        self.tab_widget.addTab(log_widget, "🎬️运行日志")
        
        # 初始化文本内容
        self.update_text_content()
        self.tab_widget.currentChanged.connect(self.update_text_content)

        middle_layout.addWidget(self.tab_widget, 1)
        return middle_widget

    def _create_bottom_widget(self):
        """创建底部面板"""
        self.bottom_widget = QWidget()
        self.bottom_widget.setFixedHeight(60)
        self.bottom_layout = QHBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(10, 0, 10, 0)

        self.data_file_label = QLabel("数据文件")
        self.video_file_label = QLabel('视频文件')

        self.open_data_file_btn = QPushButton("打开数据文件")
        self.open_data_file_btn.setStyleSheet(OPEN_BUTTON_STYLE)
        self.open_data_file_btn.clicked.connect(self.on_open_data_file)

        self.open_video_file_btn = QPushButton("打开视频文件")
        self.open_video_file_btn.setStyleSheet(OPEN_BUTTON_STYLE)
        self.open_video_file_btn.clicked.connect(self.on_open_video_file)

        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.open_video_file_btn)
        self.bottom_layout.addWidget(self.open_data_file_btn)

        self.bottom_widget.setVisible(False)
        return self.bottom_widget

    @Slot(int)
    def on_item_changed(self, row: int):
        """处理菜单项切换"""
        if 0 <= row < len(self.sidebar.menu_data):
            selected_item = self.sidebar.menu_data[row]
            
            # 特殊处理：如果是系统设置，直接打开对话框
            if selected_item["code"] == "toolkit":
                try:
                    from rpa_framework.ui.components.settings_dialog import show_settings_dialog
                    show_settings_dialog(self)
                    # 恢复之前选中的菜单项
                    if hasattr(self, 'current_menu_item'):
                        for i, item in enumerate(self.sidebar.menu_data):
                            if item["name"] == self.current_menu_item["name"]:
                                self.sidebar.menu_list.setCurrentRow(i)
                                break
                    else:
                        # 如果没有之前的菜单项，选择第一个非设置项
                        for i, item in enumerate(self.sidebar.menu_data):
                            if item["name"] != "系统设置":
                                self.sidebar.menu_list.setCurrentRow(i)
                                self.current_menu_item = item
                                break
                except Exception as e:
                    logger.error(f"打开系统设置失败: {str(e)}")
                    self.message_box.show_error(f"打开系统设置失败: {str(e)}")
                return
            
            # 常规菜单项处理
            self.current_menu_item = selected_item
            self.menu_title_label.setText(self.current_menu_item["name"])
            self.tab_widget.setCurrentIndex(0)
            self.update_text_content()

        if self.current_menu_item['method'] is None:
            self.start_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)

    @Slot()
    def start_rpa(self):
        """启动RPA任务"""
        try:
            pw_root = os.getenv('PLAYWRIGHT_BROWSERS_PATH')
            if pw_root is None:
               self.message_box.show_message('浏览器驱动未配置, 请联系技术支持进行配置!')
               return
            elif not os.path.isdir(pw_root):
                self.message_box.show_message('未找到浏览器驱动, 请联系技术支持进行配置!')

            # 检查输入文件
            input_file  = self._get_input_file()
            if not input_file:
                self.message_box.show_message(f'当前任务 "{self.current_menu_item.get("name")}" 需要输入文件,请选择正确的输入文件!')
                return

            self.clear_text_content()
            self.tab_widget.setCurrentIndex(1)
            self._run_rpa(input_file)
        except RobotsException as e:
            logger.error(f'启动robot错误: {e.message}', exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self.message_box.show_error(f"启动robot错误: {e.message}")
        except Exception as e:
            logger.error(f"启动robot错误: {str(e)}", exc_info = config.get_exc_info(), stack_info= config.get_stack_info())
            self.message_box.show_error(f"启动robot错误: {str(e)}")

    def _get_input_file(self) -> Optional[str | bool]:
        """获取输入文件"""
        if self.current_menu_item.get('file_input'):
            input_file, _ = QFileDialog.getOpenFileName(self, "请选择输入文件", "", "excel (*.xlsx)")
            if input_file:
                logger.debug(f'{input_file=}')
                return input_file
            else:
                return False
        else:
            return True

    def _run_rpa(self, input_file: Optional[str | bool] = None):
        """运行RPA任务"""

        try:
            self.is_running = True
            self._update_widget_enabled_state()

            # 创建任务参数
            task_params = {
                'show_browser': self.browser_toggle.state,
                'record_video': self.record_toggle.state
            }

            if input_file and isinstance(input_file, str):
                task_params['input_file'] = input_file

            # 创建并启动工作线程
            self.worker = RPAWorker(self.current_menu_item['method'], task_params)
            self.worker.finished.connect(self._on_worker_finished)
            self.worker.error.connect(self._handle_rpa_error)
            self.worker.progress.connect(lambda msg: self.append_log(msg, 'blue'))

            # 启动任务
            self.worker.start()
        except Exception as e:
            logger.error(f"启动robot错误: {str(e)}", exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self._handle_rpa_error(f"启动robot错误: {str(e)}")
            

    @Slot(object)
    def _on_worker_finished(self, result=None):
        """处理工作线程完成"""
        try:
            logger.debug(f'on_worker_finished with: {result=}')
            self._handle_rpa_result(result)
        except Exception as e:
            error_msg = f"处理RPA结果时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self._handle_rpa_error(error_msg)
            
    def _handle_rpa_result(self, result):
        """处理RPA结果"""
        try:
            logger.debug(f'handle_rpa_result with: {result=}')
            self.is_running = False
            self._update_widget_enabled_state()

            if result is not None:
                if isinstance(result, dict):
                    # 处理数据文件
                    videos = result.get('data_file','') != '' and result.get('data_file','') is not None
                    data =  result.get('video_file','') != '' and result.get('video_file','') is not None
                    if videos:
                        self.data_file = result['data_file']
                        self.open_data_file_btn.setVisible(True)
                    else:
                        self.open_data_file_btn.setVisible(False)

                    # 处理视频文件
                    if data:
                        self.video_file = result['video_file']
                        self.open_video_file_btn.setVisible(True)
                    else:
                        self.open_video_file_btn.setVisible(False)

                    # 处理消息
                    if 'message' in result:
                        self.message_box.show_message(result['message'])

                    self.bottom_widget.setVisible(videos or data)

        except Exception as e:
            error_msg = f"处理RPA结果时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self._handle_rpa_error(error_msg)
            
    def _handle_rpa_error(self, error_msg: str):
        """处理RPA错误"""
        try:
            logger.debug(f'handle_rpa_error with: {error_msg=}')
            self.is_running = False
            self._update_widget_enabled_state()
            self.bottom_widget.setVisible(False)
            # 显示错误消息
            self.message_box.show_error(error_msg, "错误提示")

        except Exception as e:
            logger.error(f"处理RPA错误时发生异常: {str(e)}", exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            
    def _update_widget_enabled_state(self):
        """更新控件状态"""
        self.sidebar.setEnabled(not self.is_running)
        self.browser_toggle.setEnabled(not self.is_running)
        self.record_toggle.setEnabled(not self.is_running)
        self.start_button.setEnabled(not self.is_running)
        self.bottom_widget.setVisible(not self.is_running)
        if self.is_running:
            self.start_button.setText("运行中...")
            self.start_button.setStyleSheet(STOP_BUTTON_STYLE)
        else:
            self.start_button.setText("启动任务")
            self.start_button.setStyleSheet(START_BUTTON_STYLE)

    def update_text_content(self):
        """更新文本内容"""
        if self.tab_widget.currentIndex() == 0:
            try:
                # 更新功能说明
                doc_path = self.current_menu_item.get("doc")
                if not doc_path:
                    self.instruction_text.setHtml("<h1 style='color: #3498db;'><center>暂无功能说明</center></h1>")
                    logger.warning("未找到功能说明文档路径")
                    return
                # 读取HTML文件
                with open(doc_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 根据可用组件更新内容
                if WEBENGINE_AVAILABLE and self.instruction_web is not None:
                    self.instruction_web.setHtml(html_content)
                    # 使用JavaScript滚动到顶部
                    QTimer.singleShot(100, lambda: self.instruction_web.page().runJavaScript("window.scrollTo(0, 0);"))
                elif self.instruction_text is not None:
                    self.instruction_text.setHtml(html_content)
                    # 使用QTimer延迟设置滚动条位置
                    QTimer.singleShot(100, lambda: self.instruction_text.verticalScrollBar().setValue(0))
                    
            except FileNotFoundError:
                if WEBENGINE_AVAILABLE and self.instruction_web is not None:
                    self.instruction_web.setHtml("""
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <style>
                            body { 
                                font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
                                margin: 20px; 
                                line-height: 1.6;
                                color: #333;
                            }
                            h1 { color: #e74c3c; text-align: center; font-size: 20px; }
                        </style>
                    </head>
                    <body>
                        <h1>功能说明文档不存在</h1>
                    </body>
                    </html>
                    """)
                elif self.instruction_text is not None:
                    self.instruction_text.setHtml("<h1 style='color: #e74c3c;'>功能说明文档不存在</h1>")
            except Exception as e:
                if WEBENGINE_AVAILABLE and self.instruction_web is not None:
                    self.instruction_web.setHtml(f"""
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <style>
                            body {{ 
                                font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
                                margin: 20px; 
                                line-height: 1.6;
                                color: #333;
                            }}
                            h1 {{ color: #e74c3c; text-align: center; font-size: 20px; }}
                        </style>
                    </head>
                    <body>
                        <h1>读取文档失败: {str(e)}</h1>
                    </body>
                    </html>
                    """)
                elif self.instruction_text is not None:
                    self.instruction_text.setHtml(f"<h1 style='color: #e74c3c;'>读取文档失败: {str(e)}</h1>")
        else:
            steps_text = ""
            self.textedit_log.setPlainText(steps_text)
            QTimer.singleShot(100, lambda: self.textedit_log.verticalScrollBar().setValue(0))

    def clear_text_content(self):
        """清除文本内容"""
        self.textedit_log.clear()

    @Slot(str, str, int)
    def append_log(self, message: str, color: Optional[str] = None, level: Optional[int] = None):
        """添加日志"""
        try:
            # logger.debug(f"append_log called:{message=}")
            if not isinstance(message, str):
                message = str(message)
                
            # 根据日志级别设置颜色
            if color is None or color == '':
                if level == logging.ERROR:
                    color = 'red'
                elif level == logging.WARNING:
                    color = 'orange'
                elif level == logging.INFO:
                    color = 'gray'
                else:
                    color = 'gray'
                    
            # 在主线程中更新UI
            QTimer.singleShot(0, lambda: self._append_log(message, color))
            
        except Exception as e:
            logger.error(f"添加日志时发生错误: {str(e)}", exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            
    def _append_log(self, message: str, color: str):
        """内部日志添加方法"""
        try:
            # logger.debug(f"append_log called:{message=}")
            if color:
                self.textedit_log.append(f'<span style="color:{color}">{message}</span>')
            else:
                self.textedit_log.append(message)
                
            # 滚动到底部
            self.textedit_log.verticalScrollBar().setValue(
                self.textedit_log.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            logger.error(f"追加日志文本时发生错误: {str(e)}", exc_info=config.get_exc_info(), stack_info=config.get_stack_info())

    @Slot()
    def on_open_data_file(self):
        """打开数据文件"""
        os.startfile(self.data_file)

    @Slot()
    def on_open_video_file(self):
        """打开视频文件"""
        webbrowser.open(f"file:///{self.video_file.replace(os.sep, '/')}")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            # 停止正在运行的任务
            if self.is_running:
                self.start_rpa()
                
            # 清理资源
            self._cleanup_and_close()
            
            # 接受关闭事件
            event.accept()
            
        except Exception as e:
            error_msg = f"关闭窗口时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=config.get_exc_info(), stack_info=config.get_stack_info())
            self.message_box.show_error( error_msg, "错误提示")
            event.accept()
            
    def _cleanup_and_close(self):
        """清理资源并关闭"""
        try:
            # 清理工作线程和工作对象
            if self.worker:
                self.worker.stop()
                self.worker = None
                
            # 清理日志处理器
            if hasattr(self, 'qt_handler'):
                self.qt_handler.disconnect_signal()
                logger.removeHandler(self.qt_handler)
                
        except Exception as e:
            logger.error(f"清理资源时发生错误: {str(e)}", exc_info=config.get_exc_info(), stack_info=config.get_stack_info())


