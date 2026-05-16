import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.sync_api import Page
import mimetypes
import json
from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config

class PageHelper:
    def __init__(self, page: Page):
        self.page = page
        self.config = config.get_config()
        # 设置保存目录，使用与截图相同的目录
        self.save_dir = Path(self.config["screenshot"]["save_dir"])
        self.save_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"页面状态保存目录: {self.save_dir}")

    def _get_resource_filename(self, url: str, resource_type: str) -> str:
        """
        根据URL和资源类型生成文件名
        """
        filename = url.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]
            
        # 确保文件名有正确的扩展名
        if not os.path.splitext(filename)[1]:
            ext = mimetypes.guess_extension(resource_type)
            if ext:
                filename += ext
                
        return filename

    def save_page_for_rpa(self, filename: Optional[str] = None) -> str:
        """
        为RPA开发保存页面完整信息，包括DOM结构、样式、截图和元素信息
        :param filename: 保存的文件名，如果不指定则使用时间戳
        :return: 保存的文件路径
        """
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"rpa_page_{timestamp}"
            
            # 创建保存目录
            save_dir = self.save_dir / filename
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. 等待页面稳定（等待所有网络请求完成）
            self.page.wait_for_load_state('networkidle')
            
            # 2. 获取完整的DOM内容（包括动态生成的）
            content = self.page.content()
            
            # 3. 获取页面元素信息用于RPA开发参考
            elements_info = self._extract_elements_info()
            
            # 4. 保存页面截图
            screenshot_path = save_dir / f"{filename}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)
            
            # 5. 获取并保存CSS资源
            css_resources = self.page.evaluate("""() => {
                const resources = [];
                const links = document.getElementsByTagName('link');
                for (const link of links) {
                    if (link.href && (link.rel === 'stylesheet' || link.type === 'text/css')) {
                        resources.push({url: link.href});
                    }
                }
                return resources;
            }""")
            
            # 保存CSS文件
            css_dir = save_dir / "css"
            css_dir.mkdir(exist_ok=True)
            
            for css in css_resources:
                try:
                    response = self.page.goto(css['url'])
                    if response and response.ok:
                        css_content = response.body()
                        css_filename = self._get_resource_filename(css['url'], 'css')
                        css_path = css_dir / css_filename
                        
                        with open(css_path, 'wb') as f:
                            f.write(css_content)
                        
                        # 更新HTML中的CSS路径
                        content = content.replace(css['url'], f"css/{css_filename}")
                        content = content.replace(f"/css/{css_filename}", f"css/{css_filename}")
                except Exception as e:
                    logger.warning(f"保存CSS文件失败 {css['url']}: {str(e)}")
            
            # 6. 保存HTML文件
            html_path = save_dir / f"{filename}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 7. 保存元素信息JSON文件
            elements_path = save_dir / f"{filename}_elements.json"
            with open(elements_path, 'w', encoding='utf-8') as f:
                json.dump(elements_info, f, ensure_ascii=False, indent=2)
            
            # 8. 创建RPA开发说明文件
            readme_path = save_dir / "README.md"
            self._create_rpa_readme(readme_path, filename, elements_info)
            
            logger.info(f"RPA页面分析文件已保存到: {save_dir}")
            return str(html_path)
            
        except Exception as e:
            error_msg = f"保存RPA页面失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def _extract_elements_info(self) -> dict:
        """
        提取页面元素信息，用于RPA开发参考
        """
        try:
            elements_info = self.page.evaluate("""() => {
                const elements = [];
                
                // 获取所有可交互元素
                const interactiveSelectors = [
                    'button', 'input', 'select', 'textarea', 'a[href]',
                    '[onclick]', '[role="button"]', '[tabindex]',
                    'form', 'table', '[data-*]', '[id]', '[class]'
                ];
                
                const allElements = document.querySelectorAll(interactiveSelectors.join(','));
                
                allElements.forEach((element, index) => {
                    if (element.offsetParent !== null || element.tagName === 'INPUT') { // 只处理可见元素
                        const rect = element.getBoundingClientRect();
                        const elementInfo = {
                            index: index,
                            tagName: element.tagName,
                            id: element.id || '',
                            className: element.className || '',
                            text: element.textContent?.trim().substring(0, 100) || '',
                            type: element.type || '',
                            name: element.name || '',
                            value: element.value || '',
                            href: element.href || '',
                            placeholder: element.placeholder || '',
                            title: element.title || '',
                            dataAttributes: {},
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            },
                            xpath: '',
                            cssSelector: ''
                        };
                        
                        // 获取data-*属性
                        for (let attr of element.attributes) {
                            if (attr.name.startsWith('data-')) {
                                elementInfo.dataAttributes[attr.name] = attr.value;
                            }
                        }
                        
                        // 生成简单的CSS选择器建议
                        if (element.id) {
                            elementInfo.cssSelector = `#${element.id}`;
                        } else if (element.className) {
                            const classes = element.className.split(' ').filter(c => c.trim());
                            if (classes.length > 0) {
                                elementInfo.cssSelector = `.${classes.join('.')}`;
                            }
                        }
                        
                        elements.push(elementInfo);
                    }
                });
                
                return {
                    url: window.location.href,
                    title: document.title,
                    timestamp: new Date().toISOString(),
                    elements: elements
                };
            }""")
            
            return elements_info
            
        except Exception as e:
            logger.error(f"提取元素信息失败: {str(e)}")
            return {"error": str(e), "elements": []}

    def _create_rpa_readme(self, readme_path: Path, filename: str, elements_info: dict):
        """
        创建RPA开发说明文件
        """
        try:
            readme_content = f"""# RPA页面分析报告

## 页面信息
- **URL**: {elements_info.get('url', '未知')}
- **标题**: {elements_info.get('title', '未知')}
- **保存时间**: {elements_info.get('timestamp', '未知')}
- **可交互元素数量**: {len(elements_info.get('elements', []))}

## 文件说明
- `{filename}.html` - 完整的页面HTML文件
- `{filename}.png` - 页面完整截图
- `{filename}_elements.json` - 页面元素详细信息
- `css/` - 页面样式文件目录

## 主要可交互元素

| 序号 | 元素类型 | ID | Class | 文本内容 | 建议选择器 |
|------|----------|-------|-------|----------|------------|
"""
            
            elements = elements_info.get('elements', [])
            for i, element in enumerate(elements[:20]):  # 只显示前20个元素
                readme_content += f"| {i+1} | {element.get('tagName', '')} | {element.get('id', '')} | {element.get('className', '')[:30]}... | {element.get('text', '')[:30]}... | {element.get('cssSelector', '')} |\n"
            
            if len(elements) > 20:
                readme_content += f"\n> 注意: 还有 {len(elements) - 20} 个元素未显示，请查看 {filename}_elements.json 文件获取完整信息。\n"
            
            readme_content += f"""

## RPA开发建议

1. **优先使用稳定的定位器**：
   - ID选择器（如果元素有唯一ID）
   - name属性（适用于表单元素）
   - 稳定的class名称

2. **备用定位策略**：
   - XPath（用于复杂的层级关系）
   - CSS选择器组合
   - 文本内容匹配（用于按钮和链接）

3. **注意事项**：
   - 页面可能存在动态加载内容，需要添加等待逻辑
   - 某些元素可能需要滚动到视图中才能交互
   - 建议在实际环境中验证所有定位器的有效性

## 开发步骤建议

1. 在浏览器中打开 `{filename}.html` 查看页面结构
2. 参考 `{filename}.png` 截图了解页面布局
3. 使用 `{filename}_elements.json` 中的元素信息编写定位器
4. 在实际环境中测试和验证RPA脚本
"""
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
                
        except Exception as e:
            logger.error(f"创建README文件失败: {str(e)}")

    def save_page(self, filepath:[str]=None) -> str:
        """
        保存当前页面为HTML文件，包括相关的CSS文件（原有方法保持兼容）
        :param filename: 保存的文件名，如果不指定则使用时间戳
        :return: 保存的文件路径
        """
        try:
            if not filepath.endswith('.html'):
                filepath += '.html'
            html_path = filepath
            
            # 获取页面内容
            content = self.page.content()
            
            # 获取所有CSS资源
            css_resources = self.page.evaluate("""() => {
                const resources = [];
                const links = document.getElementsByTagName('link');
                for (const link of links) {
                    if (link.href && (link.rel === 'stylesheet' || link.type === 'text/css')) {
                        resources.push({url: link.href});
                    }
                }
                return resources;
            }""")
            
            # 创建css目录
            css_dir = Path(filepath).parent / "css"
            css_dir.mkdir(exist_ok=True)
            
            # 下载并保存CSS文件
            for css in css_resources:
                try:
                    response = self.page.goto(css['url'])
                    if response and response.ok:
                        css_content = response.body()
                        css_filename = self._get_resource_filename(css['url'], 'css')
                        css_path = css_dir / css_filename
                        
                        with open(css_path, 'wb') as f:
                            f.write(css_content)
                        
                        # 更新HTML中的CSS路径，使用相对路径
                        content = content.replace(css['url'], f"css/{css_filename}")
                        # 处理可能的绝对路径引用
                        content = content.replace(f"/css/{css_filename}", f"css/{css_filename}")
                except Exception as e:
                    logger.warning(f"保存CSS文件失败 {css['url']}: {str(e)}")
            
            # 保存HTML文件
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"错误页面已保存到: {html_path}")
            return str(html_path)
            
        except Exception as e:
            error_msg = f"保存页面失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def start_operation_recording(self) -> str:
        """
        开始录制用户操作过程，用于RPA开发
        :return: 录制会话ID
        """
        try:
            import uuid
            session_id = str(uuid.uuid4())
            
            # 注入录制脚本
            self.page.evaluate(f"""
                window.rpaRecorder = {{
                    sessionId: '{session_id}',
                    actions: [],
                    startTime: Date.now(),
                    isRecording: true,
                    
                    generateSelector: function(element) {{
                        // 生成多种选择器选项
                        const selectors = [];
                        
                        // ID选择器
                        if (element.id) {{
                            selectors.push({{type: 'id', value: `#${{element.id}}`, priority: 1}});
                        }}
                        
                        // Name属性
                        if (element.name) {{
                            selectors.push({{type: 'name', value: `[name="${{element.name}}"]`, priority: 2}});
                        }}
                        
                        // Class选择器（过滤常见的动态class）
                        if (element.className) {{
                            const stableClasses = element.className.split(' ')
                                .filter(cls => !cls.match(/^(active|selected|focus|hover|btn-\\d+)$/));
                            if (stableClasses.length > 0) {{
                                selectors.push({{type: 'class', value: `.${{stableClasses.join('.')}}`, priority: 3}});
                            }}
                        }}
                        
                        // 文本内容选择器
                        const textContent = element.textContent?.trim();
                        if (textContent && textContent.length < 50) {{
                            selectors.push({{type: 'text', value: textContent, priority: 4}});
                        }}
                        
                        // XPath
                        const xpath = this.getXPath(element);
                        selectors.push({{type: 'xpath', value: xpath, priority: 5}});
                        
                        return selectors.sort((a, b) => a.priority - b.priority);
                    }},
                    
                    getXPath: function(element) {{
                        if (element.id !== '') {{
                            return `//*[@id="${{element.id}}"]`;
                        }}
                        if (element === document.body) {{
                            return '/html/body';
                        }}
                        
                        let ix = 0;
                        const siblings = element.parentNode.childNodes;
                        for (let i = 0; i < siblings.length; i++) {{
                            const sibling = siblings[i];
                            if (sibling === element) {{
                                return this.getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }}
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {{
                                ix++;
                            }}
                        }}
                    }},
                    
                    recordAction: function(type, element, value = null, additionalData = {{}}) {{
                        if (!this.isRecording) return;
                        
                        const rect = element.getBoundingClientRect();
                        const action = {{
                            id: this.actions.length + 1,
                            timestamp: Date.now() - this.startTime,
                            type: type,
                            tagName: element.tagName,
                            selectors: this.generateSelector(element),
                            value: value,
                            position: {{
                                x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2)
                            }},
                            element_info: {{
                                id: element.id || '',
                                className: element.className || '',
                                name: element.name || '',
                                type: element.type || '',
                                placeholder: element.placeholder || '',
                                text: element.textContent?.trim().substring(0, 100) || ''
                            }},
                            page_info: {{
                                url: window.location.href,
                                title: document.title,
                                viewport: {{
                                    width: window.innerWidth,
                                    height: window.innerHeight
                                }}
                            }},
                            ...additionalData
                        }};
                        
                        this.actions.push(action);
                        console.log('RPA Action recorded:', action);
                    }},
                    
                    stopRecording: function() {{
                        this.isRecording = false;
                        return this.actions;
                    }}
                }};
                
                // 事件监听器
                document.addEventListener('click', (e) => {{
                    window.rpaRecorder.recordAction('click', e.target);
                }}, true);
                
                document.addEventListener('input', (e) => {{
                    window.rpaRecorder.recordAction('input', e.target, e.target.value);
                }}, true);
                
                document.addEventListener('change', (e) => {{
                    if (e.target.type === 'select-one' || e.target.type === 'select-multiple') {{
                        const selectedText = e.target.options[e.target.selectedIndex]?.text;
                        window.rpaRecorder.recordAction('select', e.target, e.target.value, {{
                            selectedText: selectedText
                        }});
                    }}
                }}, true);
                
                document.addEventListener('keydown', (e) => {{
                    if (e.key === 'Enter' || e.key === 'Tab') {{
                        window.rpaRecorder.recordAction('keypress', e.target, e.key);
                    }}
                }}, true);
                
                // 滚动事件（节流处理）
                let scrollTimeout;
                document.addEventListener('scroll', (e) => {{
                    clearTimeout(scrollTimeout);
                    scrollTimeout = setTimeout(() => {{
                        window.rpaRecorder.recordAction('scroll', document.documentElement, null, {{
                            scrollTop: window.pageYOffset,
                            scrollLeft: window.pageXOffset
                        }});
                    }}, 500);
                }}, true);
                
                console.log('RPA Recording started. Session ID: {session_id}');
            """)
            
            logger.info(f"开始RPA操作录制，会话ID: {session_id}")
            return session_id
            
        except Exception as e:
            error_msg = f"启动操作录制失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def stop_recording_and_generate_package(self, session_id: str, package_name: str) -> str:
        """
        停止录制并生成RPA开发包
        :param session_id: 录制会话ID
        :param package_name: 用户输入的包名称（必须提供）
        :return: 生成的包路径
        """
        try:
            # 停止录制并获取动作数据
            actions = self.page.evaluate("window.rpaRecorder ? window.rpaRecorder.stopRecording() : []")
            
            if not actions:
                raise Exception("没有录制到任何操作")
            
            # 清理包名（移除特殊字符）
            import re
            clean_package_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', package_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_package_name = f"{clean_package_name}_{timestamp}"
            
            # 创建包目录
            package_dir = self.save_dir / final_package_name
            package_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. 保存操作记录
            recording_path = package_dir / "recording.json"
            with open(recording_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_id": session_id,
                    "package_name": package_name,
                    "total_actions": len(actions),
                    "duration_ms": actions[-1]["timestamp"] if actions else 0,
                    "actions": actions
                }, f, ensure_ascii=False, indent=2)
            
            # 2. 保存完整页面（用于开发人员分析页面结构）
            self._save_complete_page_for_development(package_dir, final_package_name)
            
            # 3. 为每个关键步骤截图
            screenshots_dir = package_dir / "step_screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            
            # 截取当前最终状态
            final_screenshot = screenshots_dir / "final_state.png"
            self.page.screenshot(path=str(final_screenshot), full_page=True)
            
            # 4. 生成Playwright代码
            code_dir = package_dir / "generated_code"
            code_dir.mkdir(exist_ok=True)
            
            playwright_code = self._generate_playwright_code(actions)
            with open(code_dir / "playwright_automation.py", 'w', encoding='utf-8') as f:
                f.write(playwright_code)
            
            # 5. 生成详细的操作步骤文档
            steps_doc = self._generate_detailed_steps_document(actions, package_name)
            with open(code_dir / "操作步骤说明.md", 'w', encoding='utf-8') as f:
                f.write(steps_doc)
            
            # 6. 生成开发指南
            guide_content = self._generate_development_guide(actions, package_name)
            with open(package_dir / "RPA开发指南.md", 'w', encoding='utf-8') as f:
                f.write(guide_content)
            
            logger.info(f"RPA开发包已生成: {package_dir}")
            return str(package_dir)
            
        except Exception as e:
            error_msg = f"生成RPA开发包失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _generate_playwright_code(self, actions: list) -> str:
        """生成Playwright脚本代码"""
        code = '''"""
自动生成的Playwright RPA脚本
注意：此脚本需要根据实际环境进行调整和测试
"""

from playwright.sync_api import sync_playwright
import time

def run_rpa_automation():
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)  # 设置为True可无头运行
        page = browser.new_page()
        
        try:
'''
        
        current_url = None
        for i, action in enumerate(actions):
            if action['page_info']['url'] != current_url:
                current_url = action['page_info']['url']
                code += f'''
            # 导航到页面
            page.goto("{current_url}")
            page.wait_for_load_state('networkidle')
'''
            
            primary_selector = action['selectors'][0]['value'] if action['selectors'] else None
            
            if action['type'] == 'click':
                code += f'''
            # 步骤 {i+1}: 点击 {action['element_info']['text'][:30]}...
            page.click("{primary_selector}")
            time.sleep(1)  # 等待响应
'''
            elif action['type'] == 'input':
                code += f'''
            # 步骤 {i+1}: 输入文本
            page.fill("{primary_selector}", "{action['value']}")
'''
            elif action['type'] == 'select':
                code += f'''
            # 步骤 {i+1}: 选择选项
            page.select_option("{primary_selector}", "{action['value']}")
'''
        
        code += '''
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_rpa_automation()
'''
        return code
    

    

    
    def _generate_development_guide(self, actions: list, package_name: str) -> str:
        """生成开发指南"""
        guide = f"""# RPA开发指南 - {package_name}

## 项目概述

本包包含了从用户操作录制中提取的完整RPA开发资料，包括：
- 用户操作的完整记录和分析
- 自动生成的Playwright执行代码
- 页面结构完整分析
- 详细的开发建议和最佳实践

## 文件结构

```
{package_name}/
├── recording.json                      # 完整操作记录
├── page_analysis/                      # 页面结构分析
│   ├── complete_page.html             # 完整页面HTML
│   ├── full_page_screenshot.png       # 页面完整截图
│   ├── elements_analysis.json         # 所有元素详细信息
│   └── elements_analysis_report.md    # 元素分析报告
├── step_screenshots/                   # 关键步骤截图
│   └── final_state.png               # 最终状态截图
├── generated_code/                     # 自动生成代码
│   ├── playwright_automation.py       # Playwright自动化脚本
│   └── 操作步骤说明.md                # 详细步骤文档
└── RPA开发指南.md                     # 本文档
```

## 操作统计

- **总操作数**: {len(actions)}
- **主要操作类型**: {', '.join(set(action['type'] for action in actions))}
- **涉及页面数**: {len(set(action['page_info']['url'] for action in actions))}

## 核心优势

### 🎯 **操作录制精确性**
- 记录用户的完整操作序列
- 捕获每个交互的详细信息
- 提供多种备选定位器策略

### 📊 **页面结构深度分析**
- 完整HTML源码保存（包含动态内容）
- 所有可交互元素的详细分析
- 定位器稳定性评估和建议

### 🔧 **即用代码生成**
- 生成可直接运行的Playwright脚本
- 包含错误处理和等待逻辑
- 详细的代码注释和说明

## 开发建议

### 1. 定位器选择策略（按优先级）
1. **ID选择器** `#element_id` - 最稳定，优先使用
2. **Name属性** `[name="field_name"]` - 适用于表单元素
3. **稳定的Class** `.stable-class` - 避免动态生成的class
4. **Data属性** `[data-testid="value"]` - 通常比较稳定
5. **文本内容** `text="按钮文本"` - 适用于按钮和链接
6. **XPath** - 最后选择，维护成本高

### 2. 稳定性优化技巧
- 📋 **使用页面分析**: 参考 `page_analysis/` 中的元素分析报告
- 🔍 **验证选择器**: 在实际环境中测试所有定位器
- 🏗️ **层级定位**: 对于无稳定属性的元素，使用父元素+相对位置
- 💡 **智能等待**: 使用 `wait_for_selector()` 而不是固定延时

### 3. 错误处理机制
```python
# 示例：带重试的元素定位
def safe_click(page, selector, max_retries=3):
    for attempt in range(max_retries):
        try:
            page.wait_for_selector(selector, timeout=5000)
            page.click(selector)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)
    return False
```

### 4. 数据处理建议
- 🔄 **参数化**: 将固定值改为可配置参数
- ✅ **验证**: 添加数据验证逻辑
- 📝 **日志**: 记录详细执行日志
- 💾 **结果保存**: 保存执行结果和状态

## 快速开始步骤

1. **环境准备**
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **代码测试**
   - 打开 `generated_code/playwright_automation.py`
   - 根据实际环境调整代码中的选择器
   - 运行并测试每个步骤

3. **稳定性优化**
   - 查看 `page_analysis/elements_analysis_report.md`
   - 根据建议优化定位器选择
   - 添加必要的等待逻辑

4. **生产部署**
   - 添加异常处理机制
   - 配置日志记录
   - 进行端到端测试

## 文件使用指南

| 文件 | 用途 | 重要程度 |
|------|------|----------|
| `playwright_automation.py` | 可直接运行的自动化脚本 | ⭐⭐⭐⭐⭐ |
| `操作步骤说明.md` | 详细步骤分析和代码示例 | ⭐⭐⭐⭐⭐ |
| `elements_analysis_report.md` | 页面元素分析，优化定位器 | ⭐⭐⭐⭐ |
| `complete_page.html` | 完整页面HTML，结构分析 | ⭐⭐⭐ |
| `recording.json` | 原始录制数据，深度调试 | ⭐⭐ |

## 注意事项

⚠️ **重要提醒**：
- 生成的代码是基础版本，需要根据实际环境调整
- 页面结构变化可能导致选择器失效，需要定期维护
- 建议在测试环境充分验证后再部署到生产环境
- 对于关键业务流程，建议添加详细的监控和告警

## 技术支持

🔧 **开发过程中遇到问题时的排查顺序**：
1. 查看 `操作步骤说明.md` 中的详细步骤和代码示例
2. 参考 `elements_analysis_report.md` 中的定位器建议
3. 检查 `recording.json` 中的原始操作数据
4. 使用 `complete_page.html` 分析页面结构变化

🎯 **最佳实践**：
- 优先使用本包提供的分析数据而不是手动分析
- 定期更新录制包以适应页面变化
- 将稳定的定位器配置化管理
"""
        
        return guide

    def _save_complete_page_for_development(self, package_dir: Path, package_name: str):
        """
        保存完整页面状态供开发人员分析页面结构
        """
        try:
            # 等待页面稳定
            self.page.wait_for_load_state('networkidle')
            
            # 创建页面分析目录
            page_analysis_dir = package_dir / "page_analysis"
            page_analysis_dir.mkdir(exist_ok=True)
            
            # 1. 保存完整HTML（包含所有动态内容）
            html_content = self.page.content()
            with open(page_analysis_dir / "complete_page.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 2. 保存页面截图（全页面）
            self.page.screenshot(path=str(page_analysis_dir / "full_page_screenshot.png"), full_page=True)
            
            # 3. 提取并保存所有可交互元素信息
            elements_info = self.page.evaluate("""() => {
                const elements = [];
                const interactiveSelectors = [
                    'button', 'input', 'select', 'textarea', 'a[href]',
                    '[onclick]', '[role="button"]', '[tabindex]',
                    'form', '[data-*]', '[id]', '[class*="btn"]', '[class*="button"]'
                ];
                
                const allElements = document.querySelectorAll(interactiveSelectors.join(','));
                
                allElements.forEach((element, index) => {
                    if (element.offsetParent !== null || element.tagName === 'INPUT') {
                        const rect = element.getBoundingClientRect();
                        const elementInfo = {
                            index: index + 1,
                            tagName: element.tagName,
                            id: element.id || '',
                            className: element.className || '',
                            name: element.name || '',
                            type: element.type || '',
                            text: element.textContent?.trim().substring(0, 200) || '',
                            value: element.value || '',
                            placeholder: element.placeholder || '',
                            href: element.href || '',
                            title: element.title || '',
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            },
                            selectors: {
                                id: element.id ? `#${element.id}` : '',
                                name: element.name ? `[name="${element.name}"]` : '',
                                class: element.className ? `.${element.className.split(' ').join('.')}` : '',
                                css: element.id ? `#${element.id}` : 
                                     element.className ? `.${element.className.split(' ')[0]}` : 
                                     element.tagName.toLowerCase()
                            },
                            dataAttributes: {}
                        };
                        
                        // 收集data-*属性
                        for (let attr of element.attributes) {
                            if (attr.name.startsWith('data-')) {
                                elementInfo.dataAttributes[attr.name] = attr.value;
                            }
                        }
                        
                        elements.push(elementInfo);
                    }
                });
                
                return {
                    url: window.location.href,
                    title: document.title,
                    timestamp: new Date().toISOString(),
                    total_elements: elements.length,
                    elements: elements
                };
            }""")
            
            # 保存元素分析结果
            with open(page_analysis_dir / "elements_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(elements_info, f, ensure_ascii=False, indent=2)
            
            # 4. 生成元素分析报告
            self._generate_elements_analysis_report(page_analysis_dir, elements_info)
            
            logger.info(f"页面结构分析文件已保存到: {page_analysis_dir}")
            
        except Exception as e:
            logger.error(f"保存页面结构分析失败: {str(e)}")

    def _generate_elements_analysis_report(self, analysis_dir: Path, elements_info: dict):
        """生成元素分析报告"""
        try:
            report_content = f"""# 页面元素分析报告

## 页面基本信息
- **URL**: {elements_info.get('url', '未知')}
- **标题**: {elements_info.get('title', '未知')}
- **分析时间**: {elements_info.get('timestamp', '未知')}
- **可交互元素总数**: {elements_info.get('total_elements', 0)}

## 重要提示
本报告用于辅助RPA开发人员分析页面结构，提升定位器(locator)的稳定性。

## 建议的定位器选择策略
1. **ID选择器** - 最高优先级，最稳定
2. **Name属性** - 适用于表单元素
3. **稳定的Class名** - 避免动态生成的class
4. **Data属性** - 通常比较稳定
5. **文本内容** - 适用于按钮和链接
6. **XPath** - 最后选择，维护成本高

## 可交互元素详情

| 序号 | 元素类型 | ID | Name | 主要Class | 文本内容 | 推荐选择器 |
|------|----------|----|----|----------|----------|------------|
"""
            
            elements = elements_info.get('elements', [])
            for element in elements[:50]:  # 限制显示前50个元素
                # 确定推荐选择器
                recommended_selector = ""
                if element['selectors']['id']:
                    recommended_selector = element['selectors']['id']
                elif element['selectors']['name']:
                    recommended_selector = element['selectors']['name']
                elif element['selectors']['class']:
                    recommended_selector = element['selectors']['class']
                else:
                    recommended_selector = element['selectors']['css']
                
                # 格式化显示内容
                main_class = element['className'].split(' ')[0] if element['className'] else ''
                text_preview = element['text'][:30] + '...' if len(element['text']) > 30 else element['text']
                
                report_content += f"| {element['index']} | {element['tagName']} | {element['id']} | {element['name']} | {main_class} | {text_preview} | `{recommended_selector}` |\n"
            
            if len(elements) > 50:
                report_content += f"\n> 注意: 还有 {len(elements) - 50} 个元素未在此表格中显示。完整信息请查看 `elements_analysis.json` 文件。\n"
            
            report_content += """

## 页面分析文件说明
- `complete_page.html` - 完整的页面HTML源码，包含所有动态内容
- `full_page_screenshot.png` - 页面完整截图
- `elements_analysis.json` - 所有可交互元素的详细信息
- `elements_analysis_report.md` - 本分析报告

## RPA开发建议

### 定位器稳定性优化
1. **优先使用ID**: 如果元素有ID且不是动态生成的，优先使用
2. **验证Class稳定性**: 检查class名是否包含版本号、随机字符等
3. **考虑层级关系**: 对于没有稳定属性的元素，考虑使用父元素+相对位置
4. **文本定位的注意事项**: 确保文本内容不会因语言、数据变化而改变

### 页面加载处理
- 添加适当的等待逻辑，确保动态内容加载完成
- 对于异步加载的内容，使用 `wait_for_selector()` 等方法
- 考虑页面滚动对元素可见性的影响

### 错误处理
- 为每个关键操作添加异常处理
- 提供备用的定位策略
- 记录详细的执行日志便于调试
"""
            
            with open(analysis_dir / "elements_analysis_report.md", 'w', encoding='utf-8') as f:
                f.write(report_content)
                
        except Exception as e:
            logger.error(f"生成元素分析报告失败: {str(e)}")

    def _generate_detailed_steps_document(self, actions: list, package_name: str) -> str:
        """生成详细的操作步骤文档"""
        document = f"""# {package_name} - 详细操作步骤

## 录制信息
- **流程名称**: {package_name}
- **操作步骤数**: {len(actions)}
- **录制时长**: {actions[-1]['timestamp'] if actions else 0} 毫秒

## 操作流程图
```
开始 → """
        
        # 生成简化的流程图
        step_types = [action['type'] for action in actions]
        unique_steps = []
        for step in step_types:
            if not unique_steps or unique_steps[-1] != step:
                unique_steps.append(step)
        
        document += " → ".join(unique_steps) + " → 结束"
        document += "\n```\n\n## 详细步骤说明\n\n"
        
        current_url = None
        for i, action in enumerate(actions, 1):
            # 检查是否切换了页面
            if action['page_info']['url'] != current_url:
                current_url = action['page_info']['url']
                document += f"\n### 📋 页面: {action['page_info']['title']}\n"
                document += f"**URL**: {current_url}\n\n"
            
            # 步骤详情
            document += f"#### 步骤 {i}: {action['type'].upper()}\n\n"
            
            # 操作描述
            action_desc = self._get_action_description(action)
            document += f"**操作描述**: {action_desc}\n\n"
            
            # 目标元素信息
            document += "**目标元素**:\n"
            document += f"- 标签: `{action['tagName']}`\n"
            if action['element_info']['id']:
                document += f"- ID: `{action['element_info']['id']}`\n"
            if action['element_info']['name']:
                document += f"- Name: `{action['element_info']['name']}`\n"
            if action['element_info']['className']:
                document += f"- Class: `{action['element_info']['className']}`\n"
            if action['element_info']['text']:
                document += f"- 文本内容: \"{action['element_info']['text'][:100]}...\"\n"
            
            # 推荐的定位器
            if action['selectors']:
                document += "\n**推荐定位器** (按优先级排序):\n"
                for j, selector in enumerate(action['selectors'][:3], 1):
                    document += f"{j}. `{selector['value']}` ({selector['type']})\n"
            
            # 操作值
            if action.get('value'):
                document += f"\n**操作值**: `{action['value']}`\n"
            
            # 代码示例
            document += f"\n**Playwright代码示例**:\n```python\n"
            if action['type'] == 'click':
                primary_selector = action['selectors'][0]['value'] if action['selectors'] else 'selector'
                document += f"page.click('{primary_selector}')\n"
            elif action['type'] == 'input':
                primary_selector = action['selectors'][0]['value'] if action['selectors'] else 'selector'
                document += f"page.fill('{primary_selector}', '{action['value']}')\n"
            elif action['type'] == 'select':
                primary_selector = action['selectors'][0]['value'] if action['selectors'] else 'selector'
                document += f"page.select_option('{primary_selector}', '{action['value']}')\n"
            document += "```\n\n"
            
            document += "---\n\n"
        
        document += """## 注意事项

1. **选择器稳定性**: 建议在实际环境中测试所有选择器的有效性
2. **等待策略**: 添加适当的等待逻辑，特别是对于动态加载的内容
3. **错误处理**: 为关键步骤添加异常处理机制
4. **数据参数化**: 考虑将固定值改为可配置参数

## 开发提示

- 参考 `page_analysis/` 目录中的页面结构分析
- 使用 `elements_analysis.json` 获取完整的元素信息
- 查看完整页面截图了解整体布局
"""
        
        return document

    def _get_action_description(self, action: dict) -> str:
        """获取操作的中文描述"""
        if action['type'] == 'click':
            if action['element_info']['text']:
                return f"点击 \"{action['element_info']['text'][:30]}\" 按钮/链接"
            else:
                return f"点击 {action['tagName']} 元素"
        elif action['type'] == 'input':
            field_name = action['element_info']['placeholder'] or action['element_info']['name'] or '输入框'
            return f"在 \"{field_name}\" 中输入: {action['value']}"
        elif action['type'] == 'select':
            return f"在下拉框中选择: {action.get('selectedText', action['value'])}"
        elif action['type'] == 'keypress':
            return f"按下 {action['value']} 键"
        elif action['type'] == 'scroll':
            return f"页面滚动到位置: ({action.get('scrollLeft', 0)}, {action.get('scrollTop', 0)})"
        else:
            return f"执行 {action['type']} 操作"