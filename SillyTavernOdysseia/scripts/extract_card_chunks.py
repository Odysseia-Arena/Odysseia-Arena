#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PNG角色卡提取器

从PNG文件中提取嵌入的角色卡JSON数据
基于原项目的extract_card_chunks.py，增强了错误处理和输出格式
"""

import struct
import zlib
import base64
import json
import sys
import os
from pathlib import Path


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


def extract_card(png_path, output_dir=None):
    """提取PNG中的角色卡数据"""
    png_path = Path(png_path)
    
    if output_dir is None:
        output_dir = png_path.stem + "_extracted"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"🔍 正在提取 {png_path.name} 中的角色卡数据...")
    
    try:
        chunks = read_chunks(png_path)
        
        idx = 0
        success_count = 0
        
        for name, data in chunks:
            if name == "tEXt":
                idx += 1
                decoded = try_decode(data)
                if decoded and decoded.strip():
                    # 尝试修复JSON
                    repaired_json = repair_json(decoded)
                    
                    # 验证JSON格式
                    try:
                        json.loads(repaired_json)
                        is_valid = True
                    except json.JSONDecodeError:
                        is_valid = False
                    
                    # 保存原始数据
                    raw_file = output_dir / f"card_{idx}.raw.json"
                    with open(raw_file, "w", encoding="utf-8") as f:
                        f.write(decoded)
                    
                    # 如果修复后的JSON有效，也保存修复版
                    if is_valid and repaired_json != decoded:
                        fixed_file = output_dir / f"card_{idx}.fixed.json"
                        with open(fixed_file, "w", encoding="utf-8") as f:
                            f.write(repaired_json)
                        print(f"✅ 提取到 {raw_file.name} 和 {fixed_file.name}")
                    else:
                        print(f"✅ 提取到 {raw_file.name}")
                    
                    success_count += 1
        
        if success_count == 0:
            print("❌ 没有找到有效的 tEXt chunk 或角色卡数据")
            return False
        else:
            print(f"🎉 成功提取 {success_count} 个角色卡数据到 {output_dir}/")
            return True
            
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("📖 用法: python extract_card_chunks.py <PNG文件路径> [输出目录]")
        print("📖 示例: python extract_card_chunks.py character.png")
        print("📖 示例: python extract_card_chunks.py character.png ./output")
        sys.exit(1)
    
    png_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(png_path).exists():
        print(f"❌ 文件不存在: {png_path}")
        sys.exit(1)
    
    success = extract_card(png_path, output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
