#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
角色卡格式转换器

将SillyTavern v3格式的角色卡转换为简化格式
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def safe_get(obj, key, default=""):
    """安全地获取对象属性"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def convert_world_book_entry(entry):
    """转换世界书条目"""
    converted = {
        "id": safe_get(entry, "id", 0),
        "keys": safe_get(entry, "keys", []),
        "secondary_keys": safe_get(entry, "secondary_keys", []),
        "content": safe_get(entry, "content", ""),
        "extensions": {
            "position": safe_get(entry, "position", 0),
            "group_weight": safe_get(entry, "extensions", {}).get("group_weight", 100)
        },
        "enabled": safe_get(entry, "enabled", True),
        "insertion_order": safe_get(entry, "insertion_order", 100),
        "case_sensitive": safe_get(entry, "case_sensitive", False),
        "name": safe_get(entry, "comment", ""),
        "priority": safe_get(entry, "priority", 0),
        "scanDepth": safe_get(entry, "scanDepth", 100),
        "token_budget": safe_get(entry, "token_budget", 2048),
        "recursive_scanning": safe_get(entry, "recursive_scanning", False)
    }
    return converted


def convert_character_card(character_data):
    """将SillyTavern v3角色卡转换为简化格式"""
    
    # 基本信息
    simplified = {
        "name": safe_get(character_data, "name", "未知角色"),
        "description": safe_get(character_data, "description", ""),
        "message": safe_get(character_data, "first_mes", ""),
        "extensions": {},
        "create_date": datetime.now().strftime("%Y-%m-%d"),
        "world_book": {
            "name": f"{safe_get(character_data, 'name', '未知角色')}的世界书",
            "entries": []
        }
    }
    
    # 转换世界书
    character_book = safe_get(character_data, "data", {}).get("character_book", {})
    if character_book and isinstance(character_book, dict):
        entries = safe_get(character_book, "entries", [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    converted_entry = convert_world_book_entry(entry)
                    simplified["world_book"]["entries"].append(converted_entry)
    
    return simplified


def convert_file(input_path, output_path=None):
    """转换角色卡文件"""
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.with_suffix('.simplified.json')
    else:
        output_path = Path(output_path)
    
    print(f"🔄 正在转换 {input_path.name}...")
    
    try:
        # 读取原始数据
        with open(input_path, 'r', encoding='utf-8') as f:
            character_data = json.load(f)
        
        # 转换格式
        simplified = convert_character_card(character_data)
        
        # 保存转换结果
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 转换完成: {output_path.name}")
        print(f"   角色名: {simplified['name']}")
        print(f"   世界书条目数: {len(simplified['world_book']['entries'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("📖 用法: python convert_character_card.py <输入文件> [输出文件]")
        print("📖 示例: python convert_character_card.py character.json")
        print("📖 示例: python convert_character_card.py character.json simplified.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(input_path).exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)
    
    success = convert_file(input_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
