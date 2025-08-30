#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块

负责管理聊天配置组合，包括：
- 预设、角色卡、玩家卡、通用世界书的组合
- 配置的保存、加载、切换
- 文件路径管理和验证
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .chat_history_manager import ChatHistoryManager, create_chat_manager


@dataclass
class ChatConfig:
    """聊天配置数据类"""
    config_id: str
    name: str
    description: str = ""
    components: Dict[str, Optional[str]] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.configs_dir = self.data_root / "configs"
        self.presets_dir = self.data_root / "presets"
        self.characters_dir = self.data_root / "characters"
        self.personas_dir = self.data_root / "personas"
        self.world_books_dir = self.data_root / "world_books"
        
        # 确保目录存在
        self._ensure_directories()
        
        # 当前配置
        self.current_config: Optional[ChatConfig] = None
        self.current_manager: Optional[ChatHistoryManager] = None
    
    def _ensure_directories(self) -> None:
        """确保所有必要目录存在"""
        for directory in [self.configs_dir, self.presets_dir, self.characters_dir, 
                         self.personas_dir, self.world_books_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def create_config(self, config_id: str, name: str, description: str = "",
                     preset_file: Optional[str] = None,
                     character_file: Optional[str] = None,
                     persona_file: Optional[str] = None,
                     additional_world_book: Optional[str] = None,
                     tags: Optional[List[str]] = None) -> ChatConfig:
        """创建新的聊天配置"""
        
        # 验证文件路径
        components = {}
        if preset_file:
            components["preset"] = self._validate_file_path(preset_file, self.presets_dir)
        if character_file:
            components["character"] = self._validate_file_path(character_file, self.characters_dir)
        if persona_file:
            components["persona"] = self._validate_file_path(persona_file, self.personas_dir)
        if additional_world_book:
            components["additional_world_book"] = self._validate_file_path(additional_world_book, self.world_books_dir)
        
        config = ChatConfig(
            config_id=config_id,
            name=name,
            description=description,
            components=components,
            tags=tags or []
        )
        
        return config
    
    def _validate_file_path(self, file_path: str, base_dir: Path) -> str:
        """验证文件路径是否存在，返回文件名"""
        # 支持相对路径和绝对路径
        if os.path.isabs(file_path):
            full_path = Path(file_path)
        else:
            # 如果已经包含目录前缀，直接相对于data_root
            if "/" in file_path or "\\" in file_path:
                full_path = self.data_root / file_path
            else:
                # 否则相对于指定的base_dir
                full_path = base_dir / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {full_path}")
        
        # 只返回文件名，不包含路径
        return full_path.name
    
    def save_config(self, config: ChatConfig) -> None:
        """保存配置到文件"""
        config_file = self.configs_dir / f"{config.config_id}.json"
        
        config_data = {
            "config_id": config.config_id,
            "name": config.name,
            "description": config.description,
            "components": config.components,
            "tags": config.tags,
            "created_date": config.created_date,
            "last_used": config.last_used
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 配置已保存: {config_file}")
    
    def load_config(self, config_id: str) -> ChatConfig:
        """从文件加载配置"""
        config_file = self.configs_dir / f"{config_id}.json"
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        config = ChatConfig(
            config_id=config_data["config_id"],
            name=config_data["name"],
            description=config_data.get("description", ""),
            components=config_data.get("components", {}),
            tags=config_data.get("tags", []),
            created_date=config_data.get("created_date", ""),
            last_used=config_data.get("last_used", "")
        )
        
        return config
    
    def list_configs(self) -> List[ChatConfig]:
        """列出所有配置"""
        configs = []
        
        for config_file in self.configs_dir.glob("*.json"):
            try:
                config_id = config_file.stem
                config = self.load_config(config_id)
                configs.append(config)
            except Exception as e:
                print(f"⚠️ 加载配置失败: {config_file} - {e}")
        
        # 按最后使用时间排序
        configs.sort(key=lambda x: x.last_used, reverse=True)
        return configs
    
    def delete_config(self, config_id: str) -> None:
        """删除配置"""
        config_file = self.configs_dir / f"{config_id}.json"
        
        if config_file.exists():
            config_file.unlink()
            print(f"✅ 配置已删除: {config_id}")
        else:
            print(f"⚠️ 配置不存在: {config_id}")
    
    def load_chat_manager(self, config: ChatConfig) -> ChatHistoryManager:
        """根据配置加载ChatHistoryManager"""
        
        # 加载角色卡数据
        character_data = {}
        if "character" in config.components:
            character_path = self.characters_dir / config.components["character"]
            with open(character_path, "r", encoding="utf-8") as f:
                character_data = json.load(f)
        
        # 加载预设数据
        preset_data = {}
        if "preset" in config.components:
            preset_path = self.presets_dir / config.components["preset"]
            with open(preset_path, "r", encoding="utf-8") as f:
                preset_data = json.load(f)
        
        # 加载玩家卡数据
        persona_data = {}
        if "persona" in config.components:
            persona_path = self.personas_dir / config.components["persona"]
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_data = json.load(f)

        # 创建基础管理器
        manager = create_chat_manager(character_data, preset_data, persona_data)
        
        # 加载通用世界书（如果有）
        if "additional_world_book" in config.components:
            world_book_path = self.world_books_dir / config.components["additional_world_book"]
            with open(world_book_path, "r", encoding="utf-8") as f:
                world_book_data = json.load(f)
            
            # 合并通用世界书到管理器
            self._merge_additional_world_book(manager, world_book_data)
        
        return manager
    
    def _merge_additional_world_book(self, manager: ChatHistoryManager, world_book_data: Dict[str, Any]) -> None:
        """将通用世界书合并到管理器中"""
        if "world_book" not in world_book_data:
            return
        
        additional_world_book = world_book_data["world_book"]
        if "entries" not in additional_world_book:
            return
        
        # 获取当前最大的ID，避免冲突
        max_id = 0
        for entry in manager.world_book_entries:
            max_id = max(max_id, entry.id)
        
        # 添加通用世界书条目
        for entry_data in additional_world_book["entries"]:
            # 分配新的ID避免冲突
            max_id += 1
            entry_data["id"] = max_id
            
            from .chat_history_manager import WorldBookEntry
            # 提取排序字段：优先使用insertion_order，最后是默认值
            order = entry_data.get("insertion_order", 100)
            
            # 提取enabled表达式
            enabled_expr = entry_data.get("enabled", True)
                
            entry = WorldBookEntry(
                id=entry_data.get("id", max_id),
                name=entry_data.get("name", ""),
                enabled=True,  # 初始值，运行时动态计算
                mode=entry_data.get("mode", "conditional"),
                position=entry_data.get("position", "before_char"),
                keys=entry_data.get("keys", []),
                content=entry_data.get("content", ""),
                depth=entry_data.get("depth"),
                order=order,
                code_block=entry_data.get("code_block"),  # 代码块
                enabled_expression=enabled_expr,  # 保存原始表达式
                enabled_cached=None
            )
            manager.world_book_entries.append(entry)
        
        print(f"✅ 已合并 {len(additional_world_book['entries'])} 个通用世界书条目")
    
    def set_current_config(self, config: ChatConfig) -> None:
        """设置当前配置"""
        self.current_config = config
        self.current_manager = self.load_chat_manager(config)
        
        # 更新最后使用时间
        config.last_used = datetime.now().isoformat()
        self.save_config(config)
        
        print(f"✅ 已切换到配置: {config.name}")
    
    def get_current_manager(self) -> Optional[ChatHistoryManager]:
        """获取当前的ChatHistoryManager"""
        return self.current_manager
    
    def get_file_list(self, file_type: str) -> List[str]:
        """获取指定类型的文件列表"""
        type_dir_map = {
            "presets": self.presets_dir,
            "characters": self.characters_dir,
            "personas": self.personas_dir,
            "world_books": self.world_books_dir
        }
        
        if file_type not in type_dir_map:
            return []
        
        target_dir = type_dir_map[file_type]
        files = []
        
        for file_path in target_dir.glob("*.json"):
            files.append(file_path.name)  # 只返回文件名
        
        return sorted(files)


# 便捷函数
def create_config_manager(data_root: str = "data") -> ConfigManager:
    """创建配置管理器"""
    return ConfigManager(data_root)


# 示例用法
if __name__ == "__main__":
    # 创建配置管理器
    config_manager = create_config_manager()
    
    # 列出所有配置
    configs = config_manager.list_configs()
    print(f"找到 {len(configs)} 个配置")
    
    for config in configs:
        print(f"- {config.name} ({config.config_id})")
