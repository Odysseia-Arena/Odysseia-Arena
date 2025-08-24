# fixed_prompt_response_generator.py
"""固定提示词响应生成器"""

import json
import os
import sys
from typing import Dict, List
from . import config
from .model_client import call_model

def load_test_responses() -> Dict[str, Dict[str, str]]:
    """加载测试用的响应数据"""
    test_file = os.path.join(config.DATA_DIR, "temporary_fixed_prompt_responses.json")
    if os.path.exists(test_file):
        with open(test_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 提供一个最小的测试数据
        return {
            "写一首春天的诗": {
                model["id"]: f"[测试响应] 春天来了，{model['name']}模型的测试诗句。"
                for model in config.get_models()
            }
        }

def generate_responses_with_api() -> Dict[str, Dict[str, str]]:
    """使用真实API生成所有固定提示词的响应"""
    prompts = config.load_fixed_prompts()
    models = config.get_models()
    
    if not prompts:
        raise ValueError("没有找到固定提示词")
    
    if len(models) < 2:
        raise ValueError("至少需要2个模型")
    
    all_responses = {}
    total_calls = len(prompts) * len(models)
    completed = 0
    
    print(f"\n将生成 {len(prompts)} 个提示词 × {len(models)} 个模型 = {total_calls} 个响应")
    
    for prompt in prompts:
        print(f"\n处理提示词: {prompt}")
        responses = {}
        
        for model in models:
            completed += 1
            print(f"  [{completed}/{total_calls}] 调用模型: {model}...", end='')
            try:
                response = call_model(model, prompt)
                responses[model] = response
                print(" ✓")
            except Exception as e:
                print(f" ✗ 错误: {e}")
                responses[model] = f"[生成失败] {str(e)}"
        
        all_responses[prompt] = responses
    
    return all_responses

def save_responses(responses: Dict[str, Dict[str, str]]) -> None:
    """保存生成的响应到文件"""
    output_file = config.FIXED_PROMPT_RESPONSES_FILE
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(responses, f, ensure_ascii=False, indent=2)
    
    print(f"\n响应已保存到: {output_file}")

def generate_fixed_prompt_responses(auto_confirm: bool = False) -> bool:
    """
    生成固定提示词响应的主函数
    
    Args:
        auto_confirm: 是否自动确认使用测试数据
        
    Returns:
        是否成功生成响应文件
    """
    output_file = config.FIXED_PROMPT_RESPONSES_FILE
    
    # 如果文件已存在，直接返回
    if os.path.exists(output_file):
        print(f"固定提示词响应文件已存在: {output_file}")
        return True
    
    print("\n" + "="*60)
    print("固定提示词响应文件不存在，需要生成")
    print("="*60)
    
    if not auto_confirm:
        print("\n选项:")
        print("1. 调用真实API生成响应（需要API密钥，会产生费用）")
        print("2. 使用测试数据（仅用于测试目的）")
        print("3. 退出")
        
        choice = input("\n请选择 [1/2/3]: ").strip()
    else:
        choice = "2"  # 自动选择测试数据
    
    if choice == "1":
        try:
            print("\n开始调用API生成响应...")
            responses = generate_responses_with_api()
            save_responses(responses)
            print("\n✓ 成功生成固定提示词响应")
            return True
        except Exception as e:
            print(f"\n✗ 生成失败: {e}")
            return False
    
    elif choice == "2":
        print("\n使用测试数据...")
        print("⚠️  注意：这是测试数据，不是真实模型生成的响应")
        responses = load_test_responses()
        save_responses(responses)
        print("\n✓ 已使用测试数据创建固定提示词响应文件")
        return True
    
    else:
        print("\n已取消")
        return False

if __name__ == "__main__":
    # 独立运行时执行
    success = generate_fixed_prompt_responses()
    sys.exit(0 if success else 1)