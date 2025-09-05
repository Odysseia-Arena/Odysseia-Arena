#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SillyTavern Odysseia

一个功能强大的AI聊天配置管理系统
"""

__version__ = "1.0.0"
__author__ = "Odysseia Team"
__email__ = "team@odysseia.ai"
__description__ = "AI聊天配置管理系统，支持角色卡、预设、世界书、宏处理等高级功能"

from .services.config_manager import create_config_manager, ConfigManager
from .services.chat_history_manager import create_chat_manager, ChatHistoryManager

__all__ = [
    "create_config_manager",
    "ConfigManager",
    "create_chat_manager",
    "ChatHistoryManager",
]
