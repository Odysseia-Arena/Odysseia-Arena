#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SillyTavern用户角色设定转换器

将SillyTavern的personas格式转换为Odysseia系统的persona格式：
- 提取name（从personas字段的key）
- 提取description（从persona_descriptions字段）
- 转换为标准的persona.json格式
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


def convert_tavern_personas(input_file: str, output_dir: str = "data/personas") -> None:
    """
    转换SillyTavern用户角色设定文件
    
    Args:
        input_file: 输入的SillyTavern personas文件路径
        output_dir: 输出目录，默认为data/personas
    """
    
    # 读取输入文件
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            tavern_data = json.load(f)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 检查必要字段
    if "personas" not in tavern_data or "persona_descriptions" not in tavern_data:
        print("❌ 输入文件格式不正确，缺少personas或persona_descriptions字段")
        return
    
    personas = tavern_data["personas"]
    persona_descriptions = tavern_data["persona_descriptions"]
    
    print(f"找到 {len(personas)} 个用户角色")
    
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 转换每个角色
    converted_count = 0
    for persona_key, persona_name in personas.items():
        
        # 获取描述信息
        if persona_key in persona_descriptions:
            description_data = persona_descriptions[persona_key]
            description = description_data.get("description", "")
        else:
            description = ""
        
        # 创建标准persona格式
        persona_data = {
            "name": persona_name,
            "description": description,
            "tags": ["从SillyTavern转换"],
            "created_date": "2025-01-01"
        }
        
        # 生成输出文件名（使用persona_name，去除特殊字符）
        safe_name = "".join(c for c in persona_name if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = f"persona_{converted_count + 1}"
        
        output_file = output_path / f"{safe_name}.json"
        
        # 如果文件已存在，添加数字后缀
        counter = 1
        while output_file.exists():
            output_file = output_path / f"{safe_name}_{counter}.json"
            counter += 1
        
        # 保存转换后的文件
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(persona_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 转换完成: {persona_key} -> {output_file.name}")
            print(f"   名称: {persona_name}")
            print(f"   描述: {description}")
            converted_count += 1
            
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
    
    print(f"\n🎉 转换完成！共转换 {converted_count} 个用户角色")
    print(f"输出目录: {output_path.absolute()}")


def show_tavern_personas_info(input_file: str) -> None:
    """
    显示SillyTavern用户角色设定信息
    
    Args:
        input_file: 输入文件路径
    """
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            tavern_data = json.load(f)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    print("📋 SillyTavern用户角色设定信息:")
    print("="*50)
    
    if "personas" in tavern_data:
        personas = tavern_data["personas"]
        print(f"用户角色数量: {len(personas)}")
        
        for persona_key, persona_name in personas.items():
            print(f"\n角色键: {persona_key}")
            print(f"角色名: {persona_name}")
            
            # 查找对应的描述
            if "persona_descriptions" in tavern_data:
                descriptions = tavern_data["persona_descriptions"]
                if persona_key in descriptions:
                    desc_data = descriptions[persona_key]
                    description = desc_data.get("description", "无描述")
                    position = desc_data.get("position", "未知")
                    print(f"描述: {description}")
                    print(f"位置: {position}")
                else:
                    print("描述: 无")
    
    if "default_persona" in tavern_data:
        default = tavern_data["default_persona"]
        print(f"\n默认角色: {default}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  查看信息: python convert_tavern_personas.py <输入文件>")
        print("  转换文件: python convert_tavern_personas.py <输入文件> --convert")
        print("\n示例:")
        print("  python convert_tavern_personas.py personas_20250829.json")
        print("  python convert_tavern_personas.py personas_20250829.json --convert")
        return
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"❌ 文件不存在: {input_file}")
        return
    
    if "--convert" in sys.argv:
        # 执行转换
        convert_tavern_personas(input_file)
    else:
        # 只显示信息
        show_tavern_personas_info(input_file)


if __name__ == "__main__":
    main()
