"""
RPA操作录制器

负责录制用户在浏览器中的操作行为，生成RPA开发包
支持多页面录制功能
"""

import os
import json
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from playwright.sync_api import Page, BrowserContext

from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config


class RPARecorder:
    """RPA操作录制器 - 支持多页面录制"""
    
    def __init__(self, page: Page, context: Optional[BrowserContext] = None):
        """
        初始化录制器
        :param page: 主要的Playwright页面对象
        :param context: 浏览器上下文对象，用于监听新页面
        """
        self.main_page = page
        self.context = context or page.context
        self.config = config.get_config()
        self.save_dir = Path(self.config["screenshot"]["save_dir"])
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 录制状态
        self.is_recording = False
        self.session_id = None
        self.auto_record_mode = True  # 默认启用自动录制模式
        
        # 多页面管理
        self.recording_pages = {}  # 存储所有正在录制的页面 {page_id: page_object}
        self.page_actions = {}     # 存储每个页面的录制动作 {page_id: actions_list}
        self.page_counter = 0      # 页面计数器
        
        logger.debug(f"RPA录制器初始化完成，保存目录: {self.save_dir}")
    
    def start_recording(self, auto_record: bool = True) -> str:
        """
        开始录制用户操作
        :param auto_record: 是否启用自动录制模式，默认True
        :return: 录制会话ID
        """
        try:
            if self.is_recording:
                raise Exception("录制已经在进行中")
            
            self.session_id = str(uuid.uuid4())
            self.is_recording = True
            self.auto_record_mode = auto_record  # 保存录制模式
            
            # 创建临时截屏目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_screenshots_dir = self.save_dir / f"temp_recording_{timestamp}"
            self.temp_screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            # 注册主页面
            main_page_id = self._register_page(self.main_page, "main")
            
            # 只在自动录制模式下设置监听器
            if self.auto_record_mode:
                # 设置新页面监听器
                self._setup_popup_listeners()
                
                # 注入录制脚本到主页面
                self._inject_recording_script(self.main_page, main_page_id)
                
                # 启动步骤监听（兼容原有代码）
                if hasattr(self, '_start_step_listening'):
                    self._start_step_listening()
                else:
                    # 为兼容性提供基本的步骤监听
                    self._setup_basic_step_listening()
            else:
                # 手动录制模式：只保存初始页面状态
                logger.info("手动录制模式已启动，请使用保存页面按钮手动保存")
            
            # 保存初始页面状态（第00步）
            try:
                import time
                initial_action = {
                    'type': 'page_load',
                    'tagName': 'PAGE',
                    'page_id': main_page_id,
                    'element_info': {
                        'text': '页面加载',
                        'id': '',
                        'className': '',
                        'name': '',
                        'type': '',
                        'placeholder': '',
                        'value': ''
                    },
                    'page_info': {
                        'title': self.main_page.title() if callable(self.main_page.title) else self.main_page.title,
                        'url': self.main_page.url if isinstance(self.main_page.url, str) else self.main_page.url(),
                        'page_id': main_page_id,
                        'page_type': 'main'
                    },
                    'timestamp': int(time.time() * 1000),
                    'value': ''
                }
                self._save_step_snapshot(0, initial_action, self.main_page)
                logger.info("已保存初始页面状态")
            except Exception as e:
                logger.warning(f"保存初始页面状态失败: {str(e)}")
            
            logger.info(f"开始RPA操作录制，会话ID: {self.session_id}，模式: {'自动' if auto_record else '手动'}")
            return self.session_id
            
        except Exception as e:
            error_msg = f"启动操作录制失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _register_page(self, page: Page, page_type: str = "popup") -> str:
        """
        注册新页面进行录制
        :param page: 页面对象
        :param page_type: 页面类型（main/popup）
        :return: 页面ID
        """
        self.page_counter += 1
        page_id = f"page_{self.page_counter:02d}_{page_type}"
        
        self.recording_pages[page_id] = page
        self.page_actions[page_id] = []
        
        logger.info(f"注册新页面进行录制: {page_id} - {page.url}")
        return page_id
    
    def manual_save_page(self, page: Page):
        """
        手动保存当前页面
        :param page: 要保存的页面对象
        """
        try:
            if not self.is_recording:
                raise Exception("录制未开始，无法保存页面")
            
            # 找到对应的页面ID
            page_id = None
            for pid, p in self.recording_pages.items():
                if p == page:
                    page_id = pid
                    break
            if not page_id:
                page_id = "page_01_main"
            
            # 查找最近的页面操作（click/input/select）以复用selectors
            recent_selectors = None
            for actions in self.page_actions.values():
                for act in reversed(actions):
                    if act.get('type') in ['click', 'input', 'select'] and act.get('selectors'):
                        recent_selectors = act.get('selectors')
                        break
                if recent_selectors:
                    break
            if not recent_selectors:
                recent_selectors = [{"type": "css", "value": "body"}]
            
            import time
            # 计算当前总步骤数
            total_steps = sum(len(actions) for actions in self.page_actions.values())
            step_number = total_steps + 1
            manual_action = {
                'type': 'manual_save',
                'tagName': 'PAGE',
                'page_id': page_id,
                'element_info': {
                    'text': f'{step_number:02d}_手动保存页面',
                    'id': '',
                    'className': '',
                    'name': '',
                    'type': '',
                    'placeholder': '',
                    'value': ''
                },
                'page_info': {
                    'title': page.title() if callable(page.title) else page.title,
                    'url': page.url if isinstance(page.url, str) else page.url(),
                    'page_id': page_id,
                    'page_type': 'main' if page_id == "page_01_main" else 'popup'
                },
                'timestamp': int(time.time() * 1000),
                'value': '',
                'selectors': recent_selectors
            }
            self._save_step_snapshot(step_number, manual_action, page)
            if page_id in self.page_actions:
                self.page_actions[page_id].append(manual_action)
            logger.info(f"手动保存页面成功，步骤号: {step_number}")
        except Exception as e:
            error_msg = f"手动保存页面失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _setup_popup_listeners(self):
        """设置新页面弹出监听器"""
        def on_popup(popup: Page):
            try:
                logger.info(f"检测到新页面弹出: {popup.url}")
                
                # 等待新页面加载完成
                popup.wait_for_load_state('domcontentloaded', timeout=10000)
                
                # 注册新页面
                popup_page_id = self._register_page(popup, "popup")
                
                # 在新页面注入录制脚本
                self._inject_recording_script(popup, popup_page_id)
                
                # 保存新页面的初始状态
                try:
                    import time
                    popup_initial_action = {
                        'type': 'popup_open',
                        'tagName': 'PAGE',
                        'page_id': popup_page_id,
                        'element_info': {
                            'text': f'新页面打开: {popup.title() if callable(popup.title) else popup.title}',
                            'id': '',
                            'className': '',
                            'name': '',
                            'type': '',
                            'placeholder': '',
                            'value': ''
                        },
                        'page_info': {
                            'title': popup.title() if callable(popup.title) else popup.title,
                            'url': popup.url if isinstance(popup.url, str) else popup.url(),
                            'page_id': popup_page_id,
                            'page_type': 'popup'
                        },
                        'timestamp': int(time.time() * 1000),
                        'value': ''
                    }
                    
                    # 使用当前总的录制步骤数作为步骤编号
                    total_steps = sum(len(actions) for actions in self.page_actions.values())
                    self._save_step_snapshot(total_steps + 1, popup_initial_action, popup)
                    
                    # 将此动作添加到新页面的动作列表中
                    self.page_actions[popup_page_id].append(popup_initial_action)
                    
                    logger.info(f"新页面 {popup_page_id} 录制已启动")
                    
                except Exception as e:
                    logger.warning(f"保存新页面初始状态失败: {str(e)}")
                
                # 设置页面关闭监听
                def on_close(page):
                    try:
                        logger.info(f"页面 {popup_page_id} 已关闭")
                        # 可以在这里添加页面关闭时的清理逻辑
                    except Exception as e:
                        logger.warning(f"处理页面关闭事件失败: {str(e)}")
                
                popup.on('close', on_close)
                
            except Exception as e:
                logger.error(f"处理新页面弹出失败: {str(e)}")
        
        # 监听上下文中的所有新页面
        self.context.on('page', on_popup)
        logger.info("新页面监听器已设置")
    
    def _process_step_directly(self, step_number: int, action: Dict[str, Any], page: Page):
        """直接处理步骤保存（在主线程中调用）"""
        try:
            logger.debug(f"直接处理步骤: {step_number} - {action.get('type', 'unknown')}")
            self._save_step_snapshot(step_number, action, page)
        except Exception as e:
            logger.warning(f"直接处理步骤失败: {str(e)}")
    
    def stop_recording(self) -> List[Dict]:
        """
        停止录制并获取所有页面的操作数据
        :return: 合并后的操作数据列表
        """
        try:
            if not self.is_recording:
                raise Exception("当前没有进行录制")
            
            self.is_recording = False  # 停止录制
            
            # 处理任何待处理的步骤
            self.check_and_process_pending_steps()
            
            # 从所有页面收集录制数据
            all_actions = []
            
            for page_id, page in self.recording_pages.items():
                try:
                    if not page.is_closed():
                        # 获取页面的录制数据
                        page_actions = page.evaluate("window.rpaRecorder ? window.rpaRecorder.stopRecording() : []")
                        
                        # 为每个动作添加页面信息
                        for action in page_actions:
                            action['page_id'] = page_id
                            action['page_info'] = action.get('page_info', {})
                            action['page_info']['page_id'] = page_id
                            action['page_info']['page_type'] = 'main' if page_id.endswith('_main') else 'popup'
                        
                        all_actions.extend(page_actions)
                        logger.info(f"从页面 {page_id} 收集到 {len(page_actions)} 个操作")
                        
                except Exception as e:
                    logger.warning(f"从页面 {page_id} 收集录制数据失败: {str(e)}")
            
            # 合并手动保存的actions
            for page_id, actions_list in self.page_actions.items():
                for action in actions_list:
                    if action not in all_actions:
                        all_actions.append(action)

            # 按时间戳排序所有动作
            all_actions.sort(key=lambda x: x.get('timestamp', 0))

            # 重新编号
            for i, action in enumerate(all_actions, 1):
                action['id'] = i

            logger.info(f"停止录制，共记录 {len(all_actions)} 个操作，涉及 {len(self.recording_pages)} 个页面")
            return all_actions
            
        except Exception as e:
            error_msg = f"停止录制失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def generate_package(self, package_name: str, actions: Optional[List[Dict]] = None) -> str:
        """
        生成RPA开发包
        :param package_name: 用户输入的包名称
        :param actions: 操作数据（如果不提供则自动停止录制获取）
        :return: 生成的包路径
        """
        try:
            # 如果没有提供actions，则自动获取
            if actions is None:
                actions = self.stop_recording()
            
            # 允许manual_save类型也能生成包
            if not actions or not any(a.get('type') in ['click', 'input', 'select', 'manual_save'] for a in actions):
                raise Exception("没有录制到任何操作")
            
            # 导入依赖模块
            from .page_analyzer import PageAnalyzer
            from .code_generator import CodeGenerator
            from .report_generator import ReportGenerator
            
            # 清理包名并生成最终包名
            clean_package_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', package_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_package_name = f"{clean_package_name}_{timestamp}"
            
            # 创建包目录
            package_dir = self.save_dir / final_package_name
            package_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"开始生成RPA开发包: {final_package_name}")
            
            # 1. 保存操作记录
            self._save_recording_data(package_dir, package_name, actions)
            
            # 2. 移动步骤截屏
            self._move_temp_screenshots(package_dir)
            
            # 3. 进行页面分析
            page_analyzer = PageAnalyzer(self.main_page)
            page_analysis = page_analyzer.analyze_page()
            page_analyzer.save_analysis(package_dir, page_analysis)
            
            # 4. 生成代码
            code_generator = CodeGenerator()
            playwright_code = code_generator.generate_playwright_code(actions, package_name)
            code_generator.save_code(package_dir, playwright_code)
            
            # 5. 生成报告和文档
            report_generator = ReportGenerator()
            report_generator.generate_all_reports(
                package_dir, package_name, final_package_name, actions, page_analysis
            )
            
            # 6. 保存最终状态截图
            self._save_final_screenshot(package_dir)
            
            logger.info(f"RPA开发包生成完成: {package_dir}")
            return str(package_dir)
            
        except Exception as e:
            error_msg = f"生成RPA开发包失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _inject_recording_script(self, page: Page, page_id: str):
        """向页面注入录制脚本"""
        try:
            js_code = """
                // 初始化RPA录制器
                window.rpaRecorder = {
                    isRecording: true,
                    actions: [],
                    startTime: Date.now(),
                    page_id: '""" + page_id + """',
                    lastInputElement: null,
                    inputTimer: null,
                    inputDebounceDelay: 800,  // 减少到800ms，提高响应性
                    popupDetectionEnabled: true,  // 启用弹窗检测
                
                generatePlaywrightSelector: function(element) {
                    const selectors = [];
                    
                    // 1. getByRole优先级最高（accessibility最佳实践）
                    const role = element.getAttribute('role') || this.getImplicitRole(element);
                    if (role) {
                        const name = this.getAssociatedLabel(element) || element.getAttribute('aria-label') || (element.textContent || '').trim();
                        if (name) {
                            selectors.push({type: 'role', role: role, name: name, priority: 1});
                        } else {
                            selectors.push({type: 'role', role: role, priority: 2});
                        }
                    }
                    
                    // 2. getByLabel（适用于表单元素）
                    const labelText = this.getAssociatedLabel(element);
                    if (labelText) {
                        selectors.push({type: 'label', value: labelText, priority: 1});
                    }
                    
                    // 3. getByText（适用于可见文本）
                    const text = (element.textContent || '').trim();
                    if (text && text.length > 0 && text.length <= 50 && !text.includes('\\n')) {
                        selectors.push({type: 'text', value: text, priority: 2});
                    }
                    
                    // 4. getByPlaceholder（适用于输入框）
                    const placeholder = element.getAttribute('placeholder');
                    if (placeholder) {
                        selectors.push({type: 'placeholder', value: placeholder, priority: 2});
                    }
                    
                    // 5. getByTitle
                    const title = element.getAttribute('title');
                    if (title) {
                        selectors.push({type: 'title', value: title, priority: 3});
                    }
                    
                    // 6. getByTestId
                    const testId = element.getAttribute('data-testid') || element.getAttribute('data-test');
                    if (testId) {
                        selectors.push({type: 'testId', value: testId, priority: 1});
                    }
                    
                    // 7. CSS选择器（稳定的class或id）
                    if (element.id && !element.id.match(/^(\\d|tmp|temp|generated)/)) {
                        selectors.push({type: 'css', value: `#${element.id}`, priority: 3});
                    }
                    
                    // 查找稳定的class名
                    if (element.className) {
                        const classes = element.className.split(' ').filter(cls => 
                            cls && !cls.match(/(\\d{6,}|[a-f0-9]{8,}|v-[a-f0-9]+|css-[a-f0-9]+|^_|tmp|temp)/)
                        );
                        const stableClass = classes.find(cls => cls.length > 2);
                        if (stableClass) {
                            selectors.push({type: 'css', value: `.${stableClass}`, priority: 6});
                        }
                    }
                    
                    // 8. XPath作为最后选择
                    selectors.push({type: 'xpath', value: this.getXPath(element), priority: 10});
                    
                    return selectors.sort((a, b) => a.priority - b.priority);
                },
                
                // 增强的弹窗检测
                detectPopupTrigger: function(element) {
                    const popupIndicators = [
                        element.getAttribute('target') === '_blank',
                        element.getAttribute('rel') === 'noopener',
                        element.onclick && element.onclick.toString().includes('window.open'),
                        element.getAttribute('onclick') && element.getAttribute('onclick').includes('window.open'),
                        element.href && (element.href.includes('javascript:') || element.href.includes('popup')),
                        element.classList.contains('popup-trigger'),
                        element.classList.contains('modal-trigger'),
                        element.getAttribute('data-popup'),
                        element.getAttribute('data-modal')
                    ];
                    
                    return popupIndicators.some(indicator => indicator);
                },
                
                // 检测菜单项
                detectMenuItem: function(element) {
                    const menuIndicators = [
                        element.getAttribute('role') === 'menuitem',
                        element.classList.contains('menu-item'),
                        element.classList.contains('dropdown-item'),
                        element.closest('[role="menu"]') !== null,
                        element.closest('.menu') !== null,
                        element.closest('.dropdown-menu') !== null
                    ];
                    
                    return menuIndicators.some(indicator => indicator);
                },
                
                getImplicitRole: function(element) {
                    const tagName = element.tagName.toLowerCase();
                    const roleMap = {
                        'button': 'button',
                        'a': 'link',
                        'input': element.type === 'submit' ? 'button' : 'textbox',
                        'textarea': 'textbox',
                        'select': 'combobox',
                        'h1': 'heading',
                        'h2': 'heading',
                        'h3': 'heading',
                        'h4': 'heading',
                        'h5': 'heading',
                        'h6': 'heading',
                        'img': 'img',
                        'table': 'table',
                        'form': 'form'
                    };
                    return roleMap[tagName] || null;
                },
                
                getAssociatedLabel: function(element) {
                    // 查找associated label
                    if (element.id) {
                        const label = document.querySelector(`label[for="${element.id}"]`);
                        if (label) return label.textContent?.trim();
                    }
                    
                    // 查找包含的label
                    const parentLabel = element.closest('label');
                    if (parentLabel) return parentLabel.textContent?.trim();
                    
                    // 查找aria-label
                    if (element.getAttribute('aria-label')) {
                        return element.getAttribute('aria-label');
                    }
                    
                    return null;
                },
                
                getXPath: function(element) {
                    if (element.id) {
                        return `//*[@id="${element.id}"]`;
                    }
                    if (element === document.body) {
                        return '/html/body';
                    }
                    let ix = 0;
                    const siblings = element.parentNode.childNodes;
                    for (let i = 0; i < siblings.length; i++) {
                        const sibling = siblings[i];
                        if (sibling === element) {
                            return this.getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                            ix++;
                        }
                    }
                },
                
                shouldRecordStep: function(type, element) {
                    if (type === 'click') {
                        const tagName = element.tagName.toLowerCase();
                        const inputType = (element.type || '').toLowerCase();
                        
                        // 不记录的点击：输入框、文本区域的点击
                        if (tagName === 'input') {
                            if (!['checkbox', 'radio', 'button', 'submit', 'reset'].includes(inputType)) {
                                return false;
                            }
                        }
                        if (tagName === 'textarea') {
                            return false;
                        }
                        
                        // 记录的点击：按钮、链接等
                        if (tagName === 'button') return true;
                        if (tagName === 'a' && element.href) return true;
                        if (tagName === 'input' && ['button', 'submit', 'reset', 'checkbox', 'radio'].includes(inputType)) return true;
                        if (element.getAttribute('role') === 'button') return true;
                        if (element.onclick || element.getAttribute('onclick')) return true;
                        
                        // 检查是否是有意义的可点击元素
                        const text = (element.textContent || '').trim();
                        if (text && text.length > 0 && text.length < 100) {
                            const clickableIndicators = [
                                element.classList.contains('btn'),
                                element.classList.contains('button'), 
                                element.classList.contains('link'),
                                element.style.cursor === 'pointer',
                                element.hasAttribute('data-action'),
                                element.hasAttribute('data-click'),
                                this.detectPopupTrigger(element),
                                this.detectMenuItem(element)
                            ];
                            
                            if (clickableIndicators.some(indicator => indicator)) {
                                return true;
                            }
                            
                            if (text.length <= 20 && /^[\\u4e00-\\u9fa5a-zA-Z0-9\\s]{1,20}$/.test(text)) {
                                return true;
                            }
                        }
                        
                        return false;
                    }
                    
                    return true;
                },
                
                recordAction: function(type, element, value) {
                    if (!this.isRecording) return;
                    
                    if (!this.shouldRecordStep(type, element)) {
                        return;
                    }
                    
                    // 对于输入操作，实现防抖合并
                    if (type === 'input') {
                        this.handleInputAction(element, value);
                        return;
                    }
                    
                    // 对于非输入操作，如果有未完成的输入，立即完成它
                    if (this.inputTimer && this.lastInputElement) {
                        this.finalizeInput();
                    }
                    
                    const rect = element.getBoundingClientRect();
                    const action = {
                        id: this.actions.length + 1,
                        timestamp: Date.now() - this.startTime,
                        type: type,
                        tagName: element.tagName,
                        selectors: this.generatePlaywrightSelector(element),
                        value: value || '',
                        position: {
                            x: Math.round(rect.x + rect.width / 2),
                            y: Math.round(rect.y + rect.height / 2),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        element_info: {
                            id: element.id || '',
                            className: element.className || '',
                            name: element.name || '',
                            type: element.type || '',
                            placeholder: element.placeholder || '',
                            value: element.value || '',
                            text: (element.textContent || '').trim().substring(0, 100)
                        },
                        page_info: {
                            url: window.location.href,
                            title: document.title,
                            page_id: this.page_id
                        },
                        // 新增：特殊标记
                        special_flags: {
                            is_popup_trigger: this.detectPopupTrigger(element),
                            is_menu_item: this.detectMenuItem(element),
                            is_role_based: element.getAttribute('role') !== null
                        }
                    };
                    
                    this.actions.push(action);
                    console.log('RPA Action recorded:', action.type, 'on page:', this.page_id, 'flags:', action.special_flags);
                    
                    // 通知后端保存步骤
                    this.notifyStepRecorded(action);
                },
                
                handleInputAction: function(element, value) {
                    // 如果是不同元素的输入，先完成之前的输入
                    if (this.lastInputElement && this.lastInputElement !== element && this.inputTimer) {
                        this.finalizeInput();
                    }
                    
                    // 清除之前的定时器
                    if (this.inputTimer) {
                        clearTimeout(this.inputTimer);
                    }
                    
                    // 如果是同一个元素，更新最后一个输入操作
                    if (this.lastInputElement === element && this.actions.length > 0) {
                        const lastAction = this.actions[this.actions.length - 1];
                        if (lastAction.type === 'input' && lastAction.element_info.id === element.id) {
                            lastAction.value = value;
                            lastAction.timestamp = Date.now() - this.startTime;
                            lastAction.selectors = this.generatePlaywrightSelector(element);
                            
                            // 重新设置防抖定时器
                            this.inputTimer = setTimeout(() => {
                                this.finalizeInput();
                            }, this.inputDebounceDelay);
                            return;
                        }
                    }
                    
                    // 创建新的输入操作
                    const rect = element.getBoundingClientRect();
                    const action = {
                        id: this.actions.length + 1,
                        timestamp: Date.now() - this.startTime,
                        type: 'input',
                        tagName: element.tagName,
                        selectors: this.generatePlaywrightSelector(element),
                        value: value || '',
                        position: {
                            x: Math.round(rect.x + rect.width / 2),
                            y: Math.round(rect.y + rect.height / 2),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        element_info: {
                            id: element.id || '',
                            className: element.className || '',
                            name: element.name || '',
                            type: element.type || '',
                            placeholder: element.placeholder || '',
                            value: element.value || '',
                            text: (element.textContent || '').trim().substring(0, 100)
                        },
                        page_info: {
                            url: window.location.href,
                            title: document.title,
                            page_id: this.page_id
                        }
                    };
                    
                    this.actions.push(action);
                    this.lastInputElement = element;
                    
                    // 设置防抖定时器
                    this.inputTimer = setTimeout(() => {
                        this.finalizeInput();
                    }, this.inputDebounceDelay);
                },
                
                finalizeInput: function() {
                    if (this.inputTimer) {
                        clearTimeout(this.inputTimer);
                        this.inputTimer = null;
                    }
                    
                    if (this.lastInputElement && this.actions.length > 0) {
                        const lastAction = this.actions[this.actions.length - 1];
                        if (lastAction.type === 'input') {
                            this.notifyStepRecorded(lastAction);
                        }
                    }
                    
                    this.lastInputElement = null;
                },
                
                notifyStepRecorded: function(action) {
                    // 延迟处理，确保浏览器先完成对用户操作的响应
                    setTimeout(() => {
                        // 显示处理提示并暂停用户操作
                        this.showProcessingOverlay();
                        
                        // 直接将步骤信息存储到window对象，供Python检查
                        window.pendingStepToProcess = {
                            stepNumber: action.id,
                            action: action,
                            timestamp: Date.now()
                        };
                        
                        // 通过自定义事件通知后端（保持兼容性）
                        const event = new CustomEvent('rpaStepRecorded', {
                            detail: {
                                stepNumber: action.id,
                                action: action
                            }
                        });
                        document.dispatchEvent(event);
                    }, 200); // 200ms延迟，确保浏览器完成状态更新
                },
                
                showProcessingOverlay: function() {
                    // 移除已存在的遮罩
                    this.hideProcessingOverlay();
                    
                    // 创建遮罩层
                    const overlay = document.createElement('div');
                    overlay.id = 'rpa-processing-overlay';
                    overlay.style.cssText = `
                        position: fixed !important;
                        top: 0 !important;
                        left: 0 !important;
                        width: 100vw !important;
                        height: 100vh !important;
                        background: rgba(0, 0, 0, 0.3) !important;
                        z-index: 999999 !important;
                        display: flex !important;
                        align-items: center !important;
                        justify-content: center !important;
                        pointer-events: auto !important;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
                    `;
                    
                    // 创建提示信息
                    const message = document.createElement('div');
                    message.style.cssText = `
                        background: white !important;
                        padding: 20px 30px !important;
                        border-radius: 8px !important;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
                        text-align: center !important;
                        max-width: 400px !important;
                        color: #333 !important;
                        font-size: 16px !important;
                        line-height: 1.5 !important;
                    `;
                    
                    message.innerHTML = `
                        <div style="color: #1890ff; font-size: 18px; font-weight: bold; margin-bottom: 10px;">🔄 正在处理录制步骤</div>
                        <div style="margin-bottom: 10px;">正在保存页面截图和HTML文件...</div>
                        <div style="font-size: 14px; color: #666;">请稍候，完成后可继续操作</div>
                        <div style="margin-top: 15px;">
                            <div style="width: 200px; height: 4px; background: #f0f0f0; border-radius: 2px; margin: 0 auto; overflow: hidden;">
                                <div id="rpa-progress-bar" style="height: 100%; background: #1890ff; width: 0%; transition: width 0.3s; border-radius: 2px;"></div>
                            </div>
                        </div>
                    `;
                    
                    overlay.appendChild(message);
                    document.body.appendChild(overlay);
                    
                    // 启动进度条动画
                    const progressBar = document.getElementById('rpa-progress-bar');
                    if (progressBar) {
                        let progress = 0;
                        const interval = setInterval(() => {
                            progress += 2;
                            progressBar.style.width = progress + '%';
                            if (progress >= 100) {
                                clearInterval(interval);
                            }
                        }, 50);
                    }
                },
                
                hideProcessingOverlay: function() {
                    const overlay = document.getElementById('rpa-processing-overlay');
                    if (overlay) {
                        overlay.remove();
                    }
                },
                
                stopRecording: function() {
                    this.isRecording = false;
                    this.hideProcessingOverlay();
                    return this.actions;
                }
            };
            
            // 添加事件监听
            document.addEventListener('click', function(e) {
                if (window.rpaRecorder) {
                    window.rpaRecorder.recordAction('click', e.target);
                }
            }, true);
            
            document.addEventListener('input', function(e) {
                if (window.rpaRecorder) {
                    window.rpaRecorder.recordAction('input', e.target, e.target.value);
                }
            }, true);
            
            // 监听select变化
            document.addEventListener('change', function(e) {
                if (window.rpaRecorder && e.target.tagName === 'SELECT') {
                    window.rpaRecorder.recordAction('select', e.target, e.target.value);
                }
            }, true);
            
            console.log('录制脚本已注入页面:', '""" + page_id + """');
            """
            
            page.evaluate(js_code)
            logger.info(f"页面 {page_id} 录制脚本注入成功")
            
        except Exception as e:
            logger.error(f"注入录制脚本失败: {str(e)}")
    
    def _save_recording_data(self, package_dir: Path, package_name: str, actions: List[Dict]):
        """保存录制数据"""
        recording_path = package_dir / "recording.json"
        with open(recording_path, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": self.session_id,
                "package_name": package_name,
                "total_actions": len(actions),
                "duration_ms": actions[-1]["timestamp"] if actions else 0,
                "recorded_at": datetime.now().isoformat(),
                "actions": actions
            }, f, ensure_ascii=False, indent=2)
    
    def _setup_basic_step_listening(self):
        """设置基本的步骤监听（兼容性方法）"""
        try:
            self.main_page.evaluate("""
                document.addEventListener('rpaStepRecorded', function(event) {
                    window.lastRecordedStep = event.detail;
                });
            """)
            logger.debug("基本步骤监听已设置")
        except Exception as e:
            logger.warning(f"设置步骤监听失败: {str(e)}")
    
    def _start_step_listening(self):
        """启动步骤监听"""
        # 注入步骤监听脚本
        self.main_page.evaluate("""
            document.addEventListener('rpaStepRecorded', function(event) {
                window.lastRecordedStep = event.detail;
            });
        """)
    
    def _save_step_snapshot(self, step_number: int, action: Dict[str, Any], page: Page):
        """
        保存步骤快照（截屏+页面HTML）
        :param step_number: 步骤编号
        :param action: 操作信息
        :param page: 页面对象
        """
        try:
            # 生成步骤描述
            action_desc = self._get_step_description(action)
            filename_prefix = self._sanitize_filename(f"{step_number:02d}_{action_desc}")
            
            # 根据操作类型进行智能等待
            self._wait_for_action_complete(action)
            
            # 等待页面稳定（动画完成、网络空闲）
            self._wait_for_page_stability()
            
            # 临时隐藏遮罩层进行截屏（确保截屏不包含处理浮窗）
            overlay_hidden = page.evaluate("""() => {
                const rpaOverlay = document.getElementById('rpa-processing-overlay');
                if (rpaOverlay) {
                    rpaOverlay.style.display = 'none';
                    return true;
                }
                return false;
            }""")
            
            # 短暂等待确保遮罩隐藏生效
            page.wait_for_timeout(200)
            
            # 保存截图（全页面截图）
            screenshot_path = self.temp_screenshots_dir / f"{filename_prefix}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            
            # 恢复遮罩层
            if overlay_hidden:
                page.evaluate("""() => {
                    const rpaOverlay = document.getElementById('rpa-processing-overlay');
                    if (rpaOverlay) {
                        rpaOverlay.style.display = 'flex';
                    }
                }""")
            
            # 保存页面HTML（增强版本，内联CSS确保样式正确显示）
            try:
                # 临时隐藏遮罩层
                overlay_hidden = page.evaluate("""() => {
                const rpaOverlay = document.getElementById('rpa-processing-overlay');
                if (rpaOverlay) {
                        rpaOverlay.style.display = 'none';
                        return true;
                    }
                    return false;
                }""")
                
                # 获取页面内容并内联CSS
                html_content = page.evaluate("""() => {
                    return new Promise((resolve) => {
                        try {
                            // 克隆当前文档
                            const docClone = document.cloneNode(true);
                            const htmlClone = docClone.documentElement;
                            
                            // 收集所有外部CSS内容
                            const linkElements = Array.from(document.querySelectorAll('link[rel="stylesheet"], link[rel="preload"][as="style"]'));
                            const stylePromises = [];
                            
                            linkElements.forEach((link, index) => {
                                if (link.href && !link.href.startsWith('data:')) {
                                    const promise = fetch(link.href)
                                        .then(response => response.text())
                                        .then(cssContent => ({
                                            index: index,
                                            content: cssContent,
                                            href: link.href
                                        }))
                                        .catch(error => {
                                            console.warn('Failed to fetch CSS:', link.href, error);
                                            return {
                                                index: index,
                                                content: `/* Failed to load: ${link.href} */`,
                                                href: link.href
                                            };
                                        });
                                    stylePromises.push(promise);
                                }
                            });
                            
                            // 如果没有外部CSS，直接返回当前HTML
                            if (stylePromises.length === 0) {
                                resolve(document.documentElement.outerHTML);
                                return;
                            }
                            
                            // 等待所有CSS加载完成
                            Promise.all(stylePromises).then(cssResults => {
                                try {
                                    // 在克隆的文档中替换CSS链接为内联样式
                                    const cloneLinks = Array.from(htmlClone.querySelectorAll('link[rel="stylesheet"], link[rel="preload"][as="style"]'));
                                    
                                    cssResults.forEach(cssResult => {
                                        if (cssResult.index < cloneLinks.length) {
                                            const linkElement = cloneLinks[cssResult.index];
                                            
                                            // 创建内联style标签
                                            const styleElement = htmlClone.ownerDocument.createElement('style');
                                            styleElement.textContent = `
/* Inlined from: ${cssResult.href} */
${cssResult.content}`;
                                            
                                            // 替换link标签
                                            linkElement.parentNode.insertBefore(styleElement, linkElement);
                                            linkElement.remove();
                                        }
                                    });
                                    
                                    // 添加额外的基础样式确保兼容性
                                    const additionalStyle = htmlClone.ownerDocument.createElement('style');
                                    additionalStyle.textContent = `
/* RPA录制 - 本地兼容性样式 */
* {
    box-sizing: border-box;
}
body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
}
img {
    max-width: 100%;
    height: auto;
}
/* 确保布局不受外部资源加载失败影响 */
.ant-layout {
    min-height: 100vh;
}
`;
                                    htmlClone.querySelector('head').appendChild(additionalStyle);
                                    
                                    resolve('<!DOCTYPE html>' + htmlClone.outerHTML);
                } catch (error) {
                                    console.error('Error processing CSS inlining:', error);
                                    resolve(document.documentElement.outerHTML);
                                }
                            }).catch(error => {
                                console.error('Error loading CSS:', error);
                                resolve(document.documentElement.outerHTML);
                            });
                            
                        } catch (error) {
                            console.error('Error in HTML processing:', error);
                            resolve(document.documentElement.outerHTML);
                        }
                    });
                }""")
                
                # 恢复遮罩层
                if overlay_hidden:
                    page.evaluate("""() => {
                        const rpaOverlay = document.getElementById('rpa-processing-overlay');
                        if (rpaOverlay) {
                            rpaOverlay.style.display = 'flex';
                }
            }""")
                    
            except Exception as e:
                logger.warning(f"获取增强HTML失败，使用基础方式: {str(e)}")
                html_content = page.content()
            
            # 清理HTML内容（移除多余元素但保留样式）
            html_content = self._clean_step_html(html_content)
            
            # 添加步骤信息到HTML
            step_info = f"""<!--
=== RPA录制步骤信息 ===
步骤编号: {step_number:02d}
操作描述: {action_desc}
操作类型: {action.get('type', 'unknown')}
目标元素: {action.get('tagName', 'unknown')}
页面状态: {action.get('page_info', {}).get('title', '未知页面')}
录制说明: 此页面状态反映了执行该步骤时的实际页面内容
        如果页面内容与预期不同，通常是因为页面跳转或状态变化
        这是正常的业务流程，不是录制错误
CSS处理: 外部CSS已内联，确保本地打开时样式正确显示
输入防抖: 改进了输入防抖机制，减少步骤丢失问题
-->
{html_content}"""
            
            html_path = self.temp_screenshots_dir / f"{filename_prefix}.html"
            try:
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(step_info)
                
                # 验证文件是否正确保存
                if html_path.exists() and html_path.stat().st_size > 0:
                    logger.debug(f"HTML文件保存成功: {html_path}")
                else:
                    raise Exception(f"HTML文件保存后为空: {html_path}")
                    
            except Exception as html_error:
                logger.error(f"保存HTML文件失败: {str(html_error)}")
                # 尝试保存简化版本的HTML
                try:
                    simple_html = page.content()
                    fallback_info = f"""<!--
=== RPA录制步骤信息（简化版本）===
步骤编号: {step_number:02d}
操作描述: {action_desc}
保存说明: 完整HTML保存失败，使用简化版本
错误信息: {str(html_error)}
-->
{simple_html}"""
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_info)
                    logger.warning(f"使用简化HTML保存步骤 {step_number}")
                except Exception as fallback_error:
                    logger.error(f"简化HTML保存也失败: {str(fallback_error)}")
                    # 创建错误说明文件
                    error_content = f"""<!--
HTML保存失败
步骤编号: {step_number:02d}
操作描述: {action_desc}
原始错误: {str(html_error)}
后备错误: {str(fallback_error)}
-->
<html><body><h1>HTML保存失败</h1><p>请查看截图了解页面状态</p></body></html>"""
                    try:
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(error_content)
                    except:
                        pass  # 最后的尝试失败也不再抛出异常
                
            logger.debug(f"步骤 {step_number} 快照已保存: {filename_prefix}")
            
            # 通知前端步骤处理完成，恢复用户操作
            self._notify_step_processing_complete()
            
        except Exception as e:
            logger.warning(f"保存步骤 {step_number} 快照失败: {str(e)}")
            # 即使失败也要恢复用户操作
            self._notify_step_processing_complete()
    
    def _wait_for_action_complete(self, action: Dict[str, Any]):
        """
        根据操作类型等待操作完成
        :param action: 操作信息
        """
        try:
            action_type = action.get('type', 'unknown')
            element_info = action.get('element_info', {})
            element_text = element_info.get('text', '').lower()
            
            logger.debug(f"等待操作完成: {action_type} - {element_text}")
            
            # 基础等待时间
            base_wait = 500
            
            if action_type == 'click':
                # 点击操作的智能等待
                if any(keyword in element_text for keyword in ['登录', 'login', '提交', 'submit', '保存', 'save']):
                    # 登录、提交类按钮，可能触发页面跳转或AJAX请求
                    logger.debug("检测到登录/提交类操作，延长等待时间")
                    base_wait = 2000  # 2秒
                elif any(keyword in element_text for keyword in ['确定', '确认', 'ok', 'confirm', '是', 'yes']):
                    # 确认类按钮，通常有模态框或状态变化
                    logger.debug("检测到确认类操作，适中等待时间")
                    base_wait = 1000  # 1秒
                elif any(keyword in element_text for keyword in ['取消', 'cancel', '关闭', 'close']):
                    # 取消类按钮，通常响应较快
                    logger.debug("检测到取消类操作，短等待时间")
                    base_wait = 300
                else:
                    # 其他点击操作
                    logger.debug("一般点击操作，标准等待时间")
                    base_wait = 800
                    
            elif action_type == 'input':
                # 输入操作，等待输入验证或格式化
                logger.debug("输入操作，短等待时间")
                base_wait = 300
                
            elif action_type == 'page_load':
                # 页面加载，需要更长等待
                logger.debug("页面加载操作，长等待时间")
                base_wait = 1500
                
            # 执行等待
            self.main_page.wait_for_timeout(base_wait)
            logger.debug(f"操作后等待完成: {base_wait}ms")
            
        except Exception as e:
            logger.debug(f"操作等待失败: {str(e)}")
            # 失败时使用默认等待
            try:
                self.main_page.wait_for_timeout(500)
            except:
                pass
    
    def _wait_for_page_stability(self):
        """等待页面稳定（动画、网络加载等完成）"""
        try:
            logger.debug("开始等待页面稳定...")
            
            # 1. 等待DOM内容加载完成
            self.main_page.wait_for_load_state('domcontentloaded', timeout=5000)
            logger.debug("DOM内容加载完成")
            
            # 2. 等待网络空闲（所有网络请求完成）- 这是关键！
            try:
                self.main_page.wait_for_load_state('networkidle', timeout=8000)  # 增加到8秒
                logger.debug("网络请求全部完成")
            except Exception as e:
                logger.debug(f"网络空闲等待超时，可能有持续的请求: {str(e)}")
                # 即使网络不完全空闲，也继续后续检查
            
            # 3. 等待页面URL稳定（检测是否有页面跳转）
            current_url = self.main_page.url
            self.main_page.wait_for_timeout(1000)  # 等待1秒
            if self.main_page.url != current_url:
                logger.debug(f"检测到页面跳转: {current_url} -> {self.main_page.url}")
                # 如果发生跳转，再次等待新页面稳定
                self.main_page.wait_for_load_state('domcontentloaded', timeout=5000)
                try:
                    self.main_page.wait_for_load_state('networkidle', timeout=8000)
                    logger.debug("跳转后页面稳定")
                except Exception:
                    logger.debug("跳转后页面网络未完全空闲")
            
            # 4. 等待JavaScript执行完成和DOM变化稳定
            stable_count = 0
            max_checks = 10
            for i in range(max_checks):
                # 检查页面是否还在变化
                try:
                    is_stable = self.main_page.evaluate("""() => {
                        return new Promise((resolve) => {
                            let changeCount = 0;
                            const startTime = Date.now();
                            
                            // 监听DOM变化
                            const observer = new MutationObserver((mutations) => {
                                // 忽略录制相关的变化
                                const validMutations = mutations.filter(mutation => {
                                    const target = mutation.target;
                                    return !target.closest('#rpa-processing-overlay') && 
                                           !target.id?.includes('rpa-') &&
                                           !target.classList?.contains('rpa-recording');
                                });
                                
                                if (validMutations.length > 0) {
                                    changeCount += validMutations.length;
                                }
                            });
                            
                            observer.observe(document.body, {
                                childList: true,
                                subtree: true,
                                attributes: true,
                                attributeFilter: ['class', 'style', 'src', 'href']
                            });
                            
                            // 检查500ms内的变化
                            setTimeout(() => {
                                observer.disconnect();
                                // 如果变化很少（< 5个），认为页面稳定
                                const isStable = changeCount < 5;
                                resolve({
                                    stable: isStable,
                                    changes: changeCount,
                                    duration: Date.now() - startTime
                                });
                            }, 500);
                        });
                    }""")
                    
                    if is_stable['stable']:
                        stable_count += 1
                        logger.debug(f"页面稳定检查 {i+1}/{max_checks}: 稳定 (变化: {is_stable['changes']})")
                    else:
                        stable_count = 0
                        logger.debug(f"页面稳定检查 {i+1}/{max_checks}: 不稳定 (变化: {is_stable['changes']})")
                    
                    # 连续2次检查都稳定，认为页面稳定
                    if stable_count >= 2:
                        logger.debug("页面DOM变化已稳定")
                        break
                        
                except Exception as e:
                    logger.debug(f"页面稳定性检查失败: {str(e)}")
                    break
                
                # 每次检查间隔300ms
                self.main_page.wait_for_timeout(300)
            
            # 5. 确保所有动画和过渡效果完成
            try:
                animation_stable = self.main_page.evaluate("""() => {
                    return new Promise((resolve) => {
                        const animations = document.getAnimations();
                        if (animations.length === 0) {
                            resolve({stable: true, count: 0});
                            return;
                        }
                        
                        // 等待所有动画完成，最多等待3秒
                        const timeout = setTimeout(() => {
                            resolve({stable: false, count: animations.length});
                        }, 3000);
                        
                        Promise.all(animations.map(anim => anim.finished)).then(() => {
                            clearTimeout(timeout);
                            resolve({stable: true, count: animations.length});
                        }).catch(() => {
                            clearTimeout(timeout);
                            resolve({stable: false, count: animations.length});
                        });
                    });
                }""")
                
                if animation_stable['stable']:
                    logger.debug(f"所有动画已完成 (共{animation_stable['count']}个)")
                else:
                    logger.debug(f"动画未完全完成 (仍有{animation_stable['count']}个进行中)")
                    
            except Exception as e:
                logger.debug(f"动画检查失败: {str(e)}")
            
            # 6. 最终缓冲等待，确保所有异步操作完成
            self.main_page.wait_for_timeout(1500)  # 增加到1.5秒最终缓冲
            logger.debug("页面稳定性检查完成")
                
        except Exception as e:
            logger.debug(f"页面稳定性检测失败，继续保存: {str(e)}")
            # 即使检测失败，也要有基本的等待时间
            try:
                self.main_page.wait_for_timeout(2000)  # 基本等待2秒
            except:
                pass
    
    def _notify_step_processing_complete(self):
        """通知前端步骤处理完成，可以恢复用户操作"""
        try:
            self.main_page.evaluate("""() => {
                // 清除待处理的步骤
                window.pendingStepToProcess = null;
                
                // 触发处理完成事件
                const event = new CustomEvent('rpaProcessingComplete');
                document.dispatchEvent(event);
                
                // 如果录制器存在，直接隐藏遮罩
                if (window.rpaRecorder && window.rpaRecorder.hideProcessingOverlay) {
                    window.rpaRecorder.hideProcessingOverlay();
                }
            }""")
        except Exception as e:
            logger.debug(f"通知步骤处理完成失败: {str(e)}")
    
    def _get_step_description(self, action: Dict[str, Any]) -> str:
        """
        生成步骤描述
        """
        action_type = action.get('type', 'unknown')
        element_info = action.get('element_info', {})
        if action_type == 'manual_save':
            return element_info.get('text', '手动保存页面')
        if action_type == 'click':
            text = element_info.get('text', '').strip()
            if text and len(text) < 20:
                return f"点击_{text}"
            else:
                tag_name = action.get('tagName', '元素')
                return f"点击_{tag_name}"
        elif action_type == 'input':
            placeholder = element_info.get('placeholder', '')
            name = element_info.get('name', '')
            field_name = placeholder or name or '输入框'
            value = action.get('value', '')
            if value and len(value) < 20:
                return f"输入_{field_name}_{value}"
            else:
                return f"输入_{field_name}"
        elif action_type == 'select':
            return f"选择_{action.get('value', '选项')}"
        else:
            return f"{action_type}_操作"
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除不允许的字符"""
        import re
        # 移除或替换Windows不允许的字符，包括特殊符号
        filename = re.sub(r'[<>:"/\\|?*$!@#%^&()+=\[\]{}~`]', '_', filename)  # Windows不允许的字符和特殊符号
        filename = re.sub(r'[\x00-\x1f]', '_', filename)   # 控制字符
        filename = filename.replace(' ', '_')               # 空格替换为下划线
        filename = re.sub(r'_{2,}', '_', filename)         # 多个下划线合并为一个
        filename = filename.strip('_')                      # 移除首尾下划线
        
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename or "unnamed_step"
    
    def _check_step_events(self):
        """检查是否有新的步骤事件"""
        try:
            last_step = self.main_page.evaluate("window.lastRecordedStep")
            if last_step and last_step.get('stepNumber'):
                step_number = last_step['stepNumber']
                action = last_step['action']
                
                # 保存步骤快照
                self._save_step_snapshot(step_number, action, self.main_page)
                
                # 清除事件
                self.main_page.evaluate("window.lastRecordedStep = null")
                
        except Exception as e:
            logger.debug(f"检查步骤事件时出错: {str(e)}")
    
    def _move_temp_screenshots(self, package_dir: Path):
        """将临时截屏移动到最终包目录"""
        try:
            screenshots_dir = package_dir / "step_screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            
            if hasattr(self, 'temp_screenshots_dir') and self.temp_screenshots_dir.exists():
                # 移动所有文件
                for file_path in self.temp_screenshots_dir.iterdir():
                    if file_path.is_file():
                        new_path = screenshots_dir / file_path.name
                        file_path.rename(new_path)
                
                # 删除临时目录
                self.temp_screenshots_dir.rmdir()
                logger.info(f"步骤截屏已移动到: {screenshots_dir}")
                
        except Exception as e:
            logger.warning(f"移动步骤截屏失败: {str(e)}")
    
    def _save_final_screenshot(self, package_dir: Path):
        """保存最终状态截图（不包含遮罩层）"""
        screenshots_dir = package_dir / "step_screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        
        # 临时隐藏遮罩层
        overlay_hidden = self.main_page.evaluate("""() => {
            const rpaOverlay = document.getElementById('rpa-processing-overlay');
            if (rpaOverlay) {
                rpaOverlay.style.display = 'none';
                return true;
            }
            return false;
        }""")
        
        # 短暂等待确保遮罩隐藏生效
        self.main_page.wait_for_timeout(200)
        
        final_screenshot = screenshots_dir / "final_state.png"
        self.main_page.screenshot(path=str(final_screenshot), full_page=True)
        
        # 恢复遮罩层显示（如果需要的话）
        if overlay_hidden:
            self.main_page.evaluate("""() => {
                const rpaOverlay = document.getElementById('rpa-processing-overlay');
                if (rpaOverlay) {
                    rpaOverlay.style.display = 'flex';
                }
            }""")
    
    def _clean_step_html(self, html_content: str) -> str:
        """
        清理步骤HTML内容，移除多余元素但保留CSS样式
        :param html_content: 原始HTML内容
        :return: 清理后的HTML内容
        """
        try:
            import re
            
            # 1. 移除Vue的占位元素（data-inline-*）- 但不影响我们的CSS内联标识
            html_content = re.sub(
                r'<div[^>]*data-inline-\d+[^>]*style="[^"]*position:\s*absolute[^"]*"[^>]*></div>',
                '', html_content, flags=re.IGNORECASE
            )
            
            # 2. 移除空的tabindex占位元素
            html_content = re.sub(
                r'<div[^>]*tabindex="0"[^>]*role="presentation"[^>]*style="[^"]*width:\s*0px[^"]*"[^>]*></div>',
                '', html_content, flags=re.IGNORECASE
            )
            
            # 3. 清理多余的空白和换行（但保留CSS格式）
            html_content = re.sub(r'\n\s*\n\s*\n', '\n\n', html_content)
            
            # 注意：不再移除style标签，因为现在它们包含重要的内联CSS
            
            return html_content
            
        except Exception as e:
            logger.warning(f"HTML清理失败: {str(e)}")
            return html_content 
    
    def check_and_process_pending_steps(self):
        """检查并处理所有页面中的待处理步骤（主线程安全）"""
        if not self.is_recording:
            return
        
        try:
            # 检查主页面
            if not self.main_page.is_closed():
                self._check_pending_step_for_page(self.main_page)
            
            # 检查所有弹出页面
            for page_id, page in self.recording_pages.items():
                if not page.is_closed():
                    self._check_pending_step_for_page(page)
                    
        except Exception as e:
            logger.debug(f"检查待处理步骤时出错: {str(e)}")
    
    def _check_pending_step_for_page(self, page: Page):
        """检查特定页面的待处理步骤"""
        try:
            pending_step = page.evaluate("window.pendingStepToProcess")
            if pending_step and pending_step.get('stepNumber') and pending_step.get('action'):
                step_number = pending_step['stepNumber']
                action = pending_step['action']
                
                logger.debug(f"发现待处理步骤: {step_number} - {action.get('type', 'unknown')}")
                
                # 直接处理步骤保存
                self._save_step_snapshot(step_number, action, page)
                
                # 清除待处理的步骤
                page.evaluate("window.pendingStepToProcess = null")
                
        except Exception as e:
            logger.debug(f"检查页面待处理步骤时出错: {str(e)}") 