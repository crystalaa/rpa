import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter
from typing import Iterator, List, Optional, Tuple
import os
from rpa_framework.utils.robot_exception import RobotsException
from rpa_framework.utils.log import logger

class ExcelUtils:
    def __init__(self, file_path: str):
        if not file_path.lower().endswith('.xlsx'):
            raise ValueError('只支持xlsx格式的Excel文件')
        self.file_path = file_path
        self.wb = None

        try:
            self.wb = openpyxl.load_workbook(self.file_path)
        except FileNotFoundError:
            self.wb = openpyxl.Workbook()
        except Exception as e:
            raise RuntimeError(f'打开Excel文件失败: {e}')
    def iter_excel(
        self,
        sheet_name: Optional[str] = None,
        start_row: int = 1,
        columns: Optional[str] = None,
        as_display: list = None
    ) -> Iterator[Tuple[int, List]]:
        """
        读取excel每一行，返回迭代器: iterator(row_num, row:[])
        :param sheet_name: sheet名，None为活动sheet
        :param start_row: 起始行，1为第一行
        :param columns: None为所有列，格式如"A:E"为A到E列
        :param as_display: 指定列名列表，读取为Excel显示格式（字符串）
        :return: 迭代器(row_num, row:[])
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        if columns:
            col_range = columns.split(":")
            if len(col_range) == 2:
                start_col = column_index_from_string(col_range[0])
                end_col = column_index_from_string(col_range[1])
            else:
                start_col = end_col = column_index_from_string(col_range[0])
        else:
            start_col = 1
            end_col = ws.max_column
        as_display = as_display or []
        as_display_idx = set(column_index_from_string(col) - start_col for col in as_display if start_col <= column_index_from_string(col) <= end_col)
        for idx, row_cells in enumerate(ws.iter_rows(min_row=start_row, min_col=start_col, max_col=end_col), start=start_row):
            row = []
            for i, cell in enumerate(row_cells):
                if i in as_display_idx:
                    row.append(str(cell.value) if cell.value is not None else "")
                else:
                    row.append(cell.value)
            yield idx, row

    def read_excel(self, sheet_name=None, header_row=0, index_col=None, na_fill='') -> list[dict]:
        """
        读取 Excel 文件并转换为字典，同时返回原始行号

        参数:
            file_path (str): Excel 文件路径
            sheet_name (str/int, optional): 工作表名称或索引，默认为第一个工作表
            header_row (int, optional): 表头所在行索引，默认为 0
            index_col (int/str, optional): 用作索引的列，默认为 None
            na_fill (any, optional): 填充 NaN 的值，默认为空字符串

        返回:
            list[dict]: 每个字典多一个 __row__ 字段，表示原始Excel行号（从1开始）
        """
        try:
            # 读取 Excel 文件
            ws = self.wb[sheet_name] if sheet_name else self.wb.active


            # 获取表头
            headers = []
            for cell in ws[header_row + 1]:  # openpyxl行号从1开始
                headers.append(str(cell.value) if cell.value is not None else f"Column_{len(headers) + 1}")

            # 读取数据行
            records = []
            for i, row in enumerate(ws.iter_rows(min_row=header_row + 2, values_only=True), start=header_row + 2):
                # 处理缺失值
                row_data = []
                for value in row:
                    if value is None:
                        row_data.append(na_fill)
                    else:
                        row_data.append(value)

                # 创建字典
                record = dict(zip(headers, row_data))

                # 添加行号信息
                record['__row__'] = i

                records.append(record)

            return records

        except FileNotFoundError:
            raise RobotsException(f"文件 '{file_path}' 未找到")
        except Exception as e:
            raise RobotsException(f"读取excel文件错误 '{file_path}' - {str(e)}")

    def write_excel(
        self,
        data: List[List],
        sheet_name: Optional[str] = None,
        start_row: int = -1,
        start_col: str = 'A'
    ) -> None:
        """
        写入excel数据
        :param data: 二维数组
        :param sheet_name: sheet名，None为活动sheet
        :param start_row: -1为追加行，非-1为指定行
        :param start_col: 起始列，默认A
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(start_col)
        if start_row == -1:
            start_row = ws.max_row + 1 if ws.max_row > 1 or any(cell.value for cell in ws[1]) else 1
        for i, row_data in enumerate(data):
            for j, value in enumerate(row_data):
                ws.cell(row=start_row + i, column=col_idx + j, value=value)
        self.wb.save(self.file_path)

    def write_row(
        self,
        data: list,
        sheet_name: Optional[str] = None,
        start_row: int = -1,
        start_col: str = 'A'
    ) -> None:
        """
        写入一行数据
        :param data: 一维数组
        :param sheet_name: sheet名，None为活动sheet
        :param start_row: -1为追加行，非-1为指定行
        :param start_col: 起始列，默认A
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(start_col)
        if start_row == -1:
            start_row = ws.max_row + 1 if ws.max_row > 1 or any(cell.value for cell in ws[1]) else 1
        for j, value in enumerate(data):
            ws.cell(row=start_row, column=col_idx + j, value=value)
        self.wb.save(self.file_path)

    def write_col(
        self,
        data: list,
        col: str,
        start_row: int = 1,
        sheet_name: Optional[str] = None
    ) -> None:
        """
        写入一列数据
        :param data: 一维数组
        :param col: 列名，如 'A'
        :param start_row: 起始行，默认1
        :param sheet_name: sheet名，None为活动sheet
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(col)
        for i, value in enumerate(data):
            ws.cell(row=start_row + i, column=col_idx, value=value)
        self.wb.save(self.file_path)

    def write_cell(
        self,
        data,
        row: int,
        col: str,
        sheet_name: Optional[str] = None
    ) -> None:
        """
        在指定单元格写入数据
        :param data: 可以为字符、数字、日期
        :param row: 行号
        :param col: 列名，如 'A'
        :param sheet_name: sheet名，None为活动sheet
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(col)
        ws.cell(row=row, column=col_idx, value=data)
        self.wb.save(self.file_path)

    def close(self):
        if self.wb:
            self.wb.save(self.file_path)
            self.wb.close()
            self.wb = None

    def __del__(self):
        """析构函数，确保资源被正确释放"""
        self.close()

    def get_sheet_names(self) -> list:
        """返回所有sheet名称列表"""
        return self.wb.sheetnames

    def create_sheet(self, sheet_name: str, index: int = None) -> None:
        """新建sheet，可指定插入位置"""
        self.wb.create_sheet(title=sheet_name, index=index)
        self.wb.save(self.file_path)

    def remove_sheet(self, sheet_name: str) -> None:
        """删除指定sheet"""
        if sheet_name in self.wb.sheetnames:
            ws = self.wb[sheet_name]
            self.wb.remove(ws)
            self.wb.save(self.file_path)

    def read_cell(self, row: int, col: str, sheet_name: Optional[str] = None, as_display: Optional[bool] = False):
        """读取指定单元格的值，as_display为True时返回Excel显示格式（字符串）"""
        # logger.debug(f"{sheet_name=}")
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(col)
        cell = ws.cell(row=row, column=col_idx)
        if as_display:
            return str(cell.value) if cell.value is not None else ""
        return cell.value

    def get_max_row(self, sheet_name: str = None, col: str = None) -> int:
        """
        获取最大行号，若指定col则返回该列非空的最大行号
        :param sheet_name: sheet名，None为活动sheet
        :param col: 列名，如 'A'，默认None返回整表最大行号
        :return: 最大行号
        """
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        if col is None:
            return ws.max_row
        col_idx = column_index_from_string(col)
        max_row = ws.max_row
        for row in range(max_row, 0, -1):
            if ws.cell(row=row, column=col_idx).value not in (None, ''):
                return row
        return 0

    def get_max_col(self, sheet_name: str = None) -> int:
        """获取最大列号"""
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        return ws.max_column

    def copy_sheet(self, from_sheet: str, to_sheet: str) -> None:
        """复制sheet内容到新sheet"""
        ws_from = self.wb[from_sheet]
        ws_to = self.wb.copy_worksheet(ws_from)
        ws_to.title = to_sheet
        self.wb.save(self.file_path)

    def set_cell_style(self, row: int, col: str, font=None, fill=None, sheet_name: str = None):
        """设置单元格样式"""
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        col_idx = column_index_from_string(col)
        cell = ws.cell(row=row, column=col_idx)
        if font:
            cell.font = font
        if fill:
            cell.fill = fill
        self.wb.save(self.file_path)

    def merge_cells(self, range_str: str, sheet_name: str = None):
        """合并单元格，如 'A1:C1'"""
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        ws.merge_cells(range_str)
        self.wb.save(self.file_path)

    def unmerge_cells(self, range_str: str, sheet_name: str = None):
        """取消合并单元格"""
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        ws.unmerge_cells(range_str)
        self.wb.save(self.file_path)

    def read_multiple_sheets(excel_utils, sheet_configs: dict) -> dict:
        """
        读取多个工作表的数据
        参数:
            sheet_configs (dict): 工作表配置字典，格式为 {
                'sheet_name': {'header_row': 0, 'index_col': None, 'na_fill': ''}
            }
        返回:
            dict: 以工作表名为键，数据列表为值的字典
        示例:
            sheet_configs = {
                '登录信息': {'header_row': 0},
                '单位信息': {'header_row': 0},
                '核算科目': {'header_row': 0}
            }
            data = excel_utils.read_multiple_sheets(sheet_configs)
        """
        result = {}

        try:
            for sheet_name, config in sheet_configs.items():
                if sheet_name not in excel_utils.wb.sheetnames:
                    logger.warning(f"工作表 '{sheet_name}' 不存在")
                    result[sheet_name] = []
                    continue

                header_row = config.get('header_row', 0)
                index_col = config.get('index_col', None)
                na_fill = config.get('na_fill', '')

                ws = excel_utils.wb[sheet_name]

                # 获取表头
                headers = []
                for cell in ws[header_row + 1]:  # openpyxl行号从1开始
                    headers.append(str(cell.value) if cell.value is not None else f"Column_{len(headers) + 1}")

                # 读取数据行
                records = []
                for i, row in enumerate(ws.iter_rows(min_row=header_row + 2, values_only=True), start=header_row + 2):
                    # 处理缺失值
                    row_data = []
                    for value in row:
                        if value is None:
                            row_data.append(na_fill)
                        else:
                            row_data.append(value)

                    # 创建字典
                    record = dict(zip(headers, row_data))

                    # 添加行号信息
                    record['__row__'] = i

                    records.append(record)

                result[sheet_name] = records

            return result

        except Exception as e:
            raise RobotsException(f"读取多个工作表数据错误 - {str(e)}")