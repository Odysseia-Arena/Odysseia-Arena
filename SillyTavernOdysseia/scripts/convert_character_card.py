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


def safe_get(obj, key, default=None):
    """安全地获取对象属性"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def convert_world_book_entry(entry):
    """根据新规则转换世界书条目"""
    
    converted = {
        "id": safe_get(entry, "id", 0),
        "name": safe_get(entry, "comment", ""),
        "enabled": safe_get(entry, "enabled", True),
    }

    constant = safe_get(entry, "constant", False)
    vectorized = safe_get(entry, "extensions", {}).get("vectorized", False)
    if constant is False and vectorized is True:
        converted["mode"] = "vectorized"
    elif constant is True:
        converted["mode"] = "always"
    else:
        converted["mode"] = "conditional"

    position = safe_get(entry, "position")
    ext_position = safe_get(entry, "extensions", {}).get("position")
    ext_role = safe_get(entry, "extensions", {}).get("role")
    
    if position == "before_char" and ext_position == 0:
        converted["position"] = "before_char"
    elif position == "after_char" and ext_position == 4 and ext_role == 0:
        converted["position"] = "system"
    elif position == "after_char" and ext_position == 4 and ext_role == 1:
        converted["position"] = "user"
    elif position == "after_char" and ext_position == 4 and ext_role == 2:
        converted["position"] = "assistant"
    elif position == "after_char" and ext_position == 1:
        converted["position"] = "after_char"
    else:
        converted["position"] = "system"

    if converted["position"] not in ["before_char", "after_char"]:
        converted["depth"] = safe_get(entry, "extensions", {}).get("depth")
    
    converted["order"] = safe_get(entry, "insertion_order", 100)
    converted["keys"] = safe_get(entry, "keys", [])
    converted["content"] = safe_get(entry, "content", "")
    converted["code_block"] = ""

    return converted


def convert_character_card(character_data):
    """将SillyTavern v3角色卡转换为简化格式"""
    
    char_data = safe_get(character_data, "data", {})
    
    first_mes = safe_get(char_data, "first_mes", "")
    alternate_greetings = safe_get(char_data, "alternate_greetings", [])
    message = [first_mes] + alternate_greetings if first_mes else alternate_greetings

    simplified = {
        "name": safe_get(character_data, "name", "未知角色"),
        "description": safe_get(character_data, "description", ""),
        "message": message,
        "code_block": "",
        "world_book": {
            "name": safe_get(char_data, "character_book", {}).get("name", f"{safe_get(character_data, 'name', '未知角色')}的世界书"),
            "entries": []
        },
        "extensions": safe_get(char_data, "extensions", {}),
        "create_date": datetime.now().strftime("%Y-%m-%d"),
    }
    
    character_book = safe_get(char_data, "character_book", {})
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
        with open(input_path, 'r', encoding='utf-8') as f:
            character_data = json.load(f)
        
        simplified = convert_character_card(character_data)
        
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
