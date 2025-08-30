#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
预设格式转换脚本

将SillyTavern预设格式转换为Odysseia简化格式
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional


def extract_settings(sillytavern_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取基础设置"""
    settings = {}
    
    # 提取温度和参数设置
    if "temperature" in sillytavern_data:
        settings["temperature"] = sillytavern_data["temperature"]
    if "frequency_penalty" in sillytavern_data:
        settings["frequency_penalty"] = sillytavern_data["frequency_penalty"]
    if "presence_penalty" in sillytavern_data:
        settings["presence_penalty"] = sillytavern_data["presence_penalty"]
    if "top_p" in sillytavern_data:
        settings["top_p"] = sillytavern_data["top_p"]
    if "top_k" in sillytavern_data:
        settings["top_k"] = sillytavern_data["top_k"]
    
    # 提取上下文和token设置
    if "openai_max_context" in sillytavern_data:
        settings["max_context"] = sillytavern_data["openai_max_context"]
    if "openai_max_tokens" in sillytavern_data:
        settings["max_tokens"] = sillytavern_data["openai_max_tokens"]
    
    # 提取流式设置
    if "stream_openai" in sillytavern_data:
        settings["stream"] = sillytavern_data["stream_openai"]
    
    return settings


def get_prompt_enable_status(prompt_orders: List[Dict], character_id: int, identifier: str) -> Optional[bool]:
    """获取指定角色和identifier的enable状态"""
    for order_config in prompt_orders:
        if order_config.get("character_id") == character_id:
            for order_item in order_config.get("order", []):
                if order_item.get("identifier") == identifier:
                    return order_item.get("enabled")
    return None


def convert_prompt_role(sillytavern_prompt: Dict[str, Any]) -> str:
    """转换prompt的role"""
    # 如果有role字段，直接使用
    if "role" in sillytavern_prompt:
        return sillytavern_prompt["role"]
    
    # 如果是system_prompt为true，默认为system
    if sillytavern_prompt.get("system_prompt", False):
        return "system"
    
    # 默认为system
    return "system"


def convert_prompt_position(sillytavern_prompt: Dict[str, Any]) -> tuple:
    """
    转换prompt的position和相关属性
    
    Returns:
        tuple: (position, depth, group_weight)
    """
    injection_position = sillytavern_prompt.get("injection_position")
    
    if injection_position == 1:
        # in-chat模式
        position = "in-chat"
        depth = sillytavern_prompt.get("injection_depth", 0)
        group_weight = sillytavern_prompt.get("injection_order", 100)
        return position, depth, group_weight
    else:
        # relative模式（injection_position为0或不存在）
        return "relative", None, None


def get_prompt_order(prompt_orders: List[Dict], character_id: int) -> List[str]:
    """获取指定角色的prompt顺序列表"""
    for order_config in prompt_orders:
        if order_config.get("character_id") == character_id:
            order_list = order_config.get("order", [])
            return [item.get("identifier", "") for item in order_list if item.get("identifier")]
    return []


def convert_prompts(sillytavern_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """转换prompts，按照prompt_order重新排序"""
    sillytavern_prompts = sillytavern_data.get("prompts", [])
    prompt_orders = sillytavern_data.get("prompt_order", [])
    
    # 获取character_id 100001的顺序
    order_list = get_prompt_order(prompt_orders, 100001)
    
    # 创建identifier到prompt的映射
    prompt_map = {prompt.get("identifier", ""): prompt for prompt in sillytavern_prompts}
    
    # 按照order重新排列prompts
    ordered_prompts = []
    used_identifiers = set()
    
    # 首先添加按order排序的prompts
    for identifier in order_list:
        if identifier in prompt_map:
            ordered_prompts.append(prompt_map[identifier])
            used_identifiers.add(identifier)
    
    # 然后添加不在order中的prompts（放到末尾）
    for prompt in sillytavern_prompts:
        identifier = prompt.get("identifier", "")
        if identifier and identifier not in used_identifiers:
            ordered_prompts.append(prompt)
    
    # 转换prompts
    converted_prompts = []
    for prompt in ordered_prompts:
        identifier = prompt.get("identifier", "")
        if not identifier:
            continue
        
        # 获取enable状态（固定使用100001）
        enable_status = get_prompt_enable_status(prompt_orders, 100001, identifier)
        if enable_status is None:
            enable_status = None  # 如果找不到，设为null
        
        # 构建转换后的prompt
        converted_prompt = {
            "identifier": identifier,
            "name": prompt.get("name", ""),
            "enabled": enable_status,
            "role": convert_prompt_role(prompt),
        }
        
        # 处理position和相关属性
        position, depth, group_weight = convert_prompt_position(prompt)
        converted_prompt["position"] = position
        
        if position == "in-chat":
            if depth is not None:
                converted_prompt["depth"] = depth
            if group_weight is not None:
                converted_prompt["group_weight"] = group_weight
        
        # 处理content字段
        if "content" in prompt:
            converted_prompt["content"] = prompt["content"]
        
        converted_prompts.append(converted_prompt)
    
    return converted_prompts


def convert_sillytavern_to_simplified(sillytavern_data: Dict[str, Any]) -> Dict[str, Any]:
    """将SillyTavern格式转换为简化格式"""
    
    simplified_data = {}
    
    # 提取设置
    settings = extract_settings(sillytavern_data)
    if settings:
        simplified_data["setting"] = settings
    
    # 转换prompts
    prompts = convert_prompts(sillytavern_data)
    if prompts:
        simplified_data["prompts"] = prompts
    
    return simplified_data


def convert_file(input_file: str, output_file: str = None):
    """转换文件"""
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_file}")
        return False
    
    # 确定输出文件名
    if output_file is None:
        output_path = input_path.with_suffix('.simplified.json')
    else:
        output_path = Path(output_file)
    
    try:
        # 读取输入文件
        print(f"📖 读取文件: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            sillytavern_data = json.load(f)
        
        # 转换数据
        print("🔄 转换数据...")
        simplified_data = convert_sillytavern_to_simplified(sillytavern_data)
        
        # 写入输出文件
        print(f"💾 保存到: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(simplified_data, f, ensure_ascii=False, indent=4)
        
        print(f"✅ 转换完成!")
        
        # 显示转换统计
        settings_count = len(simplified_data.get("setting", {}))
        prompts_count = len(simplified_data.get("prompts", []))
        enabled_prompts = len([p for p in simplified_data.get("prompts", []) if p.get("enabled") is True])
        
        # 获取顺序统计
        prompt_orders = sillytavern_data.get("prompt_order", [])
        order_list = get_prompt_order(prompt_orders, 100001)
        ordered_count = len(order_list)
        
        print(f"📊 转换统计:")
        print(f"   设置项: {settings_count}")
        print(f"   提示词总数: {prompts_count}")
        print(f"   启用的提示词: {enabled_prompts}")
        print(f"   按character_id:100001排序: {ordered_count}")
        print(f"   未在order中的提示词: {prompts_count - ordered_count}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将SillyTavern预设格式转换为Odysseia简化格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python convert_preset.py input.json
  python convert_preset.py input.json -o output.simplified.json

说明:
  - 自动使用character_id=100001的prompt启用配置
  - 将SillyTavern格式转换为Odysseia简化格式
        """
    )
    
    parser.add_argument(
        "input_file",
        help="输入的SillyTavern预设文件路径"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出文件路径（默认为输入文件名+.simplified.json）"
    )
    

    
    args = parser.parse_args()
    
    print("🎯 SillyTavern预设转换工具")
    print("=" * 50)
    
    success = convert_file(
        args.input_file,
        args.output
    )
    
    if success:
        print("\n🎉 转换完成!")
    else:
        print("\n💥 转换失败!")
        exit(1)


if __name__ == "__main__":
    main()
