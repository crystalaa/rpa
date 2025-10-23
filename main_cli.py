#!/usr/bin/env python3
"""
RPA 应用程序CLI入口
适用于使用 rpa-framework 包的新工程
"""

import sys


def main():
    """主函数"""
    try:
        # 导入 rpa-framework 的 CLI 入口
        from rpa_framework.main_cli import main as rpa_cli_main
        rpa_cli_main()
    except ImportError as e:
        print(f"导入 rpa-framework 失败: {e}")
        print("请确保已安装 rpa-framework: pip install rpa-framework")
        sys.exit(1)
    except Exception as e:
        print(f"程序运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 