"""
邮件发送工具

用于RPA系统发送错误通知邮件，支持HTML格式内容、多附件、邮件模板
"""

import smtplib
import os
import mimetypes
from pathlib import Path
from typing import Union, List, Optional, Dict, Any
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from rpa_framework.utils.log import logger


# 预定义邮件模板
EMAIL_TEMPLATES = {
    "rpa_error": {
        "subject": "[RPA告警] {task_name}执行失败",
        "html_template": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #d32f2f;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .error-box {{
            background: #ffebee;
            border-left: 4px solid #d32f2f;
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        .info-item {{
            margin: 10px 0;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 3px;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
        .value {{
            color: #333;
        }}
        .error-text {{
            color: #d32f2f;
            font-weight: bold;
        }}
        .warning-box {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        .success-box {{
            background: #e8f5e8;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🚨 RPA任务执行失败</h2>
    </div>
    
    <div class="info-item">
        <span class="label">任务名称：</span>
        <span class="value">{task_name}</span>
    </div>
    
    <div class="info-item">
        <span class="label">失败时间：</span>
        <span class="value">{error_time}</span>
    </div>
    
    <div class="error-box">
        <span class="label">错误信息：</span><br>
        <span class="error-text">{error_message}</span>
    </div>
    
    {impact_scope_html}
    {additional_info_html}
</body>
</html>
        """
    },
    
    "rpa_success": {
        "subject": "[RPA通知] {task_name}执行成功",
        "html_template": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #4caf50;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .success-box {{
            background: #e8f5e8;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        .info-item {{
            margin: 10px 0;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 3px;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
        .value {{
            color: #333;
        }}
        .success-text {{
            color: #4caf50;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>✅ RPA任务执行成功</h2>
    </div>
    
    <div class="info-item">
        <span class="label">任务名称：</span>
        <span class="value">{task_name}</span>
    </div>
    
    <div class="info-item">
        <span class="label">完成时间：</span>
        <span class="value">{completion_time}</span>
    </div>
    
    <div class="success-box">
        <span class="label">执行结果：</span><br>
        <span class="success-text">{result_message}</span>
    </div>
    
    {statistics_html}
    {additional_info_html}
</body>
</html>
        """
    },
    
    "rpa_warning": {
        "subject": "[RPA警告] {task_name}执行异常",
        "html_template": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #ff9800;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .warning-box {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        .info-item {{
            margin: 10px 0;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 3px;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
        .value {{
            color: #333;
        }}
        .warning-text {{
            color: #ff9800;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>⚠️ RPA任务执行异常</h2>
    </div>
    
    <div class="info-item">
        <span class="label">任务名称：</span>
        <span class="value">{task_name}</span>
    </div>
    
    <div class="info-item">
        <span class="label">异常时间：</span>
        <span class="value">{warning_time}</span>
    </div>
    
    <div class="warning-box">
        <span class="label">异常信息：</span><br>
        <span class="warning-text">{warning_message}</span>
    </div>
    
    {impact_scope_html}
    {additional_info_html}
</body>
</html>
        """
    },
    
    "rpa_report": {
        "subject": "[RPA报告] {task_name}执行报告",
        "html_template": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #2196f3;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .info-item {{
            margin: 10px 0;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 3px;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
        .value {{
            color: #333;
        }}
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        .stats-table th, .stats-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        .stats-table th {{
            background-color: #f2f2f2;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>📊 RPA任务执行报告</h2>
    </div>
    
    <div class="info-item">
        <span class="label">任务名称：</span>
        <span class="value">{task_name}</span>
    </div>
    
    <div class="info-item">
        <span class="label">执行时间：</span>
        <span class="value">{execution_time}</span>
    </div>
    
    {statistics_html}
    {summary_html}
    {additional_info_html}
</body>
</html>
        """
    }
}
smtp_config = {
    "host": "smtp.ah.sgcc.com.cn",
    "port": 25,
    "username": "xtgscwgk@ah.sgcc.com.cn",
    "password": "Ygsoft.1600!!",
    "use_tls": False
}

def send_email_with_template(
    template_name: str,
    template_data: Dict[str, Any],
    from_addr: str,
    to_addr: str,
    attachments: Optional[Union[str, List[str]]] = None,
    smtp_config: Optional[dict] = smtp_config,
    custom_subject: Optional[str] = None
) -> bool:
    """
    使用模板发送邮件
    
    Args:
        template_name: 模板名称（rpa_error, rpa_success, rpa_warning, rpa_report）
        template_data: 模板数据字典
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱（支持多个，用逗号分隔）
        attachments: 附件路径（单个文件、文件列表或目录路径）
        smtp_config: SMTP配置字典
        custom_subject: 自定义主题（可选，覆盖模板主题）
    
    Returns:
        bool: 发送是否成功
    """
    try:
        # 获取模板
        if template_name not in EMAIL_TEMPLATES:
            logger.error(f"邮件模板不存在: {template_name}")
            return False
        
        template = EMAIL_TEMPLATES[template_name]
        
        # 生成主题
        subject = custom_subject or template["subject"].format(**template_data)
        
        # 生成HTML内容
        html_content = _render_template(template["html_template"], template_data)
        
        # 发送邮件
        return send_email(
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            html_content=html_content,
            attachments=attachments,
            smtp_config=smtp_config
        )
        
    except Exception as e:
        logger.error(f"使用模板发送邮件失败: {str(e)}")
        return False


def _render_template(template: str, data: Dict[str, Any]) -> str:
    """
    渲染模板
    
    Args:
        template: 模板字符串
        data: 模板数据
    
    Returns:
        str: 渲染后的HTML内容
    """
    try:
        # 处理可选字段
        if 'impact_scope' in data and data['impact_scope']:
            data['impact_scope_html'] = f"""
            <div class="info-item">
                <span class="label">影响范围：</span>
                <span class="value">{data['impact_scope']}</span>
            </div>
            """
        else:
            data['impact_scope_html'] = ""
        
        if 'additional_info' in data and data['additional_info']:
            data['additional_info_html'] = f"""
            <div class="info-item">
                <span class="label">附加信息：</span>
                <span class="value">{data['additional_info']}</span>
            </div>
            """
        else:
            data['additional_info_html'] = ""
        
        if 'statistics' in data and data['statistics']:
            stats_html = "<table class='stats-table'>"
            stats_html += "<tr><th>指标</th><th>数值</th></tr>"
            for key, value in data['statistics'].items():
                stats_html += f"<tr><td>{key}</td><td>{value}</td></tr>"
            stats_html += "</table>"
            data['statistics_html'] = f"""
            <div class="info-item">
                <span class="label">执行统计：</span>
                {stats_html}
            </div>
            """
        else:
            data['statistics_html'] = ""
        
        if 'summary' in data and data['summary']:
            data['summary_html'] = f"""
            <div class="info-item">
                <span class="label">执行摘要：</span>
                <span class="value">{data['summary']}</span>
            </div>
            """
        else:
            data['summary_html'] = ""
        
        # 渲染模板
        return template.format(**data)
        
    except Exception as e:
        logger.error(f"模板渲染失败: {str(e)}")
        return f"<html><body><h1>模板渲染失败</h1><p>错误信息: {str(e)}</p></body></html>"


def send_rpa_error_notification(
    task_name: str,
    error_message: str,
    from_addr: str,
    to_addr: str,
    attachments: Optional[Union[str, List[str]]] = None,
    smtp_config: Optional[dict] = smtp_config,
    impact_scope: str = "",
    additional_info: str = ""
) -> bool:
    """
    发送RPA错误通知邮件（便捷函数）
    
    Args:
        task_name: 任务名称
        error_message: 错误信息
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱
        attachments: 附件路径
        smtp_config: SMTP配置
        impact_scope: 影响范围
        additional_info: 附加信息
    
    Returns:
        bool: 发送是否成功
    """
    template_data = {
        'task_name': task_name,
        'error_message': error_message,
        'error_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'impact_scope': impact_scope,
        'additional_info': additional_info
    }
    
    return send_email_with_template(
        template_name='rpa_error',
        template_data=template_data,
        from_addr=from_addr,
        to_addr=to_addr,
        attachments=attachments,
        smtp_config=smtp_config
    )


def send_rpa_success_notification(
    task_name: str,
    result_message: str,
    from_addr: str,
    to_addr: str,
    attachments: Optional[Union[str, List[str]]] = None,
    smtp_config: Optional[dict] = smtp_config,
    statistics: Optional[Dict[str, Any]] = None,
    additional_info: str = ""
) -> bool:
    """
    发送RPA成功通知邮件（便捷函数）
    
    Args:
        task_name: 任务名称
        result_message: 结果信息
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱
        attachments: 附件路径
        smtp_config: SMTP配置
        statistics: 统计信息
        additional_info: 附加信息
    
    Returns:
        bool: 发送是否成功
    """
    template_data = {
        'task_name': task_name,
        'result_message': result_message,
        'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': statistics or {},
        'additional_info': additional_info
    }
    
    return send_email_with_template(
        template_name='rpa_success',
        template_data=template_data,
        from_addr=from_addr,
        to_addr=to_addr,
        attachments=attachments,
        smtp_config=smtp_config
    )


def send_rpa_warning_notification(
    task_name: str,
    warning_message: str,
    from_addr: str,
    to_addr: str,
    attachments: Union[str, List[str]] = None,
    smtp_config: dict = smtp_config,
    impact_scope: str = "",
    additional_info: str = ""
) -> bool:
    """
    发送RPA警告通知邮件（便捷函数）
    
    Args:
        task_name: 任务名称
        warning_message: 警告信息
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱
        attachments: 附件路径
        smtp_config: SMTP配置
        impact_scope: 影响范围
        additional_info: 附加信息
    
    Returns:
        bool: 发送是否成功
    """
    template_data = {
        'task_name': task_name,
        'warning_message': warning_message,
        'warning_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'impact_scope': impact_scope,
        'additional_info': additional_info
    }
    
    return send_email_with_template(
        template_name='rpa_warning',
        template_data=template_data,
        from_addr=from_addr,
        to_addr=to_addr,
        attachments=attachments,
        smtp_config=smtp_config
    )


def send_rpa_report(
    task_name: str,
    from_addr: str,
    to_addr: str,
    attachments: Union[str, List[str]] = None,
    smtp_config: dict = smtp_config,
    statistics: Dict[str, Any] = None,
    summary: str = "",
    additional_info: str = ""
) -> bool:
    """
    发送RPA执行报告邮件（便捷函数）
    
    Args:
        task_name: 任务名称
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱
        attachments: 附件路径
        smtp_config: SMTP配置
        statistics: 统计信息
        summary: 执行摘要
        additional_info: 附加信息
    
    Returns:
        bool: 发送是否成功
    """
    template_data = {
        'task_name': task_name,
        'execution_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': statistics or {},
        'summary': summary,
        'additional_info': additional_info
    }
    
    return send_email_with_template(
        template_name='rpa_report',
        template_data=template_data,
        from_addr=from_addr,
        to_addr=to_addr,
        attachments=attachments,
        smtp_config=smtp_config
    )


# 保留原有函数以保持向后兼容
def send_email(
    from_addr: str, 
    to_addr: str, 
    subject: str, 
    html_content: str, 
    attachments: Union[str, List[str]] = None,
    smtp_config: dict = smtp_config
) -> bool:
    """
    发送RPA错误通知邮件
    
    Args:
        from_addr: 发件人邮箱
        to_addr: 收件人邮箱（支持多个，用逗号分隔）
        subject: 邮件主题
        html_content: HTML格式的邮件内容
        attachments: 附件路径（单个文件、文件列表或目录路径）
        smtp_config: SMTP配置字典，包含host, port, username, password, use_tls
    
    Returns:
        bool: 发送是否成功
    """
    try:
        # 验证必要参数
        if not all([from_addr, to_addr, subject, html_content]):
            logger.error("邮件发送失败：缺少必要参数")
            return False
        
        if not smtp_config:
            logger.error("邮件发送失败：缺少SMTP配置")
            return False
        
        # 创建邮件对象
        msg = MIMEMultipart('mixed', charset='utf-8')
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject
        
        # 添加HTML内容
        html_part = MIMEText(html_content, _subtype='html', _charset='utf-8')
        html_part.add_header('content-type', 'text/html',charset='utf-8')
        html_part.add_header('Content-Transfer-Encoding', 'quoted-printable', charset='utf-8')
        msg.attach(html_part)
        
        # 处理附件
        if attachments:
            attachment_files = _process_attachments(attachments)
            for file_path in attachment_files:
                if _add_attachment(msg, file_path):
                    logger.debug(f"附件添加成功: {file_path}")
                else:
                    logger.warning(f"附件添加失败: {file_path}")
        
        # 发送邮件
        return _send_mail(msg, smtp_config)
        
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        return False


def create_error_notification_html(
    task_name: str,
    error_message: str,
    error_time: str,
    impact_scope: str = "",
    additional_info: str = ""
) -> str:
    """
    创建RPA错误通知的HTML内容（保留向后兼容）
    
    Args:
        task_name: 任务名称
        error_message: 错误信息
        error_time: 错误时间
        impact_scope: 影响范围
        additional_info: 附加信息
    
    Returns:
        str: HTML格式的邮件内容
    """
    template_data = {
        'task_name': task_name,
        'error_message': error_message,
        'error_time': error_time,
        'impact_scope': impact_scope,
        'additional_info': additional_info
    }
    
    return _render_template(EMAIL_TEMPLATES['rpa_error']['html_template'], template_data)


# 内部函数保持不变
def _process_attachments(attachments: Union[str, List[str]]) -> List[str]:
    """
    处理附件路径，返回所有有效的文件路径列表
    
    Args:
        attachments: 附件路径（单个文件、文件列表或目录路径）
    
    Returns:
        List[str]: 有效的文件路径列表
    """
    file_paths = []
    
    try:
        if isinstance(attachments, str):
            if attachments != '' and attachments is not None:
                # 单个文件或目录
                path = Path(attachments)
                if path.is_file():
                    file_paths.append(str(path))
                elif path.is_dir():
                    # 目录下的所有文件
                    for file_path in path.iterdir():
                        if file_path.is_file():
                            file_paths.append(str(file_path))
                else:
                    logger.warning(f"附件路径不存在: {attachments}")
        
        elif isinstance(attachments, list):
            # 文件列表
            for attachment in attachments:
                if attachment != "" and attachment is not None:
                    path = Path(attachment)
                    if path.is_file():
                        file_paths.append(str(path))
                    else:
                        logger.warning(f"附件文件不存在: {attachment}")
        
        logger.debug(f"处理附件完成，共找到 {len(file_paths)} 个有效文件")
        return file_paths
        
    except Exception as e:
        logger.error(f"处理附件失败: {str(e)}")
        return []


def _add_attachment(msg: MIMEMultipart, file_path: str) -> bool:
    """
    向邮件添加单个附件
    
    Args:
        msg: 邮件对象
        file_path: 文件路径
    
    Returns:
        bool: 添加是否成功
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"附件文件不存在: {file_path}")
            return False
        
        # 获取文件MIME类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        # 创建附件
        with open(file_path, 'rb') as f:
            part = MIMEBase(*mime_type.split('/', 1))
            part.set_payload(f.read())
        
        # 编码附件
        encoders.encode_base64(part)
        
        # 设置附件头信息
        filename = path.name
        part.add_header(
            'Content-Disposition',
            'attachment',
            filename=filename
        )
        
        # 添加到邮件
        msg.attach(part)
        return True
        
    except Exception as e:
        logger.error(f"添加附件失败 {file_path}: {str(e)}")
        return False


def _send_mail(msg: MIMEMultipart, smtp_config: dict) -> bool:
    """
    通过SMTP发送邮件
    
    Args:
        msg: 邮件对象
        smtp_config: SMTP配置
    
    Returns:
        bool: 发送是否成功
    """
    try:
        if smtp_config is None:
            smtp_config = smtp_config
        # 获取SMTP配置
        host = smtp_config.get('host')
        port = smtp_config.get('port', 587)
        username = smtp_config.get('username')
        password = smtp_config.get('password')
        use_tls = smtp_config.get('use_tls', True)
        
        if not all([host, username, password]):
            logger.error("SMTP配置不完整")
            return False
        
        # 连接SMTP服务器
        logger.debug(f"连接SMTP服务器: {host}:{port}")
        server = smtplib.SMTP(host, port)
        
        # 启用TLS加密
        if use_tls:
            server.starttls()
        
        # 登录
        logger.debug(f"登录SMTP服务器: {username}")
        server.login(username, password)
        
        # 发送邮件
        text = msg.as_string()
        server.sendmail(msg['From'], msg['To'].split(','), text)
        
        # 关闭连接
        server.quit()
        
        logger.debug(f"邮件发送成功: {msg['To']}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP认证失败: {str(e)}")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"收件人地址无效: {str(e)}")
        return False
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"SMTP服务器连接断开: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"邮件发送异常: {str(e)}")
        return False


# 使用示例
if __name__ == "__main__":
    # SMTP配置示例
    smtp_config = {
        "host": "smtp.ah.sgcc.com.cn",
        "port": 25,
        "username": "xtgscwgk@ah.sgcc.com.cn",
        "password": "Ygsoft.1600!!",
        "use_tls": False
    }
    
    # 使用模板发送错误通知
    # success = send_rpa_error_notification(
    #     task_name="工单数据采集",
    #     error_message="网络连接超时，无法访问目标网站",
    #     from_addr="xtgscwgk@ah.sgcc.com.cn",
    #     to_addr="xtgscwgk@ah.sgcc.com.cn",
    #     attachments=[r"C:\Users\Administrator\PycharmProjects\RPA\screenshots\2025-07-09\运行日志\1、关联交易审核-培训中心（无记录）_20250709_191434.png"],
    #     smtp_config=smtp_config,
    #     impact_scope="今日工单数据未完成采集",
    #     additional_info="请检查网络连接和服务器状态"
    # )

    success = send_rpa_success_notification(
        task_name = '培训中心',
        result_message = '执行成功',
        from_addr = "xtgscwgk@ah.sgcc.com.cn",
        to_addr = "xtgscwgk@ah.sgcc.com.cn",
        attachments = [r"C:\Users\Administrator\PycharmProjects\RPA\screenshots\2025-07-09\运行日志\1、关联交易审核-培训中心（无记录）_20250709_191434.png"],
        additional_info =  "everything is ok"
    )
    print(f"邮件发送{'成功' if success else '失败'}") 