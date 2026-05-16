#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径管理器
用于处理不同环境下的文件路径，支持开发环境和安装环境的路径查找
"""
import os,sys
from pathlib import Path
import importlib.resources as pkg_resources
from rpa_framework.utils.log import logger

class PathManager:
    """路径管理器"""
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self._app_src_root = Path(sys._MEIPASS)
        else:
            self._app_src_root = Path.cwd()

        self._app_root = Path.cwd()

    @property
    def app_root(self) -> Path:
        return self._app_root

    @property
    def app_src_root(self) -> Path:
        return self._app_src_root

    def get_config_path(self, filename: str) -> Path:
        # 优先新工程目录
        project_config = self.app_root / "config" / filename
        if project_config.exists():
            return project_config

        # 根据环境选择不同的 fallback 策略
        import sys

        if getattr(sys, 'frozen', False):
            # PyInstaller 环境
            try:
                # 查找 _internal 目录
                internal_path = Path(sys._MEIPASS) / "rpa_framework" / "config" / filename
                if internal_path.exists():
                    return internal_path
            except Exception as e:
                logger.warning(f"PyInstaller 环境下无法找到配置文件 {filename}: {e}")

        else:
            # 开发环境或 pip 安装环境
            try:
                # 查找 data-files
                import pkg_resources
                data_files_path = Path(pkg_resources.resource_filename('rpa_framework', f'../config/{filename}'))
                if data_files_path.exists():
                    return data_files_path
            except Exception as e:
                logger.warning(f"无法找到默认配置文件 {filename}: {e}")

        return project_config

    def get_data_path(self, filename: str) -> Path:
        project_data = self.app_root / "data" / filename
        if project_data.exists():
            return project_data
        try:
            with pkg_resources.path('rpa_framework.data', filename) as p:
                return Path(p)
        except Exception as e:
            logger.warning(f"无法找到默认数据文件 {filename}: {e}")
            return project_data

    def get_doc_path(self, filename: str) -> Path:
        project_doc = self.app_root / "docs" / filename
        if project_doc.exists():
            return project_doc
        try:
            with pkg_resources.path('rpa_framework.docs', filename) as p:
                return Path(p)
        except Exception as e:
            logger.warning(f"无法找到默认文档文件 {filename}: {e}")
            return project_doc

    def get_ui_resource_path(self, filename: str) -> Path:
        project_resource = self.app_root / "ui" / "resources" / filename
        if project_resource.exists():
            return project_resource
        try:
            with pkg_resources.path('rpa_framework.ui.resources', filename) as p:
                return Path(p)
        except Exception as e:
            logger.warning(f"无法找到默认UI资源文件 {filename}: {e}")
            return project_resource

    def get_robot_path(self, filename: str) -> Path:
        project_robot = self.app_root / "robots" / filename
        if project_robot.exists():
            return project_robot
        try:
            with pkg_resources.path('rpa_framework.robots', filename) as p:
                return Path(p)
        except Exception as e:
            logger.warning(f"无法找到默认机器人文件 {filename}: {e}")
            return project_robot

    def ensure_project_dirs(self):
        dirs = [
            self.app_root / "config",
            self.app_root / "data",
            self.app_root / "docs",
            self.app_root / "ui" / "resources",
            self.app_root / "robots",
            self.app_root / "logs",
            self.app_root / "screenshots",
            self.app_root / "videos"
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"确保目录存在: {dir_path}")

    def copy_default_files(self):
        import shutil
        # 复制默认配置文件
        default_configs = ["config.json", "selectors.json", "test.json", "workorder_field_mapping.json"]
        for config_file in default_configs:
            try:
                with pkg_resources.path('rpa_framework.config', config_file) as src:
                    dst = self.app_root / "config" / config_file
                    if not dst.exists():
                        shutil.copy2(src, dst)
                        logger.info(f"复制默认配置文件: {config_file}")
            except Exception as e:
                logger.warning(f"无法复制默认配置文件 {config_file}: {e}")
        # 复制默认文档
        default_docs = ["暂无文档.html"]
        for doc_file in default_docs:
            try:
                with pkg_resources.path('rpa_framework.docs', doc_file) as src:
                    dst = self.app_root / "docs" / doc_file
                    if not dst.exists():
                        shutil.copy2(src, dst)
                        logger.info(f"复制默认文档: {doc_file}")
            except Exception as e:
                logger.warning(f"无法复制默认文档 {doc_file}: {e}")

path_manager = PathManager()
