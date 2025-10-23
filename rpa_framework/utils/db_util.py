import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, List, Tuple, Any, Optional
from rpa_framework.utils.log import logger
from rpa_framework.utils.config import config
from rpa_framework.utils.robot_exception import RobotsException


class DatabaseManager:
    """数据库管理类，负责所有数据库相关操作"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库管理器
        
        Args:
            db_path (str): 数据库文件路径
        """
        if not db_path:
            raise RobotsException('数据库路径不能为空')
        self.db_path = db_path
        logger.debug(f'数据库路径: {self.db_path}')
    
    def check_database_exists(self) -> bool:
        """
        检查数据库和表是否存在
        
        Returns:
            bool: 数据库和表是否存在
        """
        try:
            if not os.path.exists(self.db_path):
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查work_orders表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='work_orders'
            """)
            table_exists = cursor.fetchone() is not None
            
            conn.close()
            return table_exists
        except Exception as e:
            logger.warning(f"检查数据库存在性失败: {str(e)}")
            return False
    
    def init_database(self) -> None:
        """
        初始化数据库（仅在需要时）
        
        Raises:
            RobotsException: 数据库初始化失败时抛出异常
        """
        try:
            # 确保data目录存在
            os.makedirs("data", exist_ok=True)
            
            # 检查数据库是否已存在
            if self.check_database_exists():
                logger.debug("数据库已存在，跳过初始化")
                return
            
            logger.info("数据库不存在或不完整，开始初始化...")
            
            # 创建数据库连接
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 读取并执行DDL
            ddl_file_path = "data/workorder.sql"
            if not os.path.exists(ddl_file_path):
                raise FileNotFoundError(f"DDL文件不存在: {ddl_file_path}")
            
            with open(ddl_file_path, "r", encoding="utf-8") as f:
                ddl_content = f.read()
                # 执行DDL中的所有语句
                cursor.executescript(ddl_content)
            
            conn.commit()
            conn.close()
            
            # 验证初始化结果
            if self.check_database_exists():
                logger.info("数据库初始化成功")
            else:
                raise Exception("数据库初始化后验证失败")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            raise RobotsException(f"数据库初始化失败: {str(e)}", e)
    
    def get_existing_work_order_numbers(self, days_back: int = 10) -> Set[str]:
        """
        获取数据库中已存在的工单号（仅查询最近N天）
        
        Args:
            days_back (int): 查询最近多少天的数据，默认10天
            
        Returns:
            Set[str]: 已存在的工单号集合
            
        Raises:
            RobotsException: 查询失败时抛出异常
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算N天前的日期
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # 查询最近N天的工单号（基于created_at字段）
            query = """
                SELECT work_order_number 
                FROM work_orders 
                WHERE DATE(created_at) >= ? 
            """
            
            cursor.execute(query, (cutoff_date,))
            existing_numbers = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            logger.debug(f"数据库中最近{days_back}天已存在 {len(existing_numbers)} 个工单")
            return existing_numbers
        except Exception as e:
            logger.error(f"查询已存在工单号失败: {str(e)}")
            raise RobotsException(f"查询已存在工单号失败: {str(e)}", e)
    
    def insert_workorders(self, mapped_data: List[Tuple], db_fields: List[str]) -> int:
        """
        插入工单数据到数据库
        
        Args:
            mapped_data (List[Tuple]): 映射后的数据列表
            db_fields (List[str]): 数据库字段名列表
            
        Returns:
            int: 插入的记录数
            
        Raises:
            RobotsException: 插入失败时抛出异常
        """
        try:
            if not mapped_data:
                logger.debug("没有有效的数据需要插入")
                return 0
            
            conn = sqlite3.connect(self.db_path)
            
            # 动态生成插入SQL
            placeholders = ', '.join(['?' for _ in db_fields])
            field_names = ', '.join(db_fields)
            insert_sql = f"INSERT INTO work_orders ({field_names}) VALUES ({placeholders})"
            
            cursor = conn.cursor()
            cursor.executemany(insert_sql, mapped_data)
            conn.commit()
            
            inserted_count = cursor.rowcount
            conn.close()
            
            logger.debug(f"成功插入 {inserted_count} 条新工单数据")
            return inserted_count
            
        except Exception as e:
            logger.error(f"插入工单数据失败: {str(e)}")
            raise RobotsException(f"插入工单数据失败: {str(e)}", e)
    
    def save_workorders_with_deduplication(self, mapped_data: List[Tuple], db_fields: List[str], 
                                         existing_numbers: Set[str], work_order_column_index: int = 0) -> int:
        """
        保存工单数据到数据库（带去重）
        
        Args:
            mapped_data (List[Tuple]): 映射后的数据列表
            db_fields (List[str]): 数据库字段名列表
            existing_numbers (Set[str]): 已存在的工单号集合
            work_order_column_index (int): 工单号在数据中的列索引，默认0
            
        Returns:
            int: 实际插入的记录数
        """
        try:
            if not mapped_data:
                logger.debug("没有数据需要保存")
                return 0
            
            # 过滤出新的工单
            new_data = []
            for row in mapped_data:
                if len(row) > work_order_column_index:
                    work_order_number = row[work_order_column_index]
                    if work_order_number not in existing_numbers:
                        new_data.append(row)
            
            if len(new_data) == 0:
                logger.debug("没有新的工单需要插入")
                return 0


            # 插入新数据
            return self.insert_workorders(new_data, db_fields)
            
        except Exception as e:
            logger.error(f"保存工单数据失败: {str(e)}")
            raise RobotsException(f"保存工单数据失败: {str(e)}", e)
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        执行查询语句
        
        Args:
            query (str): SQL查询语句
            params (Optional[Tuple]): 查询参数
            
        Returns:
            List[Tuple]: 查询结果
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            conn.close()
            
            return results
        except Exception as e:
            logger.error(f"执行查询失败: {str(e)}")
            raise RobotsException(f"执行查询失败: {str(e)}", e)
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行更新语句
        
        Args:
            query (str): SQL更新语句
            params (Optional[Tuple]): 更新参数
            
        Returns:
            int: 影响的行数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            
            return affected_rows
        except Exception as e:
            logger.error(f"执行更新失败: {str(e)}")
            raise RobotsException(f"执行更新失败: {str(e)}", e)
    
    def delete_workorders_by_numbers(self, work_order_numbers: List[str]) -> int:
        """
        根据工单号列表删除工单记录
        
        Args:
            work_order_numbers (List[str]): 要删除的工单号列表
            
        Returns:
            int: 删除的记录数
            
        Raises:
            RobotsException: 删除失败时抛出异常
        """
        try:
            if not work_order_numbers:
                logger.debug("没有工单号需要删除")
                return 0
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建删除SQL，使用IN子句批量删除
            placeholders = ', '.join(['?' for _ in work_order_numbers])
            delete_sql = f"DELETE FROM work_orders WHERE work_order_number IN ({placeholders})"
            
            cursor.execute(delete_sql, work_order_numbers)
            conn.commit()
            
            deleted_count = cursor.rowcount
            conn.close()
            
            logger.debug(f"成功删除 {deleted_count} 条工单记录")
            return deleted_count
            
        except Exception as e:
            logger.error(f"删除工单记录失败: {str(e)}")
            raise RobotsException(f"删除工单记录失败: {str(e)}", e) 