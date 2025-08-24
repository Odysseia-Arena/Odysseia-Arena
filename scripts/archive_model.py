# scripts/archive_model.py
"""
归档或恢复数据库中的指定模型。

归档（停用）一个模型会将其从排行榜和新的对战中移除，但保留其所有历史数据。

用法:
    python -m scripts.archive_model <model_id> --deactivate
    python -m scripts.archive_model <model_id> --activate

示例:
    # 归档模型
    python -m scripts.archive_model claude-3-7-sonnet-20250219 --deactivate
    
    # 重新激活模型
    python -m scripts.archive_model claude-3-7-sonnet-20250219 --activate
"""
import os
import sys
import argparse

# 将项目根目录添加到Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import storage

def main():
    parser = argparse.ArgumentParser(
        description="归档或恢复数据库中的模型。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("model_id", help="要操作的模型的ID。")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deactivate", action="store_true", help="停用（归档）模型，将其从排行榜中隐藏。")
    group.add_argument("--activate", action="store_true", help="重新激活模型，使其在排行榜中可见。")
    
    args = parser.parse_args()

    model_id_to_modify = args.model_id
    is_activating = args.activate

    action_text = "激活" if is_activating else "归档"
    new_status_bool = True if is_activating else False
    
    print(f"--- 准备{action_text}模型: {model_id_to_modify} ---")

    try:
        print(f"正在将模型 '{model_id_to_modify}' 的状态设置为 '{'活动' if is_activating else '非活动'}'...")
        
        success = storage.set_model_active_status(model_id_to_modify, new_status_bool)
        
        if success:
            print(f"\n--- 成功 ---")
            print(f"模型 '{model_id_to_modify}' 已成功{action_text}。")
        else:
            print(f"\n--- 未找到 ---")
            print(f"在数据库中找不到ID为 '{model_id_to_modify}' 的模型。")

    except Exception as e:
        print(f"\n--- 发生错误 ---")
        print(f"操作过程中发生错误: {e}")

if __name__ == "__main__":
    try:
        storage.initialize_storage()
    except Exception as e:
        print(f"错误：无法初始化存储。请确保数据库文件路径正确且可访问。")
        print(f"详细信息: {e}")
        sys.exit(1)
        
    main()