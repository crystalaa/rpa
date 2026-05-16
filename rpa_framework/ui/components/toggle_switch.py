from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt

class ToggleSwitch(QWidget):
    """开关组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = False
        self.setFixedSize(38, 18)  # 宽38，高18
        
    @property
    def state(self):
        return self._state
        
    @state.setter
    def state(self, value):
        if self._state != value:
            self._state = value
            self.update()
            
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        bg_color = QColor("#4CAF50") if self._state else QColor("#E0E0E0")
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(self.rect(), 9, 9)  # 圆角半径为高度一半
        
        # 绘制滑块
        margin = 2
        diameter = self.height() - 2 * margin  # 14px
        y = margin
        if self._state:
            x = self.width() - diameter - margin
        else:
            x = margin
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(x, y, diameter, diameter)
        
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.state = not self._state
            self.update()
            
    def update(self):
        """更新状态"""
        super().update()
        self.parent().update() if self.parent() else None 