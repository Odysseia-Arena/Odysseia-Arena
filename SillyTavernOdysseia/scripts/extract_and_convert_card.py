#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版角色卡提取和转换器

集成PNG提取、JSON修复和SillyTavern格式转换功能
"""

import struct
import zlib
import base64
import json
import sys
import os
from pathlib import Path
from datetime import datetime


def read_chunks(png_path):
    """读取PNG文件中的所有chunks"""
    with open(png_path, "rb") as f:
        signature = f.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise Exception("Not a PNG file")

        chunks = []
        while True:
            data = f.read(8)
            if len(data) < 8:
                break
            length, ctype = struct.unpack(">I4s", data)
            chunk_data = f.read(length)
            crc = f.read(4)
            chunks.append((ctype.decode("latin1"), chunk_data))
        return chunks


def try_decode(data):
    """尝试解码 chunk 里的数据"""
    try:
        txt = data.decode("utf-8")
    except:
        return None

    # 如果以 { 开头，大概率是 JSON
    if txt.strip().startswith("{"):
        return txt

    # 如果是 Base64
    try:
        decoded = base64.b64decode(txt)
        # 尝试解压
        try:
            decompressed = zlib.decompress(decoded).decode("utf-8")
            return decompressed
        except Exception:
            return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return txt


def repair_json(json_text):
    """修复JSON格式问题"""
    # 移除开头的非JSON字符
    json_text = json_text.strip()
    if json_text.startswith('q'):
        json_text = json_text[1:]
    
    # 查找JSON的结束位置
    try:
        # 简单的括号计数来找到JSON结束
        brace_count = 0
        for i, char in enumerate(json_text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_text = json_text[:i+1]
                    break
    except:
        pass
    
    return json_text


def convert_character_card(character_data):
    """将SillyTavern v3角色卡转换为简化格式"""
    
    def safe_get(obj, key, default=""):
        """安全地获取对象属性"""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default
    
    def convert_world_book_entry(entry):
        """转换世界书条目"""
        extensions = safe_get(entry, "extensions", {})
        
        # 确定mode
        constant = safe_get(entry, "constant", False)
        vectorized = extensions.get("vectorized", False)
        
        if constant:
            mode = "always"
        elif vectorized:
            mode = "vectorized"
        else:
            mode = "conditional"
        
        # 确定position
        position = safe_get(entry, "position", "")
        ext_position = extensions.get("position", 0)
        ext_role = extensions.get("role", 0)
        
        if position == "before_char" and ext_position == 0:
            final_position = "before_char"
        elif position == "after_char" and ext_position == 4:
            if ext_role == 0:
                final_position = "system"
            elif ext_role == 1:
                final_position = "user"
            elif ext_role == 2:
                final_position = "assistant"
            else:
                final_position = "system"  # 默认
        elif position == "after_char" and ext_position == 1:
            final_position = "after_char"
        else:
            # 其他情况，使用原始position或默认值
            final_position = position if position else "before_char"
        
        # 构建基础条目（按目标顺序排列）
        converted = {
            "id": safe_get(entry, "id", 0),
            "name": safe_get(entry, "comment", ""),
            "enabled": safe_get(entry, "enabled", True),
            "mode": mode,
            "position": final_position
        }
        
        # 根据position决定是否添加depth（在keys之前）
        if final_position not in ["after_char", "before_char"]:
            # 其他情况：记录depth
            converted["depth"] = extensions.get("depth", 0)
        
        # 添加剩余字段
        converted["group_weight"] = extensions.get("group_weight", 100)
        converted["probability"] = extensions.get("probability", 100)
        converted["keys"] = safe_get(entry, "keys", [])
        converted["content"] = safe_get(entry, "content", "")
        
        return converted
    
    # 构建message数组（包含first_mes和alternate_greetings）
    messages = []
    first_mes = safe_get(character_data, "first_mes", "")
    if first_mes:
        messages.append(first_mes)
    
    # 从data中获取alternate_greetings
    data = safe_get(character_data, "data", {})
    alternate_greetings = safe_get(data, "alternate_greetings", [])
    if isinstance(alternate_greetings, list):
        messages.extend(alternate_greetings)
    
    # 如果没有任何消息，至少保留一个空消息
    if not messages:
        messages = [""]
    
    # 获取世界书名称
    character_book = safe_get(data, "character_book", {})
    world_book_name = safe_get(character_book, "name", f"{safe_get(character_data, 'name', '未知角色')}的世界书")
    
    # 基本信息（按目标文件字段顺序）
    simplified = {
        "name": safe_get(character_data, "name", "未知角色"),
        "description": safe_get(character_data, "description", ""),
        "message": messages,
        "world_book": {
            "name": world_book_name,
            "entries": []
        }
    }
    
    # 添加extensions（从data.extensions获取）
    data_extensions = safe_get(data, "extensions", {})
    if data_extensions:
        simplified["extensions"] = data_extensions
    
    # 添加create_date（使用原始数据或当前时间）
    create_date = safe_get(character_data, "create_date", datetime.now().strftime("%Y-%m-%d"))
    simplified["create_date"] = create_date
    
    # 转换世界书（character_book在前面已经获取）
    if character_book and isinstance(character_book, dict):
        entries = safe_get(character_book, "entries", [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    converted_entry = convert_world_book_entry(entry)
                    simplified["world_book"]["entries"].append(converted_entry)
    
    return simplified


def extract_and_convert_card(png_path, output_dir=None):
    """提取PNG中的角色卡数据并转换格式"""
    png_path = Path(png_path)
    
    if output_dir is None:
        output_dir = png_path.stem + "_extracted"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"🔍 正在提取和转换 {png_path.name}...")
    
    try:
        chunks = read_chunks(png_path)
        
        success_count = 0
        
        for name, data in chunks:
            if name == "tEXt":
                decoded = try_decode(data)
                if decoded and decoded.strip():
                    # 修复JSON
                    repaired_json = repair_json(decoded)
                    
                    try:
                        # 解析JSON
                        character_data = json.loads(repaired_json)
                        
                        # 生成文件名
                        char_name = character_data.get("name", "unknown")
                        safe_name = "".join(c for c in char_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_name = safe_name.replace(' ', '_')
                        
                        # 保存原始JSON
                        raw_file = output_dir / f"{safe_name}.raw.json"
                        with open(raw_file, "w", encoding="utf-8") as f:
                            json.dump(character_data, f, ensure_ascii=False, indent=2)
                        
                        # 转换并保存简化格式
                        simplified = convert_character_card(character_data)
                        simplified_file = output_dir / f"{safe_name}.simplified.json"
                        with open(simplified_file, "w", encoding="utf-8") as f:
                            json.dump(simplified, f, ensure_ascii=False, indent=2)
                        
                        print(f"✅ 已转换: {raw_file.name} → {simplified_file.name}")
                        success_count += 1
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON解析失败: {e}")
                        continue
        
        if success_count == 0:
            print("❌ 没有找到有效的角色卡数据")
            return False
        else:
            print(f"🎉 成功转换 {success_count} 个角色卡到 {output_dir}/")
            return True
            
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("📖 用法: python extract_and_convert_card.py <PNG文件路径> [输出目录]")
        print("📖 示例: python extract_and_convert_card.py character.png")
        print("📖 示例: python extract_and_convert_card.py character.png ./output")
        sys.exit(1)
    
    png_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(png_path).exists():
        print(f"❌ 文件不存在: {png_path}")
        sys.exit(1)
    
    success = extract_and_convert_card(png_path, output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
