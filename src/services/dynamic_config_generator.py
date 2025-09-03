#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动态配置生成器模块

负责在对战开始时，为两个模型动态地、随机地组合和创建SillyTavernOdysseia的运行配置。
"""

import os
import random
import uuid
from pathlib import Path
from typing import Tuple, Optional, List

from SillyTavernOdysseia.src.services.config_manager import ConfigManager as SillyTavernConfigManager
from src.utils.logger_config import logger
from src.utils import config

class DynamicConfigGenerator:
    """
    动态生成对战所需的SillyTavern配置。
    """
    def __init__(self, data_root: str = "SillyTavernOdysseia/data"):
        """
        初始化动态配置生成器。

        Args:
            data_root (str): SillyTavernOdysseia数据目录的根路径。
        """
        self.st_config_manager = SillyTavernConfigManager(data_root=data_root)
        self.presets_dir = Path(data_root) / "presets"
        self.characters_dir = Path(data_root) / "characters"
        self.world_books_dir = Path(data_root) / "world_books"

    def _get_random_file(self, directory: Path) -> Optional[str]:
        """从指定目录随机选择一个 .json 文件。"""
        try:
            files = [f.name for f in directory.glob("*.json") if f.is_file()]
            if not files:
                logger.warning(f"目录 {directory} 中没有找到 .json 文件。")
                return None
            return random.choice(files)
        except Exception as e:
            logger.error(f"从目录 {directory} 随机选择文件时出错: {e}", exc_info=True)
            return None

    def _get_two_different_presets(self, model_a_id: str, model_b_id: str) -> Tuple[Optional[str], Optional[str]]:
        """从每个模型的可用预设列表中，为它们分别随机选择一个不同的预设。"""
        mapping = config.get_model_preset_mapping()
        default_presets = mapping.get("default", [])

        presets_a = mapping.get(model_a_id, default_presets)
        presets_b = mapping.get(model_b_id, default_presets)

        if not presets_a or not presets_b:
            logger.error(f"模型 {model_a_id} 或 {model_b_id} 没有可用的预设列表，且无默认预设。")
            return None, None

        preset_a = random.choice(presets_a)
        preset_b = random.choice(presets_b)

        # 如果两个模型共享同一个预设列表且该列表只有一个元素，则它们只能选择相同的预设
        if preset_a == preset_b and len(set(presets_a) | set(presets_b)) == 1:
             logger.warning(f"模型 {model_a_id} 和 {model_b_id} 只能选择同一个预设 '{preset_a}'。")
             return preset_a, preset_b

        # 尽力确保预设不同
        max_retries = 10
        for _ in range(max_retries):
            if preset_a != preset_b:
                break
            preset_b = random.choice(presets_b)
        
        if preset_a == preset_b:
            logger.warning(f"多次尝试后，模型 {model_a_id} 和 {model_b_id} 仍然选择了相同的预设 '{preset_a}'。")

        return preset_a, preset_b

    def generate_configs_for_battle(self, model_a_id: str, model_b_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        为一场对战生成两个独立的配置文件。

        逻辑：
        1. 随机选择一个角色卡和一个世界书，两者共用。
        2. 随机选择两个不同的预设，每个模型一个。
        3. 为模型A和模型B分别创建并保存一个配置文件。
        4. 返回两个配置文件的ID。

        Args:
            model_a_id (str): 模型A的ID。
            model_b_id (str): 模型B的ID。

        Returns:
            Tuple[Optional[str], Optional[str]]: 一个包含两个新配置ID的元组 (config_id_a, config_id_b)，如果失败则为 (None, None)。
        """
        logger.info(f"开始为模型 {model_a_id} 和 {model_b_id} 生成动态配置...")

        # 1. 选择公共组件
        character_file = self._get_random_file(self.characters_dir)
        world_book_file = self._get_random_file(self.world_books_dir)
        
        if not character_file:
            logger.error("无法选择角色卡，配置生成失败。")
            return None, None

        # 2. 为每个模型选择不同的预设
        preset_a, preset_b = self._get_two_different_presets(model_a_id, model_b_id)
        if not preset_a or not preset_b:
            logger.error("无法为模型选择两个不同的预设，配置生成失败。")
            return None, None

        logger.info(f"选定的组件: 角色卡='{character_file}', 世界书='{world_book_file}', 预设A='{preset_a}', 预设B='{preset_b}'")

        try:
            # 3. 为模型A创建配置
            config_id_a = f"arena_battle_{uuid.uuid4().hex[:8]}"
            config_a = self.st_config_manager.create_config(
                config_id=config_id_a,
                name=f"Arena Battle - {model_a_id}",
                description=f"Dynamically generated config for model {model_a_id}",
                character_file=character_file,
                additional_world_book=world_book_file,
                preset_file=preset_a
            )
            self.st_config_manager.save_config(config_a)
            logger.info(f"已为模型A创建并保存配置: {config_id_a}")

            # 4. 为模型B创建配置
            config_id_b = f"arena_battle_{uuid.uuid4().hex[:8]}"
            config_b = self.st_config_manager.create_config(
                config_id=config_id_b,
                name=f"Arena Battle - {model_b_id}",
                description=f"Dynamically generated config for model {model_b_id}",
                character_file=character_file,
                additional_world_book=world_book_file,
                preset_file=preset_b
            )
            self.st_config_manager.save_config(config_b)
            logger.info(f"已为模型B创建并保存配置: {config_id_b}")

            return config_id_a, config_id_b

        except Exception as e:
            logger.error(f"创建或保存动态配置过程中出错: {e}", exc_info=True)
            return None, None

# 全局实例，方便调用
dynamic_config_generator = DynamicConfigGenerator()