from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, Slot
from typing import Optional

class MessageBox(QMessageBox):
    """自定义消息框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提示")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
    @Slot(str, str)
    def show_message(self, message: str, title: Optional[str] = None):
        """显示普通消息"""
        try:
            self.setIcon(QMessageBox.Information)
            self.setText(message)
            if title:
                self.setWindowTitle(title)
            self.exec()
        except Exception as e:
            print(f"显示消息时发生错误: {str(e)}")
            
    @Slot(str, str)
    def show_error(self, message: str, title: Optional[str] = None):
        """显示错误消息"""
        try:
            self.setIcon(QMessageBox.Critical)
            self.setText(message)
            if title:
                self.setWindowTitle(title)
            self.exec()
        except Exception as e:
            print(f"显示错误消息时发生错误: {str(e)}")
            
    @Slot(str, str)
    def show_warning(self, message: str, title: Optional[str] = None):
        """显示警告消息"""
        try:
            self.setIcon(QMessageBox.Warning)
            self.setText(message)
            if title:
                self.setWindowTitle(title)
            self.exec()
        except Exception as e:
            print(f"显示警告消息时发生错误: {str(e)}")
            
    @Slot(str, str)
    def show_question(self, message: str, title: Optional[str] = None) -> bool:
        """显示问题消息"""
        try:
            self.setIcon(QMessageBox.Question)
            self.setText(message)
            if title:
                self.setWindowTitle(title)
            return self.exec() == QMessageBox.Yes
        except Exception as e:
            print(f"显示问题消息时发生错误: {str(e)}")
            return False 