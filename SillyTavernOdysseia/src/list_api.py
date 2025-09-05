#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
列表API接口模块

提供获取各类列表数据的接口：
- 角色卡列表
- 预设列表
- 用户列表
- 世界书列表
- 正则规则列表
- 配置列表
"""

from __future__ import annotations

import json
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

from .services.config_manager import create_config_manager, ChatConfig


@dataclass
class ListsResponse:
    """列表响应数据类"""
    characters: List[str] = field(default_factory=list)  # 角色卡列表
    presets: List[str] = field(default_factory=list)     # 预设列表
    personas: List[str] = field(default_factory=list)    # 用户列表
    world_books: List[str] = field(default_factory=list) # 世界书列表
    regex_rules: List[str] = field(default_factory=list) # 正则规则列表
    configs: List[Dict[str, Any]] = field(default_factory=list)  # 配置列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'characters': self.characters,
            'presets': self.presets,
            'personas': self.personas,
            'world_books': self.world_books,
            'regex_rules': self.regex_rules,
            'configs': self.configs,
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ConfigResponse:
    """配置响应数据类"""
    success: bool = True
    message: str = ""
    config_id: str = ""
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'success': self.success,
            'message': self.message
        }
        
        if self.config_id:
            result['config_id'] = self.config_id
            
        if self.error:
            result['error'] = self.error
            
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# 共享实例
_config_manager = None

def _get_config_manager(data_root: str = "data"):
    """获取共享的配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = create_config_manager(data_root)
    return _config_manager


# 列表API函数
def get_characters(data_root: str = "data") -> List[str]:
    """
    获取角色卡列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[str]: 角色卡文件名列表
    """
    config_manager = _get_config_manager(data_root)
    return config_manager.get_file_list("characters")


def get_presets(data_root: str = "data") -> List[str]:
    """
    获取预设列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[str]: 预设文件名列表
    """
    config_manager = _get_config_manager(data_root)
    return config_manager.get_file_list("presets")


def get_personas(data_root: str = "data") -> List[str]:
    """
    获取用户列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[str]: 用户文件名列表
    """
    config_manager = _get_config_manager(data_root)
    return config_manager.get_file_list("personas")


def get_world_books(data_root: str = "data") -> List[str]:
    """
    获取世界书列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[str]: 世界书文件名列表
    """
    config_manager = _get_config_manager(data_root)
    return config_manager.get_file_list("world_books")


def get_regex_rules(data_root: str = "data") -> List[str]:
    """
    获取正则规则列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[str]: 正则规则文件名列表
    """
    config_manager = _get_config_manager(data_root)
    return config_manager.get_file_list("regex_rules")


def get_configs(data_root: str = "data") -> List[Dict[str, Any]]:
    """
    获取配置列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        List[Dict[str, Any]]: 配置信息列表
    """
    config_manager = _get_config_manager(data_root)
    configs = config_manager.list_configs()
    return [
        {
            "config_id": config.config_id,
            "name": config.name,
            "description": config.description,
            "components": config.components,
            "tags": config.tags,
            "created_date": config.created_date,
            "last_used": config.last_used
        }
        for config in configs
    ]


def get_all_lists(data_root: str = "data") -> Union[Dict[str, Any], str]:
    """
    获取所有列表
    
    Args:
        data_root: 数据根目录，默认为"data"
        
    Returns:
        Union[Dict[str, Any], str]: 所有列表数据的字典或JSON字符串
    """
    characters = get_characters(data_root)
    presets = get_presets(data_root)
    personas = get_personas(data_root)
    world_books = get_world_books(data_root)
    regex_rules = get_regex_rules(data_root)
    configs = get_configs(data_root)
    
    response = ListsResponse(
        characters=characters,
        presets=presets,
        personas=personas,
        world_books=world_books,
        regex_rules=regex_rules,
        configs=configs
    )
    
    return response.to_dict()


def create_config(config_data: Dict[str, Any], data_root: str = "data") -> Union[Dict[str, Any], str]:
    """
    创建新的配置
    
    Args:
        config_data: 配置数据，包含以下字段：
            - config_id: 配置ID
            - name: 配置名称
            - description: 配置描述
            - components: 组件配置
            - tags: 标签列表
        data_root: 数据根目录，默认为"data"
        
    Returns:
        Union[Dict[str, Any], str]: 包含结果信息的字典或JSON字符串
    """
    config_manager = _get_config_manager(data_root)
    
    try:
        # 提取配置数据
        config_id = config_data.get("config_id")
        name = config_data.get("name")
        
        if not name:
            return ConfigResponse(
                success=False,
                error="配置名称不能为空"
            ).to_dict()
        
        description = config_data.get("description", "")
        components = config_data.get("components", {})
        tags = config_data.get("tags", [])
        
        # 如果没有提供config_id，生成一个唯一ID
        if not config_id:
            config_id = f"config_{uuid.uuid4().hex[:8]}"
            
        # 创建配置
        preset_file = components.get("preset")
        character_file = components.get("character")
        persona_file = components.get("persona")
        additional_world_book = components.get("additional_world_book")
        regex_rule_files = components.get("regex_rules", [])
        
        config = config_manager.create_config(
            config_id=config_id,
            name=name,
            description=description,
            preset_file=preset_file,
            character_file=character_file,
            persona_file=persona_file,
            additional_world_book=additional_world_book,
            regex_rule_files=regex_rule_files,
            tags=tags
        )
        
        # 保存配置
        config_manager.save_config(config)
        
        return ConfigResponse(
            success=True,
            message="配置创建成功",
            config_id=config_id
        ).to_dict()
        
    except Exception as e:
        return ConfigResponse(
            success=False,
            error=str(e)
        ).to_dict()


# 示例用法
if __name__ == "__main__":
    # 获取所有列表
    all_lists = get_all_lists()
    
    # 打印结果
    print("=== 角色卡列表 ===")
    for char in all_lists["characters"]:
        print(f"- {char}")
    
    print("\n=== 预设列表 ===")
    for preset in all_lists["presets"]:
        print(f"- {preset}")
    
    print("\n=== 用户列表 ===")
    for persona in all_lists["personas"]:
        print(f"- {persona}")
        
    print("\n=== 世界书列表 ===")
    for world_book in all_lists["world_books"]:
        print(f"- {world_book}")
    
    print("\n=== 正则规则列表 ===")
    for regex_rule in all_lists["regex_rules"]:
        print(f"- {regex_rule}")
        
    print("\n=== 配置列表 ===")
    for config in all_lists["configs"]:
        print(f"- {config['name']} ({config['config_id']})")
    
        
    # 创建配置示例
    config_data = {
        "config_id": "test_config_new",
        "name": "测试新配置",
        "description": "通过API创建的测试配置",
        "components": {
            "preset": "test_preset.simplified.json",
            "character": "test_character.simplified.json"
        },
        "tags": ["测试", "API创建"]
    }
    
    result = create_config(config_data)
    print(f"\n=== 创建配置结果 ===")
    print(f"成功: {result['success']}")
    if result['success']:
        print(f"配置ID: {result['config_id']}")
        print(f"消息: {result['message']}")
    else:
        print(f"错误: {result['error']}")