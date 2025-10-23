from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QLabel, QToolButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Slot, QSize
from typing import List, Dict, Any
from rpa_framework.ui.styles.main_style import SIDEBAR_STYLE, SEARCH_STYLE, SEARCH_BTN_STYLE
from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger
import os

class Sidebar(QWidget):
    """侧边栏组件"""
    
    def __init__(self, menu_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        logger.debug("初始化侧边栏")
        self.setFixedWidth(300)
        # self.setObjectName("sidebar")
        self.setStyleSheet(SIDEBAR_STYLE)
        self.parent = parent  # 保存父窗口引用
        self.menu_data = menu_data
        self.menu_data_all = menu_data[:]  # 保存完整的菜单数据
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(0)
        
        # 创建搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("查找")
        self.search_edit.setStyleSheet(SEARCH_STYLE)
        self.search_edit.setFixedWidth(300)
        self.search_edit.returnPressed.connect(self.on_search)
        
        # 创建长方形圆角按钮，融合到搜索框
        btn_width = 28
        btn_height = 22
        search_edit_height = 28
        btn_top = (search_edit_height - btn_height) // 2
        self.search_btn = QToolButton(self.search_edit)
        self.search_btn.setIcon(QIcon(str(config.get_app_root() / "src/ui/resources/search.svg")))
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setStyleSheet(SEARCH_BTN_STYLE)
        self.search_btn.setIconSize(QSize(16, 16))
        self.search_btn.clicked.connect(self.on_search)
        # self.search_btn.move(self.search_edit.width() - btn_width - 500, btn_top)
        self.search_btn.raise_()
        def update_btn_pos():
            self.search_btn.move(self.search_edit.width() - btn_width - 10, btn_top)
        self.search_edit.resizeEvent = lambda event: (update_btn_pos(), QLineEdit.resizeEvent(self.search_edit, event))
        
        # 创建菜单列表
        self.menu_list = QListWidget()
        self.menu_list.setObjectName("menuList")
        self.menu_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 添加菜单项
        self._init_menu(self.menu_data)
        
        # 添加到布局
        layout.addWidget(self.search_edit)
        layout.addWidget(self.menu_list)
        logger.debug("侧边栏初始化完成")

    def _init_menu(self, menu_data: List[Dict[str, Any]]):
        """初始化菜单"""
        try:
            self.menu_list.clear()
            for item in menu_data:
                list_item = QListWidgetItem()
                list_item.setIcon(QIcon(item["icon"]))
                list_item.setText(item["name"])
                list_item.setSizeHint(QListWidgetItem().sizeHint())
                self.menu_list.addItem(list_item)
                
            # 设置默认选中项
            if self.menu_list.count() > 0:
                self.menu_list.setCurrentRow(0)
                
        except Exception as e:
            logger.error(f"初始化菜单失败: {str(e)}", exc_info=True)
            
    @Slot()
    def on_search(self):
        """处理搜索"""
        try:
            keyword = self.search_edit.text().strip()
            logger.debug(f"执行搜索: {keyword}")
            
            if not keyword:
                # 如果搜索框为空，显示所有菜单项
                self.menu_data = self.menu_data_all[:]
            else:
                # 过滤菜单项
                self.menu_data = [
                    item for item in self.menu_data_all 
                    if keyword.lower() in item["name"].lower()
                ]
                
            # 更新菜单
            self._init_menu(self.menu_data)
            logger.debug(f"搜索完成，找到 {len(self.menu_data)} 个结果")
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}", exc_info=True)
            
    def setEnabled(self, enabled: bool):
        """设置启用状态"""
        super().setEnabled(enabled)
        self.menu_list.setEnabled(enabled)
        self.search_edit.setEnabled(enabled)
        self.search_btn.setEnabled(enabled) 