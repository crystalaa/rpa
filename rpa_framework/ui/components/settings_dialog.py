"""
系统设置对话框

包含密码加密和页面保存功能的设置界面
"""

import os
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
    QMessageBox, QProgressBar, QGroupBox, QGridLayout,
    QListWidgetItem, QFrame, QSizePolicy, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

from rpa_framework.utils.encryptor import Encryptor
from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config


class RecordingThread(QThread):
    """页面录制线程"""
    progress_updated = Signal(str)
    recording_finished = Signal(str)
    error_occurred = Signal(str)
    step_recorded = Signal(int, str)  # 新增：步骤录制信号 (步骤号, 步骤描述)
    manual_save_requested = Signal()  # UI用于回显
    manual_save_signal = Signal()     # 新增：线程内手动保存信号
    
    def __init__(self, url: str, package_name: str, auto_record: bool = True):
        super().__init__()
        self.url = url
        self.package_name = package_name
        self.auto_record = auto_record
        self._should_stop = False
        self.recorder = None
        self.page = None
        self._manual_save_flag = False  # 标记是否有手动保存请求
        self.manual_save_signal.connect(self._on_manual_save_signal)
    
    def run(self):
        """运行录制"""
        try:
            self.progress_updated.emit("正在导入必要模块...")
            
            # 导入必要模块
            try:
                from playwright.sync_api import sync_playwright
                from rpa_framework.record import RPARecorder
                self.progress_updated.emit("导入RPARecorder模块成功")
            except Exception as e:
                self.error_occurred.emit(f"导入RPA录制器失败: {str(e)}")
                return
            
            self.progress_updated.emit("正在启动浏览器...")
            
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    page = browser.new_page()
                    
                    try:
                        self.progress_updated.emit("正在创建录制器...")
                        recorder = RPARecorder(page)
                        self.recorder = recorder
                        self.page = page
                        self.progress_updated.emit(f"正在访问: {self.url}")
                        page.goto(self.url)
                        page.wait_for_load_state('networkidle')
                        self.step_recorded.emit(0, "页面加载完成")
                        session_id = recorder.start_recording(auto_record=self.auto_record)
                        last_step_count = 0
                        while not self._should_stop:
                            # 只在自动录制模式下检查步骤事件
                            if self.auto_record:
                                try:
                                    recorder._check_step_events()
                                    current_actions = page.evaluate("window.rpaRecorder ? window.rpaRecorder.actions.length : 0")
                                    if current_actions > last_step_count:
                                        latest_action = page.evaluate(f"""
                                            window.rpaRecorder && window.rpaRecorder.actions.length > {last_step_count} ? 
                                            window.rpaRecorder.actions[{current_actions - 1}] : null
                                        """)
                                        if latest_action:
                                            step_desc = self._get_step_description(latest_action)
                                            self.step_recorded.emit(current_actions, f"第{current_actions}步: {step_desc}")
                                        last_step_count = current_actions
                                except Exception as e:
                                    pass
                            # 检查手动保存请求
                            if self._manual_save_flag:
                                self._manual_save_flag = False
                                try:
                                    if hasattr(self.recorder, 'manual_save_page'):
                                        self.recorder.manual_save_page(self.page)
                                        self.manual_save_requested.emit()  # 通知UI回显
                                    else:
                                        self._save_current_page_manually()
                                        self.manual_save_requested.emit()
                                except Exception as e:
                                    self.error_occurred.emit(f"手动保存页面失败: {str(e)}")
                            self.msleep(500)
                        self.progress_updated.emit("正在生成RPA开发包...")
                        package_path = recorder.generate_package(self.package_name)
                        self.recording_finished.emit(package_path)
                    except Exception as e:
                        self.error_occurred.emit(f"录制过程出错: {str(e)}")
                    finally:
                        browser.close()
            except Exception as e:
                self.error_occurred.emit(f"启动浏览器失败: {str(e)}")
                    
        except Exception as e:
            self.error_occurred.emit(f"启动录制失败: {str(e)}")
    
    def stop_recording(self):
        """停止录制"""
        self._should_stop = True
    
    def manual_save_page(self):
        """UI线程调用：发信号到录制线程"""
        self.manual_save_signal.emit()
    
    def _on_manual_save_signal(self):
        """录制线程内设置标记，主循环检测并执行保存"""
        self._manual_save_flag = True
    
    def _save_current_page_manually(self):
        """手动保存当前页面的默认实现"""
        try:
            if not self.page or not self.recorder:
                return
                
            # 创建手动保存的动作
            import time
            manual_action = {
                'type': 'manual_save',
                'tagName': 'PAGE',
                'element_info': {
                    'text': '手动保存页面',
                    'id': '',
                    'className': '',
                    'name': '',
                    'type': '',
                    'placeholder': '',
                    'value': ''
                },
                'page_info': {
                    'title': self.page.title,
                    'url': self.page.url,
                    'page_id': 'main',
                    'page_type': 'main'
                },
                'timestamp': int(time.time() * 1000),
                'value': ''
            }
            
            # 保存页面截图和HTML
            if hasattr(self.recorder, '_save_step_snapshot') and hasattr(self.recorder, 'page_actions'):
                total_steps = sum(len(actions) for actions in self.recorder.page_actions.values())
                self.recorder._save_step_snapshot(total_steps + 1, manual_action, self.page)
                
                # 添加到主页面的动作列表
                if 'page_01_main' in self.recorder.page_actions:
                    self.recorder.page_actions['page_01_main'].append(manual_action)
                    
        except Exception as e:
            self.error_occurred.emit(f"手动保存页面实现失败: {str(e)}")
    
    def _get_step_description(self, action: dict) -> str:
        """获取步骤描述"""
        action_type = action.get('type', 'unknown')
        element_info = action.get('element_info', {})
        
        if action_type == 'click':
            text = element_info.get('text', '').strip()
            if text and len(text) < 30:
                return f"点击 \"{text}\""
            else:
                tag_name = action.get('tagName', '元素')
                return f"点击 {tag_name}"
        elif action_type == 'input':
            placeholder = element_info.get('placeholder', '')
            name = element_info.get('name', '')
            field_name = placeholder or name or '输入框'
            value = action.get('value', '')
            if value and len(value) < 20:
                return f"输入 \"{value}\" 到 {field_name}"
            else:
                return f"在 {field_name} 中输入内容"
        elif action_type == 'select':
            return f"选择 \"{action.get('value', '选项')}\""
        else:
            return f"{action_type} 操作"


class DebugThread(QThread):
    """Playwright调试线程"""
    debug_started = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
    
    def run(self):
        """启动Playwright调试模式"""
        try:
            self.debug_started.emit("正在启动Playwright调试模式...")
            
            # 导入Playwright
            try:
                from playwright.sync_api import sync_playwright
            except Exception as e:
                self.error_occurred.emit(f"导入Playwright失败: {str(e)}")
                return
            
            # 启动调试模式
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    devtools=True,  # 自动打开开发者工具
                    slow_mo=1000    # 慢动作，便于调试
                )
                page = browser.new_page()
                
                # 导航到指定URL
                self.debug_started.emit(f"正在访问: {self.url}")
                
                if self.url.startswith('file://'):
                    # 本地文件
                    page.goto(self.url)
                else:
                    # 在线网页，确保有协议前缀
                    if not self.url.startswith(('http://', 'https://', 'file://')):
                        url = 'https://' + self.url
                    else:
                        url = self.url
                    page.goto(url)
                
                # 等待页面加载
                page.wait_for_load_state('networkidle')
                
                self.debug_started.emit("调试模式已启动，Playwright Inspector 已打开")
                self.debug_started.emit("您可以在Inspector中检查元素、编写和测试Playwright代码")
                
                # 激活调试模式 - 这会暂停执行并打开Playwright Inspector
                page.pause()
                
                # 当用户关闭Inspector或继续执行后，关闭浏览器
                browser.close()
                self.debug_started.emit("调试会话已结束")
                
        except Exception as e:
            self.error_occurred.emit(f"启动调试失败: {str(e)}")


class PasswordEncryptionTab(QWidget):
    """密码加密标签页"""
    
    def __init__(self):
        super().__init__()
        self.encryptor = Encryptor()
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🔐 密码加密工具")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 说明文本
        desc_label = QLabel("用于加密和解密敏感密码信息，确保配置文件安全。")
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # 密码输入区域
        input_layout = QGridLayout()
        
        input_layout.addWidget(QLabel("原始密码:"), 0, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入要加密的密码")
        input_layout.addWidget(self.password_input, 0, 1)
        
        # 显示密码按钮
        self.show_password_btn = QPushButton("👁")
        self.show_password_btn.setMaximumWidth(40)
        self.show_password_btn.setToolTip("显示/隐藏密码")
        self.show_password_btn.clicked.connect(self.toggle_password_visibility)
        input_layout.addWidget(self.show_password_btn, 0, 2)
        
        layout.addLayout(input_layout)
        
        # 按钮组
        button_layout = QHBoxLayout()
        self.encrypt_btn = QPushButton("🔒 加密")
        self.encrypt_btn.clicked.connect(self.encrypt_password)
        self.decrypt_btn = QPushButton("🔓 解密")
        self.decrypt_btn.clicked.connect(self.decrypt_password)
        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.clicked.connect(self.clear_all)
        
        button_layout.addWidget(self.encrypt_btn)
        button_layout.addWidget(self.decrypt_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 结果文本框
        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("加密或解密的结果将显示在这里...")
        self.result_text.setMaximumHeight(100)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        
        # 复制按钮
        self.copy_btn = QPushButton("📋 复制结果")
        self.copy_btn.clicked.connect(self.copy_result)
        layout.addWidget(self.copy_btn)
        
        # 使用说明
        usage_group = QGroupBox("使用说明")
        usage_layout = QVBoxLayout(usage_group)
        usage_text = """• 加密: 输入原始密码，点击"加密"按钮，将得到加密后的密文
• 解密: 输入加密后的密文，点击"解密"按钮，将得到原始密码
• 在配置文件中使用加密后的密码可以提高安全性
• 建议定期更换密码并重新加密"""
        usage_label = QLabel(usage_text.strip())
        usage_label.setStyleSheet("color: #555; line-height: 1.4;")
        usage_layout.addWidget(usage_label)
        layout.addWidget(usage_group)
        
        layout.addStretch()
    
    def toggle_password_visibility(self):
        """切换密码显示状态"""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_password_btn.setText("🙈")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_password_btn.setText("👁")
    
    def encrypt_password(self):
        """加密密码"""
        try:
            password = self.password_input.text().strip()
            if not password:
                QMessageBox.warning(self, "警告", "请输入要加密的密码")
                return
            
            encrypted = self.encryptor.encrypt(password)
            self.result_text.setText(encrypted)
            logger.info("密码加密成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加密失败: {str(e)}")
            logger.error(f"密码加密失败: {str(e)}")
    
    def decrypt_password(self):
        """解密密码"""
        try:
            encrypted_text = self.password_input.text().strip()
            if not encrypted_text:
                QMessageBox.warning(self, "警告", "请输入要解密的密文")
                return
            
            decrypted = self.encryptor.decrypt(encrypted_text)
            self.result_text.setText(decrypted)
            logger.info("密码解密成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解密失败: {str(e)}")
            logger.error(f"密码解密失败: {str(e)}")
    
    def copy_result(self):
        """复制结果到剪贴板"""
        result = self.result_text.toPlainText()
        if result:
            clipboard = QApplication.clipboard()
            clipboard.setText(result)
            QMessageBox.information(self, "成功", "结果已复制到剪贴板")
        else:
            QMessageBox.warning(self, "警告", "没有可复制的内容")
    
    def clear_all(self):
        """清空所有内容"""
        self.password_input.clear()
        self.result_text.clear()


class PageSaveTab(QWidget):
    """页面保存标签页"""
    
    def __init__(self):
        super().__init__()
        self.recording_thread = None
        self.last_generated_package_path = None  # 保存最后生成的包路径
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("📋 页面操作录制")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 说明文本
        desc_label = QLabel("录制业务人员的页面操作，自动生成RPA开发包。")
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # 录制设置组
        setting_group = QGroupBox("录制设置")
        setting_layout = QGridLayout(setting_group)
        
        setting_layout.addWidget(QLabel("流程名称:"), 0, 0)
        self.package_name_input = QLineEdit()
        self.package_name_input.setPlaceholderText("例如: 用户登录流程")
        setting_layout.addWidget(self.package_name_input, 0, 1)
        
        setting_layout.addWidget(QLabel("目标网址:"), 1, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        setting_layout.addWidget(self.url_input, 1, 1)
        
        layout.addWidget(setting_group)
        
        # 录制控制按钮
        control_layout = QHBoxLayout()
        
        # 自动录制checkbox
        self.auto_record_checkbox = QCheckBox("自动录制")
        self.auto_record_checkbox.setChecked(True)  # 默认勾选
        self.auto_record_checkbox.stateChanged.connect(self.on_auto_record_changed)
        
        self.start_btn = QPushButton("🎬 开始录制")
        self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn = QPushButton("⏹ 停止并保存")
        self.stop_btn.clicked.connect(self.stop_recording)
        self.stop_btn.setEnabled(False)
        
        # 保存页面按钮（手动模式使用）
        self.save_page_btn = QPushButton("💾 保存页面")
        self.save_page_btn.clicked.connect(self.manual_save_page)
        self.save_page_btn.setEnabled(False)  # 默认禁用，因为自动录制默认开启
        
        self.debug_btn = QPushButton("🐛 调试")
        self.debug_btn.clicked.connect(self.start_debug)
        self.debug_btn.setToolTip("启动Playwright调试模式，支持本地文件和在线网页")
        
        control_layout.addWidget(self.auto_record_checkbox)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.save_page_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.debug_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 录制进度显示
        progress_group = QGroupBox("操作步骤")
        progress_layout = QVBoxLayout(progress_group)
        
        # 步骤列表 - 改为多行文本框
        self.current_steps_list = QTextEdit()
        # self.current_steps_list.setMinimumHeight(100)  # 减小高度避免超出 group
        # self.current_steps_list.setMaximumHeight(100)  # 设置最大高度避免过度扩展
        self.current_steps_list.setReadOnly(True)  # 设置为只读
        self.current_steps_list.setPlaceholderText("录制的步骤将在这里显示...")
        self.current_steps_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 需要时显示滚动条
        self.current_steps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 需要时显示水平滚动条
        progress_layout.addWidget(self.current_steps_list)
        
        layout.addWidget(progress_group)
        
        # 录制状态和操作按钮（简化为直接的HBox布局）
        status_layout = QHBoxLayout()
        
        self.completion_label = QLabel("录制已就绪，请开始录制")  # 用于显示录制完成状态
        self.completion_label.setStyleSheet("color: #666; font-weight: bold;")
        
        self.open_package_btn = QPushButton("📂 打开包目录")
        self.open_package_btn.clicked.connect(self.open_generated_package)
        self.open_package_btn.setEnabled(False)  # 初始状态不可用
        
        status_layout.addWidget(self.completion_label)
        status_layout.addStretch()
        status_layout.addWidget(self.open_package_btn)
        
        layout.addLayout(status_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 使用说明
        usage_group = QGroupBox("使用说明")
        usage_layout = QVBoxLayout(usage_group)
        usage_text = """• 输入流程名称和目标网址，点击"开始录制"
• 系统会打开浏览器，在浏览器中进行你需要录制的操作
• 操作完成后，点击"停止并保存"生成RPA开发包
• 开发包包含可直接运行的Playwright代码和详细分析报告"""
        usage_label = QLabel(usage_text.strip())
        usage_label.setStyleSheet("color: #555; line-height: 1.4;")
        usage_layout.addWidget(usage_label)
        layout.addWidget(usage_group)
    
    def start_recording(self):
        """开始录制"""
        package_name = self.package_name_input.text().strip()
        url = self.url_input.text().strip()
        
        if not package_name:
            QMessageBox.warning(self, "警告", "请输入流程名称")
            return
        
        if not url:
            QMessageBox.warning(self, "警告", "请输入目标网址")
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_input.setText(url)
        
        try:
            # 清空当前步骤列表和状态
            self.current_steps_list.clear()
            self.completion_label.setText("")
            self.completion_label.setStyleSheet("color: #666; font-weight: bold;")
            
            # 获取自动录制模式状态
            auto_record = self.auto_record_checkbox.isChecked()
            
            # 创建录制线程
            self.recording_thread = RecordingThread(url, package_name, auto_record)
            self.recording_thread.progress_updated.connect(self.update_progress)
            self.recording_thread.recording_finished.connect(self.recording_finished)
            self.recording_thread.error_occurred.connect(self.recording_error)
            self.recording_thread.step_recorded.connect(self.add_step_to_list)  # 连接步骤录制信号
            self.recording_thread.manual_save_requested.connect(self.on_manual_save_requested)  # 连接手动保存信号
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.open_package_btn.setEnabled(False)  # 录制开始时禁用
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 无限进度条
            
            # 启动录制
            self.recording_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动录制失败: {str(e)}")
    
    def stop_recording(self):
        """停止录制"""
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.stop_recording()
    
    def update_progress(self, message: str):
        """更新进度信息"""
        self.completion_label.setText(message)
        self.completion_label.setStyleSheet("color: #007acc; font-weight: bold;")  # 设置录制过程中的样式
        logger.info(f"录制进度: {message}")
    
    def recording_finished(self, package_path: str):
        """录制完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # 在状态标签显示完成信息
        self.completion_label.setText("🎉 录制完成")
        self.completion_label.setStyleSheet("color: #28a745; font-weight: bold;")
        self.completion_label.setToolTip(f"包保存路径: {package_path}")
        
        # 更新最后生成的包路径
        self.last_generated_package_path = package_path
        self.open_package_btn.setEnabled(True)  # 录制完成后启用打开包目录按钮
        
        QMessageBox.information(self, "成功", f"RPA开发包已生成:\n{package_path}")
        
        # 清空输入
        # self.package_name_input.clear()
        # self.url_input.clear()
    
    def recording_error(self, error_message: str):
        """录制出错"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # 在状态标签显示错误信息
        self.completion_label.setText("❌ 录制失败")
        self.completion_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.completion_label.setToolTip(error_message)
        
        # 录制失败时，如果之前有成功的包，保持打开按钮可用
        # 否则禁用打开按钮
        if not self.last_generated_package_path:
            self.open_package_btn.setEnabled(False)
        
        QMessageBox.critical(self, "错误", error_message)
    
    def add_step_to_list(self, step_number: int, step_description: str):
        """添加步骤到列表"""
        step_text = f"✅ {step_description}"
        self.current_steps_list.append(step_text)
        # 自动滚动到最新步骤
        cursor = self.current_steps_list.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.current_steps_list.setTextCursor(cursor)
        self.current_steps_list.ensureCursorVisible()
    
    def open_generated_package(self):
        """打开最后生成的包"""
        if self.last_generated_package_path:
            try:
                os.startfile(self.last_generated_package_path)  # Windows
            except:
                try:
                    os.system(f'open "{self.last_generated_package_path}"')  # macOS
                except:
                    try:
                        os.system(f'xdg-open "{self.last_generated_package_path}"')  # Linux
                    except:
                        QMessageBox.warning(self, "警告", f"无法打开目录: {self.last_generated_package_path}")
        else:
            QMessageBox.warning(self, "警告", "没有可打开的包")
    
    def start_debug(self):
        """启动调试模式"""
        url = self.url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "警告", "请输入目标网址或本地文件路径")
            return
        
        try:
            # 处理不同类型的URL
            if url.startswith('file://'):
                # 本地文件路径
                debug_url = url
            elif url.startswith(('http://', 'https://')):
                # 在线网页
                debug_url = url
            elif url.startswith('/') or url.startswith('C:') or url.startswith('D:'):
                # 本地文件路径，需要转换为file://格式
                debug_url = f"file:///{url.replace('\\', '/')}"
            else:
                # 假设是在线网页，添加https://前缀
                debug_url = 'https://' + url
            
            # 创建调试线程
            self.debug_thread = DebugThread(debug_url)
            self.debug_thread.debug_started.connect(self.update_debug_status)
            self.debug_thread.error_occurred.connect(self.debug_error)
            
            # 更新状态显示
            self.completion_label.setText("🐛 正在启动调试模式...")
            self.completion_label.setStyleSheet("color: #722ed1; font-weight: bold;")
            
            # 启动调试
            self.debug_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动调试失败: {str(e)}")
    
    def update_debug_status(self, message: str):
        """更新调试状态"""
        self.completion_label.setText(f"🐛 {message}")
        self.completion_label.setStyleSheet("color: #722ed1; font-weight: bold;")
        logger.info(f"调试状态: {message}")
    
    def debug_error(self, error_message: str):
        """调试出错"""
        self.completion_label.setText("❌ 调试失败")
        self.completion_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.completion_label.setToolTip(error_message)
        QMessageBox.critical(self, "调试错误", error_message)
    
    def on_auto_record_changed(self, state):
        """自动录制checkbox状态改变"""
        is_auto_mode = state == Qt.CheckState.Checked
        self.save_page_btn.setEnabled(not is_auto_mode)  # 手动模式时启用保存页面按钮
        
        if is_auto_mode:
            self.save_page_btn.setToolTip("自动录制模式下，系统会自动保存页面")
        else:
            self.save_page_btn.setToolTip("手动模式下，点击此按钮保存当前页面")
    
    def manual_save_page(self):
        """手动保存当前页面（UI线程，只发信号）"""
        if self.recording_thread and self.recording_thread.isRunning():
            # 设置鼠标为沙漏状态，防止用户操作
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.save_page_btn.setEnabled(False)
            
            # 发送保存信号
            self.recording_thread.manual_save_page()  # 只发信号，不直接操作Page
            
            # 设置定时器，在保存完成后恢复鼠标状态
            # QTimer.singleShot(5000, self._restore_cursor_and_show_success)
        else:
            QMessageBox.warning(self, "警告", "请先开始录制")
    
    def _restore_cursor_and_show_success(self):
        """恢复鼠标状态并显示保存成功提示"""
        # 恢复鼠标箭头状态
        QApplication.restoreOverrideCursor()
        self.save_page_btn.setEnabled(True)
        # 显示保存成功弹窗
        QMessageBox.information(self, "保存成功", "页面已成功保存！")
    
    def on_manual_save_requested(self):
        """手动保存请求处理"""
        # 计算当前步骤号
        step_number = 1
        if self.recording_thread and self.recording_thread.recorder and self.recording_thread.recorder.page_actions:
            step_number = sum(len(actions) for actions in self.recording_thread.recorder.page_actions.values())
        step_desc = f"{step_number:02d}_手动保存页面"
        self.add_step_to_list(step_number, step_desc)
        self._restore_cursor_and_show_success()


class SettingsDialog(QDialog):
    """系统设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setModal(True)
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("系统设置")
        self.setMinimumSize(800, 600)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 密码加密标签页
        self.password_tab = PasswordEncryptionTab()
        self.tab_widget.addTab(self.password_tab, "🔐 密码加密")
        
        # 页面保存标签页
        self.page_save_tab = PageSaveTab()
        self.tab_widget.addTab(self.page_save_tab, "📋 页面录制")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)


def show_settings_dialog(parent=None):
    """显示系统设置对话框"""
    dialog = SettingsDialog(parent)
    return dialog.exec()
