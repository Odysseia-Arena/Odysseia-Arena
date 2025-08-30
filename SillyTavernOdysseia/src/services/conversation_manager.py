#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话管理模块

负责保存、加载和管理对话历史：
- 对话的保存和自动备份
- 对话历史的加载和恢复
- 对话会话的管理
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .chat_history_manager import ChatHistoryManager, ChatMessage


@dataclass
class ConversationMetadata:
    """对话元数据"""
    conversation_id: str
    title: str
    config_id: str
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    message_count: int = 0
    tags: List[str] = field(default_factory=list)


class ConversationManager:
    """对话管理器"""
    
    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.conversations_dir = self.data_root / "conversations"
        self.current_dir = self.conversations_dir / "current"
        self.archived_dir = self.conversations_dir / "archived"
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """确保所有必要目录存在"""
        for directory in [self.conversations_dir, self.current_dir, self.archived_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save_conversation(self, conversation_id: str, manager: ChatHistoryManager, 
                         config_id: str, title: str = "", 
                         tags: Optional[List[str]] = None) -> None:
        """保存对话到文件"""
        
        # 创建对话文件
        conversation_file = self.current_dir / f"{conversation_id}.json"
        
        # 获取聊天历史
        chat_history = manager.get_full_chat_history()
        
        # 创建元数据
        metadata = ConversationMetadata(
            conversation_id=conversation_id,
            title=title or f"对话 {conversation_id[:8]}",
            config_id=config_id,
            message_count=len(chat_history),
            tags=tags or []
        )
        
        # 如果文件已存在，保留创建时间
        if conversation_file.exists():
            try:
                with open(conversation_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    if "metadata" in existing_data:
                        metadata.created_date = existing_data["metadata"].get("created_date", metadata.created_date)
            except Exception:
                pass  # 如果读取失败，使用新的创建时间
        
        # 准备保存数据
        conversation_data = {
            "metadata": {
                "conversation_id": metadata.conversation_id,
                "title": metadata.title,
                "config_id": metadata.config_id,
                "created_date": metadata.created_date,
                "last_updated": metadata.last_updated,
                "message_count": metadata.message_count,
                "tags": metadata.tags
            },
            "chat_history": [
                {
                    "role": msg.role.value,
                    "content": msg.content,
                    "metadata": msg.metadata
                }
                for msg in chat_history
            ],
            "triggered_entries": list(manager.triggered_entries),
            "persona_data": getattr(manager, 'persona_data', {}),
            "character_data": getattr(manager, 'character_data', {})
        }
        
        # 保存到文件
        with open(conversation_file, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 对话已保存: {conversation_file}")
    
    def load_conversation(self, conversation_id: str, manager: ChatHistoryManager) -> bool:
        """从文件加载对话到管理器"""
        
        # 先在current目录查找
        conversation_file = self.current_dir / f"{conversation_id}.json"
        
        # 如果没找到，在archived目录查找
        if not conversation_file.exists():
            conversation_file = self.archived_dir / f"{conversation_id}.json"
        
        if not conversation_file.exists():
            print(f"⚠️ 对话文件不存在: {conversation_id}")
            return False
        
        try:
            with open(conversation_file, "r", encoding="utf-8") as f:
                conversation_data = json.load(f)
            
            # 清空当前聊天历史
            manager.chat_history.clear()
            manager.triggered_entries.clear()
            
            # 恢复聊天历史
            from .chat_history_manager import MessageRole
            for msg_data in conversation_data.get("chat_history", []):
                role = MessageRole(msg_data["role"])
                content = msg_data["content"]
                metadata = msg_data.get("metadata", {})
                
                msg = ChatMessage(role=role, content=content, metadata=metadata)
                manager.chat_history.append(msg)
            
            # 恢复触发的条目
            triggered_entries = conversation_data.get("triggered_entries", [])
            manager.triggered_entries.update(triggered_entries)
            
            # 恢复persona和character数据（如果存在）
            if "persona_data" in conversation_data:
                manager.persona_data = conversation_data["persona_data"]
            
            if "character_data" in conversation_data:
                manager.character_data = conversation_data["character_data"]
            
            print(f"✅ 对话已加载: {conversation_id}")
            print(f"   消息数: {len(manager.chat_history)}")
            print(f"   触发条目: {len(manager.triggered_entries)}")
            
            return True
            
        except Exception as e:
            print(f"❌ 对话加载失败: {e}")
            return False
    
    def list_conversations(self, include_archived: bool = False) -> List[ConversationMetadata]:
        """列出所有对话"""
        conversations = []
        
        # 扫描current目录
        for conv_file in self.current_dir.glob("*.json"):
            try:
                metadata = self._read_conversation_metadata(conv_file)
                if metadata:
                    conversations.append(metadata)
            except Exception as e:
                print(f"⚠️ 读取对话元数据失败: {conv_file} - {e}")
        
        # 如果需要，扫描archived目录
        if include_archived:
            for conv_file in self.archived_dir.glob("*.json"):
                try:
                    metadata = self._read_conversation_metadata(conv_file)
                    if metadata:
                        conversations.append(metadata)
                except Exception as e:
                    print(f"⚠️ 读取归档对话元数据失败: {conv_file} - {e}")
        
        # 按最后更新时间排序
        conversations.sort(key=lambda x: x.last_updated, reverse=True)
        return conversations
    
    def _read_conversation_metadata(self, conv_file: Path) -> Optional[ConversationMetadata]:
        """读取对话元数据"""
        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            metadata = data.get("metadata", {})
            return ConversationMetadata(
                conversation_id=metadata.get("conversation_id", conv_file.stem),
                title=metadata.get("title", f"对话 {conv_file.stem[:8]}"),
                config_id=metadata.get("config_id", "unknown"),
                created_date=metadata.get("created_date", ""),
                last_updated=metadata.get("last_updated", ""),
                message_count=metadata.get("message_count", 0),
                tags=metadata.get("tags", [])
            )
        except Exception:
            return None
    
    def archive_conversation(self, conversation_id: str) -> bool:
        """归档对话（从current移动到archived）"""
        current_file = self.current_dir / f"{conversation_id}.json"
        archived_file = self.archived_dir / f"{conversation_id}.json"
        
        if not current_file.exists():
            print(f"⚠️ 对话文件不存在: {conversation_id}")
            return False
        
        try:
            # 移动文件
            current_file.rename(archived_file)
            print(f"✅ 对话已归档: {conversation_id}")
            return True
        except Exception as e:
            print(f"❌ 归档失败: {e}")
            return False
    
    def delete_conversation(self, conversation_id: str, archived: bool = False) -> bool:
        """删除对话"""
        if archived:
            conv_file = self.archived_dir / f"{conversation_id}.json"
        else:
            conv_file = self.current_dir / f"{conversation_id}.json"
        
        if not conv_file.exists():
            print(f"⚠️ 对话文件不存在: {conversation_id}")
            return False
        
        try:
            conv_file.unlink()
            status = "归档" if archived else "当前"
            print(f"✅ {status}对话已删除: {conversation_id}")
            return True
        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return False
    
    def export_conversation(self, conversation_id: str, export_path: str) -> bool:
        """导出对话到指定路径"""
        # 查找对话文件
        conv_file = self.current_dir / f"{conversation_id}.json"
        if not conv_file.exists():
            conv_file = self.archived_dir / f"{conversation_id}.json"
        
        if not conv_file.exists():
            print(f"⚠️ 对话文件不存在: {conversation_id}")
            return False
        
        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            export_file = Path(export_path)
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 对话已导出: {export_file}")
            return True
        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return False


# 便捷函数
def create_conversation_manager(data_root: str = "data") -> ConversationManager:
    """创建对话管理器"""
    return ConversationManager(data_root)


# 示例用法
if __name__ == "__main__":
    # 创建对话管理器
    conv_manager = create_conversation_manager()
    
    # 列出所有对话
    conversations = conv_manager.list_conversations()
    print(f"找到 {len(conversations)} 个对话")
    
    for conv in conversations:
        print(f"- {conv.title} ({conv.conversation_id[:8]}...)")
        print(f"  配置: {conv.config_id}, 消息数: {conv.message_count}")
