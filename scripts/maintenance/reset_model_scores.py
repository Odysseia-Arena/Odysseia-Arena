# scripts/maintenance/reset_model_scores.py
# python scripts/maintenance/reset_model_scores.py chushi.json
import json
import os
import sys
import argparse

# 将 src 目录添加到 Python 路径中
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.data import storage
from src.utils.logger_config import logger

def reset_scores_from_json(file_path: str):
    """
    从 JSON 文件重置模型得分数据。
    对于文件中的每个模型，先删除数据库中的现有记录，然后插入新记录。
    """
    logger.info(f"开始从文件 '{file_path}' 重置模型得分...")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"错误：找不到文件 '{file_path}'。")
        return
    except json.JSONDecodeError:
        logger.error(f"错误：无法解析文件 '{file_path}' 中的 JSON。")
        return

    if not isinstance(data, dict):
        logger.error("错误：JSON 文件的顶层结构必须是一个字典 (model_id -> score_data)。")
        return

    models_to_reset = []
    for model_id, stats in data.items():
        rating = stats.get("rating")
        rd = stats.get("rd")
        volatility = stats.get("volatility")
        tier = stats.get("tier")

        if not all([rating is not None, rd is not None, volatility is not None, tier is not None]):
            logger.warning(f"跳过模型 '{model_id}'，因为缺少必要的字段（rating, rd, volatility, tier）。")
            continue
        
        models_to_reset.append({
            "model_id": model_id,
            "rating": float(rating),
            "rd": float(rd),
            "volatility": float(volatility),
            "tier": tier
        })

    if not models_to_reset:
        logger.info("没有找到需要处理的模型数据。")
        return

    try:
        with storage.transaction() as conn:
            logger.info("已启动数据库事务。")
            cursor = conn.cursor()
            
            # 1. 提取所有需要重置的 model_id
            model_ids_to_delete = [model['model_id'] for model in models_to_reset]
            
            # 2. 先执行删除操作
            # 使用 (?, ?, ...) 语法来安全地传递参数列表
            placeholders = ','.join('?' for _ in model_ids_to_delete)
            delete_query = f"DELETE FROM models WHERE model_id IN ({placeholders})"
            cursor.execute(delete_query, model_ids_to_delete)
            logger.info(f"删除了 {cursor.rowcount} 条现有模型记录。")

            # 3. 准备要插入的新数据
            records_to_insert = []
            for model in models_to_reset:
                records_to_insert.append((
                    model['model_id'],
                    model['model_id'],  # model_name
                    model['rating'],
                    model['rd'],
                    model['volatility'],
                    model['tier'],
                    model['rating'],  # rating_realtime
                    model['rd'],      # rating_deviation_realtime
                    model['volatility'] # volatility_realtime
                ))

            # 4. 再执行插入操作
            cursor.executemany("""
                INSERT INTO models (
                    model_id, model_name, rating, rating_deviation, volatility, tier,
                    rating_realtime, rating_deviation_realtime, volatility_realtime,
                    battles, wins, ties, skips, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 1)
            """, records_to_insert)
            
            logger.info(f"数据重置完成。总共插入了 {cursor.rowcount} 条新记录。")

    except Exception as e:
        logger.error(f"在重置过程中发生数据库错误，事务已回滚: {e}", exc_info=True)
    else:
        logger.info("数据库事务已成功提交。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 JSON 文件手动重置模型得分数据。")
    parser.add_argument("file_path", type=str, help="包含模型得分数据的 JSON 文件的路径。")
    
    args = parser.parse_args()
    
    # 1. 确保数据库和表结构存在
    storage.initialize_storage()
    
    # 2. 执行重置
    reset_scores_from_json(args.file_path)