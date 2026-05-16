"""
页面分析器

负责分析页面结构，提取所有可交互元素信息，为RPA开发提供详细的页面分析报告
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from playwright.sync_api import Page

from rpa_framework.utils.log import logger


class PageAnalyzer:
    """页面结构分析器"""
    
    def __init__(self, page: Page):
        """
        初始化页面分析器
        :param page: Playwright页面对象
        """
        self.page = page
        logger.debug("页面分析器初始化完成")
    
    def analyze_page(self) -> Dict[str, Any]:
        """
        分析当前页面结构
        :return: 页面分析结果
        """
        try:
            # 等待页面稳定
            self.page.wait_for_load_state('networkidle')
            
            logger.info("开始分析页面结构...")
            
            # 获取页面基本信息
            page_info = self._get_page_info()
            
            # 获取所有可交互元素
            elements_info = self._extract_elements_info()
            
            # 分析页面表单
            forms_info = self._analyze_forms()
            
            # 分析链接和导航
            links_info = self._analyze_links()
            
            analysis_result = {
                "page_info": page_info,
                "elements": elements_info,
                "forms": forms_info,
                "links": links_info,
                "analysis_time": datetime.now().isoformat(),
                "total_elements": len(elements_info.get('elements', []))
            }
            
            logger.info(f"页面分析完成，发现 {analysis_result['total_elements']} 个可交互元素")
            return analysis_result
            
        except Exception as e:
            logger.error(f"页面分析失败: {str(e)}")
            raise Exception(f"页面分析失败: {str(e)}")
    
    def save_analysis(self, package_dir: Path, analysis_result: Dict[str, Any]):
        """
        保存页面分析结果
        :param package_dir: 包目录
        :param analysis_result: 分析结果
        """
        try:
            # 创建页面分析目录
            page_analysis_dir = package_dir / "page_analysis"
            page_analysis_dir.mkdir(exist_ok=True)
            
            # 1. 保存完整HTML
            self._save_complete_html(page_analysis_dir)
            
            # 2. 保存页面截图
            self._save_page_screenshot(page_analysis_dir)
            
            # 3. 保存分析结果JSON
            with open(page_analysis_dir / "elements_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            
            # 4. 生成分析报告
            self._generate_analysis_report(page_analysis_dir, analysis_result)
            
            logger.info(f"页面分析结果已保存到: {page_analysis_dir}")
            
        except Exception as e:
            logger.error(f"保存页面分析结果失败: {str(e)}")
    
    def _get_page_info(self) -> Dict[str, Any]:
        """获取页面基本信息"""
        return self.page.evaluate("""() => {
            return {
                url: window.location.href,
                title: document.title,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                scroll: {
                    maxX: document.documentElement.scrollWidth - window.innerWidth,
                    maxY: document.documentElement.scrollHeight - window.innerHeight
                },
                userAgent: navigator.userAgent
            };
        }""")
    
    def _extract_elements_info(self) -> Dict[str, Any]:
        """提取页面元素信息"""
        return self.page.evaluate("""() => {
            const elements = [];
            const interactiveSelectors = [
                'button', 'input', 'select', 'textarea', 'a[href]',
                '[onclick]', '[role="button"]', '[tabindex]',
                'form', '[id]', '[class*="btn"]', '[class*="button"]',
                '[type="submit"]', '[type="button"]', 'label'
            ];
            
            const allElements = document.querySelectorAll(interactiveSelectors.join(','));
            
            allElements.forEach((element, index) => {
                // 只处理可见或重要的元素
                if (element.offsetParent !== null || element.tagName === 'INPUT' || element.tagName === 'FORM') {
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
                        visibility: {
                            visible: element.offsetParent !== null,
                            displayed: window.getComputedStyle(element).display !== 'none',
                            opacity: window.getComputedStyle(element).opacity
                        },
                        selectors: {
                            id: element.id ? `#${element.id}` : '',
                            name: element.name ? `[name="${element.name}"]` : '',
                            class: element.className ? `.${element.className.split(' ').join('.')}` : '',
                            css: element.id ? `#${element.id}` : 
                                 element.className ? `.${element.className.split(' ')[0]}` : 
                                 element.tagName.toLowerCase()
                        },
                        dataAttributes: {},
                        parentInfo: {
                            tagName: element.parentElement?.tagName || '',
                            id: element.parentElement?.id || '',
                            className: element.parentElement?.className || ''
                        }
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
                elements: elements,
                summary: {
                    total: elements.length,
                    byTag: elements.reduce((acc, el) => {
                        acc[el.tagName] = (acc[el.tagName] || 0) + 1;
                        return acc;
                    }, {}),
                    withId: elements.filter(el => el.id).length,
                    withName: elements.filter(el => el.name).length,
                    withClass: elements.filter(el => el.className).length
                }
            };
        }""")
    
    def _analyze_forms(self) -> Dict[str, Any]:
        """分析页面表单"""
        return self.page.evaluate("""() => {
            const forms = [];
            const formElements = document.querySelectorAll('form');
            
            formElements.forEach((form, index) => {
                const formInfo = {
                    index: index + 1,
                    id: form.id || '',
                    name: form.name || '',
                    action: form.action || '',
                    method: form.method || 'GET',
                    fields: []
                };
                
                // 分析表单字段
                const fields = form.querySelectorAll('input, select, textarea');
                fields.forEach(field => {
                    formInfo.fields.push({
                        tagName: field.tagName,
                        type: field.type || '',
                        name: field.name || '',
                        id: field.id || '',
                        placeholder: field.placeholder || '',
                        required: field.required || false,
                        value: field.value || ''
                    });
                });
                
                forms.push(formInfo);
            });
            
            return {
                forms: forms,
                totalForms: forms.length,
                totalFields: forms.reduce((acc, form) => acc + form.fields.length, 0)
            };
        }""")
    
    def _analyze_links(self) -> Dict[str, Any]:
        """分析页面链接和导航"""
        return self.page.evaluate("""() => {
            const links = [];
            const linkElements = document.querySelectorAll('a[href]');
            
            linkElements.forEach((link, index) => {
                const rect = link.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {  // 只包含可见链接
                    links.push({
                        index: index + 1,
                        text: link.textContent?.trim() || '',
                        href: link.href,
                        title: link.title || '',
                        target: link.target || '',
                        position: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                }
            });
            
            return {
                links: links,
                totalLinks: links.length,
                externalLinks: links.filter(link => !link.href.includes(window.location.hostname)).length,
                internalLinks: links.filter(link => link.href.includes(window.location.hostname)).length
            };
        }""")
    
    def _save_complete_html(self, analysis_dir: Path):
        """保存完整HTML（完整CSS内联版本）"""
        try:
            # 使用改进的CSS内联方法
            html_content = self.page.evaluate("""async () => {
                try {
                    // 收集所有CSS样式
                    const allStyles = [];
                    
                    // 1. 从可访问的样式表中提取CSS规则
                    const styleSheets = Array.from(document.styleSheets);
                    for (let sheet of styleSheets) {
                        try {
                            if (sheet.cssRules && sheet.cssRules.length > 0) {
                                const cssRules = Array.from(sheet.cssRules).map(rule => rule.cssText);
                                allStyles.push(`/* StyleSheet: ${sheet.href || 'inline'} */`);
                                allStyles.push(...cssRules);
                            }
                        } catch (e) {
                            // 跨域样式表无法访问，尝试通过fetch获取
                            if (sheet.href) {
                                try {
                                    const response = await fetch(sheet.href);
                                    if (response.ok) {
                                        const cssText = await response.text();
                                        allStyles.push(`/* Fetched CSS: ${sheet.href} */`);
                                        allStyles.push(cssText);
                                    }
                                } catch (fetchError) {
                                    console.log('无法获取外部CSS:', sheet.href);
                                }
                            }
                        }
                    }
                    
                    // 2. 收集内联style标签
                    const styleTags = document.querySelectorAll('style');
                    styleTags.forEach(style => {
                        if (style.textContent && style.textContent.trim()) {
                            allStyles.push('/* Inline Style Tag */');
                            allStyles.push(style.textContent);
                        }
                    });
                    
                    // 3. 收集重要元素的内联样式
                    const importantElements = document.querySelectorAll('[style]');
                    const inlineStyles = [];
                    importantElements.forEach((element, index) => {
                        const style = element.getAttribute('style');
                        if (style && style.trim()) {
                            // 生成选择器
                            const selector = element.id ? `#${element.id}` : 
                                            element.className ? `.${element.className.split(' ').filter(cls => cls.length > 0)[0]}` : 
                                            `[data-inline-style-${index}]`;
                            
                            // 为没有ID和class的元素添加标识
                            if (!element.id && !element.className) {
                                element.setAttribute('data-inline-style-' + index, '');
                            }
                            
                            inlineStyles.push(`${selector} { ${style} }`);
                        }
                    });
                    
                    if (inlineStyles.length > 0) {
                        allStyles.push('/* Converted Inline Styles */');
                        allStyles.push(...inlineStyles);
                    }
                    
                    // 克隆文档
                    const clonedDoc = document.cloneNode(true);
                    const clonedHtml = clonedDoc.documentElement;
                    
                    // 移除原有的CSS链接和style标签
                    const cssLinks = clonedHtml.querySelectorAll('link[rel="stylesheet"], link[rel="preload"][as="style"]');
                    cssLinks.forEach(link => link.remove());
                    
                    const oldStyles = clonedHtml.querySelectorAll('style');
                    oldStyles.forEach(style => style.remove());
                    
                    // 创建新的合并样式
                    if (allStyles.length > 0) {
                        const newStyle = clonedDoc.createElement('style');
                        newStyle.setAttribute('type', 'text/css');
                        newStyle.textContent = '\\n' + allStyles.join('\\n') + '\\n';
                        
                        const head = clonedHtml.querySelector('head');
                        if (head) {
                            head.appendChild(newStyle);
                        }
                    }
                    
                    // 获取完整HTML
                    const doctype = document.doctype ? 
                        `<!DOCTYPE ${document.doctype.name}>` : '';
                    return doctype + '\\n' + clonedHtml.outerHTML;
                    
                } catch (error) {
                    console.error('CSS内联处理失败:', error);
                    
                    // 失败时返回基础HTML
                    const doctype = document.doctype ? 
                        `<!DOCTYPE ${document.doctype.name}>` : '';
                    return doctype + '\\n' + document.documentElement.outerHTML;
                }
            }""")
            
            # 如果JavaScript方法失败，使用原始方法
            if not html_content:
                html_content = self.page.content()
            
            # 清理HTML内容，移除多余的占位元素
            html_content = self._clean_html_content(html_content)
            
            with open(analysis_dir / "complete_page.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            logger.warning(f"保存完整HTML失败，使用基础方法: {str(e)}")
            # fallback到原始方法
            html_content = self.page.content()
            html_content = self._clean_html_content(html_content)
            with open(analysis_dir / "complete_page.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
    
    def _clean_html_content(self, html_content: str) -> str:
        """
        清理HTML内容，移除多余元素但保留CSS样式
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
    
    def _save_page_screenshot(self, analysis_dir: Path):
        """保存页面截图（不包含录制遮罩层）"""
        try:
            # 设置较短的超时时间，跳过字体加载等待
            self.page.set_default_timeout(10000)  # 10秒超时
            
            # 禁用字体加载等待
            self.page.evaluate("""
                () => {
                    // 停止等待字体加载
                    if (document.fonts && document.fonts.ready) {
                        document.fonts.clear();
                    }
                }
            """)
            
            # 临时隐藏录制遮罩层（如果存在）
            overlay_hidden = self.page.evaluate("""() => {
                const rpaOverlay = document.getElementById('rpa-processing-overlay');
                if (rpaOverlay) {
                    rpaOverlay.style.display = 'none';
                    return true;
                }
                return false;
            }""")
            
            # 短暂等待确保遮罩隐藏生效
            if overlay_hidden:
                self.page.wait_for_timeout(200)
            
            self.page.screenshot(
                path=str(analysis_dir / "full_page_screenshot.png"), 
                full_page=True,
                animations="disabled"  # 禁用动画
            )
            
            # 恢复遮罩层显示（如果之前存在）
            if overlay_hidden:
                self.page.evaluate("""() => {
                    const rpaOverlay = document.getElementById('rpa-processing-overlay');
                    if (rpaOverlay) {
                        rpaOverlay.style.display = 'flex';
                    }
                }""")
            
            # 恢复默认超时
            self.page.set_default_timeout(30000)
            
        except Exception as e:
            logger.warning(f"页面截图失败，尝试简化截图: {str(e)}")
            # 如果全页截图失败，尝试当前视口截图
            try:
                self.page.set_default_timeout(5000)  # 5秒超时
                
                # 隐藏遮罩层（如果存在）
                overlay_hidden = self.page.evaluate("""() => {
                    const rpaOverlay = document.getElementById('rpa-processing-overlay');
                    if (rpaOverlay) {
                        rpaOverlay.style.display = 'none';
                        return true;
                    }
                    return false;
                }""")
                
                if overlay_hidden:
                    self.page.wait_for_timeout(200)
                
                self.page.screenshot(
                    path=str(analysis_dir / "viewport_screenshot.png"),
                    full_page=False
                )
                
                # 恢复遮罩层显示
                if overlay_hidden:
                    self.page.evaluate("""() => {
                        const rpaOverlay = document.getElementById('rpa-processing-overlay');
                        if (rpaOverlay) {
                            rpaOverlay.style.display = 'flex';
                        }
                    }""")
                
                self.page.set_default_timeout(30000)  # 恢复默认超时
            except Exception as e2:
                logger.error(f"截图完全失败: {str(e2)}")
                # 创建一个空的占位文件
                (analysis_dir / "screenshot_failed.txt").write_text(
                    f"截图失败: {str(e2)}", encoding='utf-8'
                )
    
    def _generate_analysis_report(self, analysis_dir: Path, analysis_result: Dict[str, Any]):
        """生成页面分析报告"""
        page_info = analysis_result['page_info']
        elements_info = analysis_result['elements']
        forms_info = analysis_result['forms']
        links_info = analysis_result['links']
        
        report_content = f"""# 页面结构分析报告

## 页面基本信息
- **URL**: {page_info['url']}
- **标题**: {page_info['title']}
- **分析时间**: {analysis_result['analysis_time']}
- **视口大小**: {page_info['viewport']['width']} x {page_info['viewport']['height']}
- **可交互元素总数**: {analysis_result['total_elements']}

## 元素统计

### 按标签类型分布
"""
        
        for tag, count in elements_info['summary']['byTag'].items():
            report_content += f"- **{tag}**: {count} 个\n"
        
        report_content += f"""

### 定位器可用性
- **有ID的元素**: {elements_info['summary']['withId']} 个
- **有Name的元素**: {elements_info['summary']['withName']} 个  
- **有Class的元素**: {elements_info['summary']['withClass']} 个

## 表单分析
- **表单总数**: {forms_info['totalForms']}
- **表单字段总数**: {forms_info['totalFields']}

## 链接分析
- **链接总数**: {links_info['totalLinks']}
- **内部链接**: {links_info['internalLinks']} 个
- **外部链接**: {links_info['externalLinks']} 个

## 定位器建议

### 优先级排序
1. **ID选择器** - 最稳定，推荐优先使用
2. **Name属性** - 适用于表单元素
3. **稳定Class** - 避免动态生成的class
4. **Data属性** - 通常比较稳定
5. **文本内容** - 适用于按钮和链接
6. **XPath** - 最后选择

### 可交互元素详情

| 序号 | 标签 | ID | Name | 主要Class | 文本内容 | 推荐选择器 |
|------|------|----|----|----------|----------|------------|
"""
        
        elements = elements_info['elements']
        for element in elements[:30]:  # 显示前30个元素
            # 确定推荐选择器
            recommended_selector = ""
            if element['selectors']['id']:
                recommended_selector = element['selectors']['id']
            elif element['selectors']['name']:
                recommended_selector = element['selectors']['name']
            elif element['selectors']['class']:
                # 取第一个稳定的class
                classes = element['className'].split(' ')
                stable_class = next((cls for cls in classes if not cls.startswith('btn-') and not cls.endswith('-active')), classes[0] if classes else '')
                recommended_selector = f".{stable_class}" if stable_class else element['selectors']['css']
            else:
                recommended_selector = element['selectors']['css']
            
            # 格式化显示内容
            main_class = element['className'].split(' ')[0] if element['className'] else ''
            text_preview = element['text'][:20] + '...' if len(element['text']) > 20 else element['text']
            
            report_content += f"| {element['index']} | {element['tagName']} | {element['id']} | {element['name']} | {main_class} | {text_preview} | `{recommended_selector}` |\n"
        
        if len(elements) > 30:
            report_content += f"\n> 注意: 还有 {len(elements) - 30} 个元素未在此表格中显示。完整信息请查看 `elements_analysis.json` 文件。\n"
        
        report_content += """

## 开发建议

### 定位器稳定性优化
1. **优先使用ID**: 如果元素有ID且不是动态生成的，优先使用
2. **验证Class稳定性**: 检查class名是否包含版本号、随机字符等
3. **考虑层级关系**: 对于没有稳定属性的元素，考虑使用父元素+相对位置
4. **文本定位注意事项**: 确保文本内容不会因语言、数据变化而改变

### 页面加载处理
- 添加适当的等待逻辑，确保动态内容加载完成
- 对于异步加载的内容，使用 `wait_for_selector()` 等方法
- 考虑页面滚动对元素可见性的影响

### 错误处理建议
- 为每个关键操作添加异常处理
- 提供备用的定位策略
- 记录详细的执行日志便于调试

## 文件说明
- `complete_page.html` - 完整的页面HTML源码
- `full_page_screenshot.png` - 页面完整截图
- `elements_analysis.json` - 所有元素的详细数据
- `elements_analysis_report.md` - 本分析报告
"""
        
        with open(analysis_dir / "elements_analysis_report.md", 'w', encoding='utf-8') as f:
            f.write(report_content) 