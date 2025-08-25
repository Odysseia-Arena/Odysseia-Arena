# scripts/merge_duplicate_models.py
import os
import sys
import sqlite3
import json
from collections import defaultdict

# 将项目根目录添加到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.utils import config

DATABASE_FILE = os.path.join(config.DATA_DIR, "arena.db")
MODELS_CONFIG_FILE = config.MODELS_FILE

def get_authoritative_models():
    """从models.json加载权威模型信息"""
    try:
        with open(MODELS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {model['name']: model['id'] for model in data.get("models", [])}
    except Exception as e:
        print(f"错误: 无法加载或解析权威模型文件 {MODELS_CONFIG_FILE}: {e}")
        return None

def fix_foreign_key_issues():
    """
    修复外键约束失败的问题。
    通过先更新battles表，再处理models表中的记录来解决。
    """
    authoritative_models = get_authoritative_models()
    if authoritative_models is None:
        return

    if not os.path.exists(DATABASE_FILE):
        print(f"错误: 数据库文件不存在于 {DATABASE_FILE}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        print("开始查找所有重名的模型...")
        cursor.execute("""
            SELECT model_name
            FROM models
            GROUP BY model_name
            HAVING COUNT(*) > 1
        """)
        duplicate_groups = cursor.fetchall()

        if not duplicate_groups:
            print("没有找到需要处理的重名模型。")
            return

        print(f"找到了 {len(duplicate_groups)} 组需要处理的重名模型。")

        cursor.execute("BEGIN TRANSACTION")

        for group in duplicate_groups:
            model_name = group['model_name']
            print(f"\n--- 正在处理模型: '{model_name}' ---")

            if model_name not in authoritative_models:
                print(f"  - 警告: 在 '{MODELS_CONFIG_FILE}' 中找不到模型 '{model_name}' 的权威ID。跳过此模型。")
                continue
            
            authoritative_id = authoritative_models[model_name]
            print(f"  - 权威ID: {authoritative_id}")

            cursor.execute("SELECT * FROM models WHERE model_name = ?", (model_name,))
            models_to_process = cursor.fetchall()
            
            all_ids = [m['model_id'] for m in models_to_process]
            source_ids = [m['model_id'] for m in models_to_process if m['model_id'] != authoritative_id]
            
            print(f"  - 发现的所有ID: {all_ids}")
            
            # 1. 优先更新 battles 表，将所有非权威ID重定向到权威ID
            if source_ids:
                print(f"  - 需要重定向的源ID: {source_ids}")
                for source_id in source_ids:
                    cursor.execute("UPDATE battles SET model_a_id = ? WHERE model_a_id = ?", (authoritative_id, source_id))
                    if cursor.rowcount > 0:
                        print(f"    - 已更新 battles 表中 {cursor.rowcount} 条 model_a_id 从 '{source_id}'。")
                    cursor.execute("UPDATE battles SET model_b_id = ? WHERE model_b_id = ?", (authoritative_id, source_id))
                    if cursor.rowcount > 0:
                        print(f"    - 已更新 battles 表中 {cursor.rowcount} 条 model_b_id 从 '{source_id}'。")
            else:
                print("  - 无需重定向 battles 表记录。")

            # 2. 计算合并后的统计数据
            total_battles = sum(m['battles'] for m in models_to_process)
            total_wins = sum(m['wins'] for m in models_to_process)
            total_ties = sum(m['ties'] for m in models_to_process)
            total_skips = sum(m.get('skips', 0) for m in models_to_process)
            weighted_rating_sum = sum(m['rating'] * m['battles'] for m in models_to_process if m['battles'] > 0)
            total_rating_battles = sum(m['battles'] for m in models_to_process if m['battles'] > 0)
            avg_rating = round(weighted_rating_sum / total_rating_battles) if total_rating_battles > 0 else config.DEFAULT_ELO_RATING
            print(f"  - 合并后统计: Battles={total_battles}, Wins={total_wins}, Ties={total_ties}, Skips={total_skips}, AvgRating={avg_rating}")

            # 3. 删除所有源记录 (非权威ID的记录)
            if source_ids:
                placeholders = ','.join('?' for _ in source_ids)
                cursor.execute(f"DELETE FROM models WHERE model_id IN ({placeholders})", tuple(source_ids))
                print(f"  - 已从 models 表中删除 {cursor.rowcount} 条源记录。")

            # 4. 检查权威ID记录是否存在，不存在则插入，存在则更新
            cursor.execute("SELECT 1 FROM models WHERE model_id = ?", (authoritative_id,))
            if cursor.fetchone():
                # 更新现有的权威记录
                cursor.execute("""
                    UPDATE models SET model_name = ?, rating = ?, battles = ?, wins = ?, ties = ?, skips = ?, is_active = 1
                    WHERE model_id = ?
                """, (model_name, avg_rating, total_battles, total_wins, total_ties, total_skips, authoritative_id))
                print(f"  - 已更新现有的权威记录 '{authoritative_id}'。")
            else:
                # 插入新的权威记录
                cursor.execute("""
                    INSERT INTO models (model_id, model_name, rating, battles, wins, ties, skips, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (authoritative_id, model_name, avg_rating, total_battles, total_wins, total_ties, total_skips, 1))
                print(f"  - 权威记录 '{authoritative_id}' 不存在，已插入新记录。")

        conn.commit()
        print("\n所有重名模型已成功处理。")

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f"\n发生数据库错误，操作已回滚: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    confirm = input("警告: 此脚本将永久性地修复数据库中的重名模型记录。要继续吗? (yes/no): ")
    if confirm.lower() == 'yes':
        fix_foreign_key_issues()
    else:
        print("操作已取消。")