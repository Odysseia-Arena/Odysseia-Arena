#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
酒馆正则格式转换脚本

将SillyTavern酒馆的正则脚本格式转换为SillyTavern Odysseia的RegexRule格式
"""

import os
import json
import argparse
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


def map_placement_to_targets(placement: List[int]) -> List[str]:
    """
    映射酒馆的placement数值到我们的targets字符串
    
    映射关系:
    - 1 -> "user"
    - 2 -> "assistant_response"
    - 5 -> "world_book"
    - 6 -> "assistant_thinking"
    """
    mapping = {
        1: "user",
        2: "assistant_response",
        5: "world_book", 
        6: "assistant_thinking"
    }
    
    targets = [mapping.get(p, "unknown") for p in placement if p in mapping]
    
    # 如果没有有效的targets，默认所有
    if not targets:
        return ["user", "assistant_response", "world_book", "preset", "assistant_thinking"]
        
    return targets


def convert_replace_pattern(replace_str: str) -> str:
    """
    将酒馆正则的替换模式转换为Python正则的格式
    
    酒馆使用 $1, $2 等，Python正则使用 \\1, \\2 等
    """
    import re
    # 将 $1, $2, $3... 转换为 \1, \2, \3...
    converted = re.sub(r'\$(\d+)', r'\\\1', replace_str)
    return converted


def convert_tavern_regex(tavern_regex: Dict[str, Any]) -> Dict[str, Any]:
    """
    将单个酒馆正则转换为Odysseia RegexRule格式
    
    Args:
        tavern_regex: 酒馆正则格式的字典
        
    Returns:
        转换后的RegexRule格式字典
    """
    # 基本字段转换 - 使用正确的RegexRule字段名
    odysseia_regex = {
        "id": tavern_regex.get("id", str(uuid.uuid4())),
        "name": tavern_regex.get("scriptName", "未命名正则"),
        "enabled": not tavern_regex.get("disabled", False),
        "find_regex": tavern_regex.get("findRegex", ""),
        "replace_regex": convert_replace_pattern(tavern_regex.get("replaceString", "")),  # 转换替换模式
        "targets": map_placement_to_targets(tavern_regex.get("placement", [])),
        "placement": "after_macro",  # 默认宏处理后应用
        "views": ["original"]  # 默认应用于原始视图
    }
    
    # 处理深度范围 - 使用RegexRule的min_depth和max_depth字段
    min_depth = tavern_regex.get("minDepth")
    max_depth = tavern_regex.get("maxDepth")
    
    if min_depth is not None:
        odysseia_regex["min_depth"] = min_depth
    if max_depth is not None:
        odysseia_regex["max_depth"] = max_depth
    
    # 处理order范围 - 使用RegexRule的min_order和max_order字段（如果有）
    min_order = tavern_regex.get("minOrder")
    max_order = tavern_regex.get("maxOrder")
    
    if min_order is not None:
        odysseia_regex["min_order"] = min_order
    if max_order is not None:
        odysseia_regex["max_order"] = max_order
    
    # 添加描述字段
    description_parts = []
    if tavern_regex.get("promptOnly", False):
        description_parts.append("仅对提示词生效")
    if tavern_regex.get("markdownOnly", False):
        description_parts.append("仅对Markdown内容生效")
    if min_depth is not None and max_depth is not None:
        description_parts.append(f"深度范围: {min_depth}-{max_depth}")
    
    odysseia_regex["description"] = " | ".join(description_parts) if description_parts else "从酒馆正则转换"
    
    return odysseia_regex


def convert_file(input_file: str, output_file: str, combine_existing: bool = False) -> None:
    """
    转换酒馆正则文件到Odysseia RegexRule文件
    
    Args:
        input_file: 输入文件路径（酒馆正则格式）
        output_file: 输出文件路径
        combine_existing: 是否合并现有输出文件内容
    """
    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        try:
            # 尝试读取为JSON对象
            tavern_regex = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ 输入文件 {input_file} 不是有效的JSON")
            return
    
    # 检查是单个规则还是规则列表
    if isinstance(tavern_regex, dict):
        tavern_regexes = [tavern_regex]
    elif isinstance(tavern_regex, list):
        tavern_regexes = tavern_regex
    else:
        print(f"⚠️ 无效的输入格式: {type(tavern_regex)}")
        return
    
    # 转换规则
    odysseia_regexes = [convert_tavern_regex(regex) for regex in tavern_regexes]
    
    # 如果需要合并现有文件
    if combine_existing and os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_regexes = json.load(f)
                if isinstance(existing_regexes, list):
                    # 检查ID是否重复
                    existing_ids = {r.get("id") for r in existing_regexes}
                    new_regexes = []
                    for regex in odysseia_regexes:
                        if regex.get("id") in existing_ids:
                            print(f"⚠️ 跳过重复ID: {regex.get('id')}")
                        else:
                            new_regexes.append(regex)
                    odysseia_regexes = existing_regexes + new_regexes
        except Exception as e:
            print(f"⚠️ 读取现有文件失败: {e}")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(odysseia_regexes, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已将 {len(tavern_regexes)} 条酒馆正则转换为 {len(odysseia_regexes)} 条Odysseia规则")
    print(f"✅ 输出到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="将SillyTavern酒馆正则格式转换为Odysseia RegexRule格式")
    parser.add_argument("input", help="输入文件或目录路径（酒馆正则格式）")
    parser.add_argument("-o", "--output", help="输出文件路径，默认为data/regex_rules/converted_规则文件名.json")
    parser.add_argument("-c", "--combine", action="store_true", help="合并现有输出文件的内容")
    
    args = parser.parse_args()
    
    # 处理输入路径
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"⚠️ 输入路径不存在: {input_path}")
        return
    
    # 单个文件处理
    if input_path.is_file():
        if args.output:
            output_file = args.output
        else:
            # 默认输出到data/regex_rules/converted_文件名.json
            filename = input_path.stem
            output_file = f"data/regex_rules/converted_{filename}.json"
        
        convert_file(str(input_path), output_file, args.combine)
    
    # 目录处理
    elif input_path.is_dir():
        # 如果指定了输出但是不是目录，报错
        if args.output and not os.path.isdir(args.output):
            print(f"⚠️ 处理目录时，输出路径应该也是目录: {args.output}")
            return
            
        # 遍历目录中的所有JSON文件
        for file_path in input_path.glob("*.json"):
            if args.output:
                output_dir = args.output
                output_file = os.path.join(output_dir, f"converted_{file_path.name}")
            else:
                output_file = f"data/regex_rules/converted_{file_path.name}"
            
            convert_file(str(file_path), output_file, args.combine)


if __name__ == "__main__":
    main()