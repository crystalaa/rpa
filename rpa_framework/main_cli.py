#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPA框架 - CLI主入口
"""

import sys
import os
import traceback
import argparse
from pathlib import Path

from rpa_framework.utils.config import config
from rpa_framework.utils.log import logger
from rpa_framework.utils.menu_config import register_all_methods, get_robot_data, menu_manager


def load_custom_robot(robot_file_path: str):
    """动态加载自定义robot文件"""
    try:
        import importlib.util
        import sys
        import os
        from pathlib import Path
        
        # 检查文件是否存在
        if not os.path.exists(robot_file_path):
            raise ValueError(f"Robot文件不存在: {robot_file_path}")
        
        # 检查文件扩展名
        if not robot_file_path.endswith('.py'):
            raise ValueError(f"Robot文件必须是Python文件(.py): {robot_file_path}")
        
        # 获取robot文件所在的目录
        robot_dir = Path(robot_file_path).parent
        robot_file_name = Path(robot_file_path).name
        
        # 将robot文件所在目录添加到sys.path，以支持相对导入
        if str(robot_dir) not in sys.path:
            sys.path.insert(0, str(robot_dir))
        
        # 检查是否在打包环境中运行，如果是，添加_internal/src路径
        if hasattr(sys, '_MEIPASS'):  # type: ignore
            # 在PyInstaller打包环境中
            internal_src_path = os.path.join(sys._MEIPASS, 'src')  # type: ignore
            if os.path.exists(internal_src_path) and internal_src_path not in sys.path:
                sys.path.insert(0, internal_src_path)
        else:
            # 在开发环境中，添加项目根目录
            project_root = Path(__file__).parent.parent
            src_path = project_root / 'src'
            if src_path.exists() and str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
        
        # 获取模块名称（去掉.py扩展名）
        module_name = robot_file_name.replace('.py', '')
        
        # 创建模块规范
        spec = importlib.util.spec_from_file_location(module_name, robot_file_path)
        if spec is None:
            raise ValueError(f"无法创建模块规范，请检查文件格式: {robot_file_path}")
        
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise ValueError(f"模块加载器为空，文件可能损坏: {robot_file_path}")
        
        # 将模块添加到sys.modules，以便相对导入能够正常工作
        sys.modules[module_name] = module
        
        # 执行模块
        spec.loader.exec_module(module)
        
        # 验证是否包含main函数
        if not hasattr(module, 'main'):
            raise ValueError(f"Robot文件必须包含main函数: {robot_file_path}")
        
        return module.main
    except ImportError as e:
        raise ValueError(f"导入错误，请检查依赖模块: {str(e)}")
    except SyntaxError as e:
        raise ValueError(f"Python语法错误: {str(e)}")
    except Exception as e:
        if "无法创建模块规范" in str(e):
            raise ValueError(f"模块加载失败，请检查文件路径和格式: {robot_file_path}")
        raise ValueError(f"加载自定义robot文件失败: {str(e)}")

def create_parser():
    """创建命令行参数解析器"""
    # 注册所有方法映射
    register_all_methods()
    
    # 获取robot选择列表
    robot_choices = menu_manager.get_robot_choices()
    robots_info = menu_manager.get_robots_info()
    
    epilog = f"""
使用示例:
  # 显示帮助信息
  %(prog)s -h

  # 银行账户补采（显示浏览器 + 录屏）
  %(prog)s -b -v -r bank_account_collector -i "D:\\data\\银行账号补采.xlsx"

  # 银行账户补采（后台运行）
  %(prog)s -r bank_account_collector -i "D:\\data\\银行账号补采.xlsx"

  # 陕西监控（调试模式，单步执行）
  %(prog)s -d -b -r shanxi_jiankong -i "D:\\data\\陕西监控.xlsx"

  # 影刀订单采集（显示浏览器）
  %(prog)s -b -r yingdao_order_collector

  # 影刀订单采集（后台运行 + 录屏）
  %(prog)s -v -r yingdao_order_collector

  # 自定义robot文件（显示浏览器）
  %(prog)s -r custom -f "D:\\test_robot.py" -b

  # 自定义robot文件（后台运行 + 录屏）
  %(prog)s -r custom -f "D:\\test_robot.py" -v

  # 自定义robot文件（带输入文件）
  %(prog)s -r custom -f "D:\\test_robot.py" -i "D:\\input.xlsx" -b

可用的Robots列表:
  名称                      代码
  -----------------------------------------------
{robots_info}

"""
    
    parser = argparse.ArgumentParser(
        description='RPA自动化工具 - 命令行版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    
    parser.add_argument('-r', '--robot', 
                       choices=robot_choices,
                       help='要运行的robot代码',
                       required=True)
    
    # 新增自定义robot文件参数
    parser.add_argument('-f', '--robot-file',
                       type=str,
                       help='自定义robot文件路径（当-r为custom时必需）')
    
    parser.add_argument('-b', '--show-browser', 
                       action='store_true',
                       help='显示浏览器窗口（默认为隐藏）')
    
    parser.add_argument('-v', '--record-video', 
                       action='store_true',
                       help='录制屏幕视频（默认不录制）')
    
    parser.add_argument('-d', '--debug', 
                       action='store_true',
                       help='启用调试模式，程序将在关键步骤暂停等待用户确认')
    
    parser.add_argument('-i', '--input-file', 
                       type=str,
                       help='输入文件路径（对于bank_account_collector必需）')
    
    return parser

def run_robot(args):
    """运行指定的robot"""
    try:
        logger.info(f"命令行模式启动 - Robot: {args.robot}")
        
        # 处理自定义robot
        if args.robot == 'custom':
            if not args.robot_file:
                raise ValueError("使用custom模式时必须指定robot文件路径 (-f)")
            
            robot_file_path = Path(args.robot_file)
            if not robot_file_path.exists():
                raise ValueError(f"Robot文件不存在: {args.robot_file}")
            
            # 动态加载自定义robot
            try:
                robot_method = load_custom_robot(str(robot_file_path))
            except ValueError as e:
                # 重新抛出更友好的错误信息
                raise ValueError(f"自定义Robot加载失败: {str(e)}")
            
            # 准备参数
            kwargs = {
                'show_browser': args.show_browser,
                'record_video': args.record_video,
                'debug_mode': args.debug
            }
            
            # 如果有输入文件，添加到参数中
            if args.input_file:
                input_path = Path(args.input_file)
                if not input_path.exists():
                    raise ValueError(f"输入文件不存在: {args.input_file}")
                kwargs['input_file'] = str(input_path.absolute())
            
            logger.info(f"准备执行自定义robot: {args.robot_file}")
            logger.debug(f"执行参数: {kwargs}")
            
            # 执行自定义robot
            result = robot_method(**kwargs)
            
            logger.info(f"自定义Robot执行完成: {args.robot_file}")
            if isinstance(result, dict):
                logger.info(f"执行结果: {result}")
            
        else:
            # 从配置中获取robot配置
            robot_config = menu_manager.get_robot_by_code(args.robot)
            
            if not robot_config:
                raise ValueError(f"未找到robot配置: {args.robot}")
            
            # 准备参数
            kwargs = {
                'show_browser': args.show_browser,
                'record_video': args.record_video,
                'debug_mode': args.debug
            }
            
            # 根据不同的robot添加特定参数
            if args.robot == 'bank_account_collector':
                if not args.input_file:
                    raise ValueError("bank_account_collector需要输入文件，请使用 -i 参数指定")
                
                input_path = Path(args.input_file)
                if not input_path.exists():
                    raise ValueError(f"输入文件不存在: {args.input_file}")
                
                kwargs['input_file'] = str(input_path.absolute())
                
            elif args.robot == 'yingdao_order_collector':
                # 影刀订单采集的默认参数
                kwargs.update({
                    'username': 'admin',
                    'password': '58T2$!hm',
                    'order_name': '短袖T恤'
                })
            elif args.robot == 'shanxi_jiankong':
                # 陕西监控需要输入文件
                if not args.input_file:
                    raise ValueError("shanxi_jiankong需要输入文件，请使用 -i 参数指定")
                
                input_path = Path(args.input_file)
                if not input_path.exists():
                    raise ValueError(f"输入文件不存在: {args.input_file}")
                
                kwargs['input_file'] = str(input_path.absolute())
            
            logger.info(f"准备执行robot: {args.robot}")
            logger.debug(f"执行参数: {kwargs}")
            
            # 执行robot
            result = robot_config["method"](**kwargs)
            
            logger.info(f"Robot执行完成: {args.robot}")
            if isinstance(result, dict):
                logger.info(f"执行结果: {result}")
        
        return 0
        
    except Exception as e:
        error_msg = f"Robot执行失败: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        print(f"错误: {str(e)}")
        return 1

def main():
    """主函数"""
    try:
        # 创建解析器并解析参数
        parser = create_parser()
        
        # 检查是否有命令行参数
        if len(sys.argv) == 1:
            # 没有参数时显示帮助信息
            parser.print_help()
            return 0
        
        args = parser.parse_args()
        
        # 运行指定的robot
        return run_robot(args)
        
    except KeyboardInterrupt:
        logger.info("用户中断执行")
        return 0
    except Exception as e:
        error_msg = f"程序执行错误: {str(e)}\n{traceback.format_exc()}"
        try:
            logger.error(error_msg)
        except Exception:
            print(f"程序执行失败：{error_msg}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 