"""
报告生成器

负责生成RPA开发包的各种报告和文档
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rpa_framework.utils.log import logger


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        logger.debug("报告生成器初始化完成")
    
    def generate_all_reports(self, package_dir: Path, package_name: str, 
                           final_package_name: str, actions: List[Dict], 
                           page_analysis: Dict[str, Any]):
        """
        生成所有报告和文档
        """
        try:
            logger.info("开始生成RPA开发报告...")
            
            # 生成详细的操作步骤文档
            self._generate_detailed_steps_document(package_dir, package_name, actions)
            
            # 生成开发指南
            self._generate_development_guide(package_dir, package_name, final_package_name, actions)
            
            # 生成快速开始指南
            self._generate_quick_start_guide(package_dir, package_name, actions)
            
            # 生成步骤导航页面 index.html
            self._generate_index_html(package_dir, package_name, actions)
            
            logger.info("所有报告生成完成")
            
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
    
    def _generate_detailed_steps_document(self, package_dir: Path, package_name: str, actions: List[Dict]):
        """生成详细的操作步骤文档"""
        try:
            code_dir = package_dir / "generated_code"
            code_dir.mkdir(exist_ok=True)
            
            document = f"""# {package_name} - 详细操作步骤

## 录制信息
- 流程名称: {package_name}
- 操作步骤数: {len(actions)}
- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 操作列表
"""
            
            for i, action in enumerate(actions, 1):
                step_desc = self._get_step_description(action, i, actions)
                document += f"""
### {step_desc}
- 元素标签: {action['tagName']}
- 操作值: {action.get('value', '')}
- 时间戳: {action['timestamp']}ms
"""
            
            with open(code_dir / "操作步骤说明.md", 'w', encoding='utf-8') as f:
                f.write(document)
                
        except Exception as e:
            logger.error(f"生成操作步骤文档失败: {str(e)}")
    
    def _generate_development_guide(self, package_dir: Path, package_name: str, 
                                  final_package_name: str, actions: List[Dict]):
        """生成开发指南"""
        guide = f"""# RPA开发指南 - {package_name}

## 项目概述
本包包含了从用户操作录制中提取的完整RPA开发资料。

## 操作统计
- 总操作数: {len(actions)}
- 主要操作类型: {', '.join(set(action['type'] for action in actions))}

## 快速开始步骤
1. 环境准备: pip install playwright
2. 代码测试: 打开 generated_code/playwright_automation.py
3. 稳定性优化: 查看 page_analysis/ 目录
"""
        
        with open(package_dir / "RPA开发指南.md", 'w', encoding='utf-8') as f:
            f.write(guide)
    
    def _generate_quick_start_guide(self, package_dir: Path, package_name: str, actions: List[Dict]):
        """生成快速开始指南"""
        guide = f"""# 快速开始 - {package_name}

## 5分钟快速运行

### 1. 环境准备
```bash
pip install playwright
playwright install chromium
```

### 2. 运行自动化脚本
```bash
cd generated_code
python playwright_automation.py
```

### 3. 如果遇到问题
查看 操作步骤说明.md 获取详细帮助！
"""
        
        with open(package_dir / "quick_start.md", 'w', encoding='utf-8') as f:
            f.write(guide)
    
    def _generate_index_html(self, package_dir: Path, package_name: str, actions: List[Dict]):
        """生成步骤导航页面 index.html"""
        try:
            # 生成步骤列表HTML
            steps_html = ""
            for i, action in enumerate(actions, 1):
                # 生成与录制器相同的步骤描述和文件名
                step_desc = self._get_step_description(action, i, actions)
                filename_prefix = self._sanitize_filename(f"{i:02d}_{step_desc}")
                
                # 获取推荐的locator
                best_locator = "未知定位器"
                if action.get('selectors') and len(action['selectors']) > 0:
                    # 取优先级最高的定位器（第一个）
                    best_selector = action['selectors'][0]
                    # 根据选择器类型生成正确的Python格式
                    best_locator = self._generate_python_locator_from_selector(best_selector)
                
                # 生成步骤卡片HTML
                steps_html += f"""
                <div class="step-card" data-step="{i}">
                    <div class="step-header">
                        <span class="step-number">第{i}步</span>
                        <span class="step-type">{action.get('type', 'unknown').upper()}</span>
                    </div>
                    <div class="step-description">{step_desc}</div>
                    <div class="step-details">
                        <div class="detail-item">
                            <strong>目标元素:</strong> {action.get('tagName', 'unknown')}
                        </div>
                        <div class="detail-item">
                            <strong>操作值:</strong> {action.get('value', '') or '无'}
                        </div>
                        <div class="detail-item">
                            <strong>页面:</strong> {action.get('page_info', {}).get('title', '未知页面')}
                        </div>
                        <div class="detail-item locator-item">
                            <strong>Locator:</strong> <code class="locator-code">{best_locator}</code>
                        </div>
                    </div>
                    <div class="step-links">
                        <a href="step_screenshots/{filename_prefix}.png" target="_blank" class="btn btn-image">
                            📷 查看截图
                        </a>
                        <a href="step_screenshots/{filename_prefix}.html" target="_blank" class="btn btn-html">
                            🌐 查看页面
                        </a>
                    </div>
                </div>
                """
            
            # 生成完整的HTML页面
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{package_name} - 操作步骤导航</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(45deg, #1890ff, #36cfc9);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        
        .header p {{
            font-size: 16px;
            opacity: 0.9;
        }}
        
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.2);
        }}
        
        .stat-item {{
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            display: block;
        }}
        
        .stat-label {{
            font-size: 14px;
            opacity: 0.8;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .search-bar {{
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .search-input {{
            width: 400px;
            max-width: 100%;
            padding: 12px 20px;
            border: 2px solid #e8e8e8;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }}
        
        .search-input:focus {{
            border-color: #1890ff;
        }}
        
        .steps-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        
        .step-card {{
            background: white;
            border: 1px solid #e8e8e8;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .step-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            border-color: #1890ff;
        }}
        
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .step-number {{
            background: linear-gradient(45deg, #1890ff, #36cfc9);
            color: white;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        .step-type {{
            background: #f0f0f0;
            color: #666;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        .step-description {{
            font-size: 16px;
            font-weight: 500;
            color: #333;
            margin-bottom: 15px;
            line-height: 1.4;
        }}
        
        .step-details {{
            margin-bottom: 20px;
        }}
        
        .detail-item {{
            margin-bottom: 8px;
            font-size: 14px;
            color: #666;
            line-height: 1.4;
        }}
        
        .detail-item strong {{
            color: #333;
        }}
        
        .locator-item {{
            margin-top: 12px;
            padding-top: 8px;
            border-top: 1px solid #f0f0f0;
        }}
        
        .locator-code {{
            background: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 4px;
            padding: 4px 8px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 12px;
            color: #d73a49;
            word-break: break-all;
            display: inline-block;
            max-width: 100%;
        }}
        
        .step-links {{
            display: flex;
            gap: 10px;
        }}
        
        .btn {{
            display: inline-flex;
            align-items: center;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
            border: 1px solid transparent;
        }}
        
        .btn-image {{
            background: #f6ffed;
            color: #52c41a;
            border-color: #52c41a;
        }}
        
        .btn-image:hover {{
            background: #52c41a;
            color: white;
        }}
        
        .btn-html {{
            background: #e6f7ff;
            color: #1890ff;
            border-color: #1890ff;
        }}
        
        .btn-html:hover {{
            background: #1890ff;
            color: white;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            border-top: 1px solid #e8e8e8;
        }}
        
        .footer p {{
            margin-bottom: 10px;
        }}
        
        .hidden {{
            display: none !important;
        }}
        
        @media (max-width: 768px) {{
            .steps-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats {{
                flex-direction: column;
                gap: 15px;
            }}
            
            .step-links {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 {package_name}</h1>
            <p>RPA操作步骤录制结果 - 可视化导航页面</p>
            
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-number">{len(actions)}</span>
                    <span class="stat-label">操作步骤</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{len(set(action.get('type', 'unknown') for action in actions))}</span>
                    <span class="stat-label">操作类型</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{datetime.now().strftime('%m-%d')}</span>
                    <span class="stat-label">录制日期</span>
                </div>
            </div>
        </div>
        
        <div class="content">
            <div class="search-bar">
                <input type="text" class="search-input" placeholder="🔍 搜索步骤描述..." id="searchInput">
            </div>
            
            <div class="steps-grid" id="stepsGrid">
                {steps_html}
            </div>
        </div>
        
        <div class="footer">
            <p><strong>使用说明:</strong> 点击"查看截图"可以看到该步骤执行时的页面截图，点击"查看页面"可以查看完整的页面HTML。</p>
            <p><strong>调试提示:</strong> 可以在RPA系统的调试功能中输入此 index.html 的本地路径进行 Playwright 调试。</p>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 总计 {len(actions)} 个操作步骤</p>
        </div>
    </div>

    <script>
        // 搜索功能
        const searchInput = document.getElementById('searchInput');
        const stepsGrid = document.getElementById('stepsGrid');
        const stepCards = document.querySelectorAll('.step-card');

        searchInput.addEventListener('input', function() {{
            const searchTerm = this.value.toLowerCase();
            
            stepCards.forEach(card => {{
                const description = card.querySelector('.step-description').textContent.toLowerCase();
                const details = card.querySelector('.step-details').textContent.toLowerCase();
                
                if (description.includes(searchTerm) || details.includes(searchTerm)) {{
                    card.classList.remove('hidden');
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
        }});

        // 步骤卡片点击高亮
        stepCards.forEach(card => {{
            card.addEventListener('click', function() {{
                stepCards.forEach(c => c.style.border = '1px solid #e8e8e8');
                this.style.border = '2px solid #1890ff';
            }});
        }});
    </script>
</body>
</html>"""
            
            # 保存 index.html
            with open(package_dir / "index.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            logger.info(f"步骤导航页面已生成: {package_dir / 'index.html'}")
            
        except Exception as e:
            logger.error(f"生成index.html失败: {str(e)}")
    
    def _get_step_description(self, action: dict, step_number: int, actions: List[Dict]) -> str:
        """
        生成步骤描述（与录制器保持一致，支持手动录制友好描述）
        """
        action_type = action.get('type', 'unknown')
        element_info = action.get('element_info', {})
        
        # 手动保存步骤保持原有逻辑
        if action_type == 'manual_save':
            return element_info.get('text', f'{step_number:02d}_手动保存页面')
        
        # 自动录制步骤与recorder.py保持一致
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
        """清理文件名（与录制器保持一致）"""
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
    
    def _generate_python_locator_from_selector(self, selector: Dict) -> str:
        """
        根据录制时的selector数据生成Python格式的locator
        :param selector: 录制时的selector数据
        :return: Python格式的locator字符串
        """
        try:
            selector_type = selector.get('type', 'css')
            
            if selector_type == 'role':
                role = selector.get('role', 'button')
                name = selector.get('name', '')
                if name:
                    return f"page.get_by_role('{role}', name='{name}')"
                else:
                    return f"page.get_by_role('{role}')"
            
            elif selector_type == 'text':
                text_value = selector.get('value', '')
                return f"page.get_by_text('{text_value}')"
            
            elif selector_type == 'label':
                label_value = selector.get('value', '')
                return f"page.get_by_label('{label_value}')"
            
            elif selector_type == 'placeholder':
                placeholder_value = selector.get('value', '')
                return f"page.get_by_placeholder('{placeholder_value}')"
            
            elif selector_type == 'testId':
                testid_value = selector.get('value', '')
                return f"page.get_by_test_id('{testid_value}')"
            
            elif selector_type == 'title':
                title_value = selector.get('value', '')
                return f"page.get_by_title('{title_value}')"
            
            elif selector_type == 'css':
                css_value = selector.get('value', '')
                return f"page.locator('{css_value}')"
            
            elif selector_type == 'xpath':
                xpath_value = selector.get('value', '')
                return f"page.locator('xpath={xpath_value}')"
            
            else:
                # 未知类型，尝试从value字段获取
                value = selector.get('value', '未知定位器')
                return f"page.locator('{value}')"
                
        except Exception as e:
            logger.debug(f"生成Python locator失败: {str(e)}")
            return "未知定位器"
    
    def _convert_js_locator_to_python(self, js_locator: str) -> str:
        """
        将JavaScript locator转换为Python格式（保留向后兼容性）
        :param js_locator: JavaScript格式的locator
        :return: Python格式的locator
        """
        import re
        
        try:
            # 转换 getByRole('button', { name: '登录' }) -> get_by_role(role='button', name='登录')
            role_match = re.match(r"getByRole\(['\"]([^'\"]+)['\"](?:,\s*\{\s*name:\s*['\"]([^'\"]*)['\"].*?\})?\)", js_locator)
            if role_match:
                role = role_match.group(1)
                name = role_match.group(2)
                if name:
                    return f"get_by_role(role='{role}', name='{name}')"
                else:
                    return f"get_by_role(role='{role}')"
            
            # 转换 getByText('账户admin') -> get_by_text('账户admin')
            text_match = re.match(r"getByText\(['\"]([^'\"]*)['\"]", js_locator)
            if text_match:
                text = text_match.group(1)
                return f"get_by_text('{text}')"
            
            # 转换 getByLabel('pink') -> get_by_label('pink')
            label_match = re.match(r"getByLabel\(['\"]([^'\"]*)['\"]", js_locator)
            if label_match:
                label = label_match.group(1)
                return f"get_by_label('{label}')"
            
            # 转换 getByPlaceholder('请输入用户名') -> get_by_placeholder('请输入用户名')
            placeholder_match = re.match(r"getByPlaceholder\(['\"]([^'\"]*)['\"]", js_locator)
            if placeholder_match:
                placeholder = placeholder_match.group(1)
                return f"get_by_placeholder('{placeholder}')"
            
            # 转换 getByTestId('login-button') -> get_by_test_id('login-button')
            testid_match = re.match(r"getByTestId\(['\"]([^'\"]*)['\"]", js_locator)
            if testid_match:
                testid = testid_match.group(1)
                return f"get_by_test_id('{testid}')"
            
            # 转换 getByTitle('标题') -> get_by_title('标题')
            title_match = re.match(r"getByTitle\(['\"]([^'\"]*)['\"]", js_locator)
            if title_match:
                title = title_match.group(1)
                return f"get_by_title('{title}')"
            
            # 如果是CSS选择器或无法解析的，直接返回
            if js_locator.startswith('#') or js_locator.startswith('.') or js_locator.startswith('['):
                return f"locator('{js_locator}')"
            
            # 其他情况直接返回原值
            return js_locator
            
        except Exception as e:
            logger.debug(f"转换locator格式失败: {str(e)}")
            return js_locator 