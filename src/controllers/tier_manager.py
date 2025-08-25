# tier_manager.py
import time
from src.data import storage
from src.utils import config
from src.utils.logger_config import logger
from typing import List, Tuple

def promote_and_relegate_models():
    """
    执行模型的升级与降级操作。
    从高端等级中评分最低的N个模型降级。
    从低端等级中评分最高的N个模型升级。
    """
    logger.info("开始执行每日模型升降级任务...")
    relegation_count = config.PROMOTION_RELEGATION_COUNT

    if relegation_count <= 0:
        logger.info("升降级数量配置为0，跳过任务。")
        return

    try:
        # 使用事务确保数据一致性
        with storage.transaction():
            all_scores = storage.get_model_scores()
            config_models = {m['id'] for m in config.get_models()}

            active_models = {
                model_id: stats for model_id, stats in all_scores.items()
                if stats.get("is_active", 1) and model_id in config_models
            }

            if not active_models:
                logger.warning("没有活动的模型，跳过升降级。")
                return

            # 获取高端模型，并按分数升序排序（最低的在前）
            high_tier_models = sorted(
                [item for item in active_models.items() if item[1].get('tier') == 'high'],
                key=lambda item: item[1]["rating"]
            )
            
            # 获取低端模型，并按分数降序排序（最高的在前）
            low_tier_models = sorted(
                [item for item in active_models.items() if item[1].get('tier') == 'low'],
                key=lambda item: item[1]["rating"],
                reverse=True
            )

            if not high_tier_models or not low_tier_models:
                logger.warning("高端或低端等级中缺少模型，无法进行升降级。建议检查初始化状态。")
                return

            # 选出需要降级和升级的模型
            models_to_relegate = high_tier_models[:relegation_count]
            models_to_promote = low_tier_models[:relegation_count]

            updates: List[Tuple[str, str]] = []
            for model_id, stats in models_to_relegate:
                updates.append(('low', model_id))
            
            for model_id, stats in models_to_promote:
                updates.append(('high', model_id))

            if updates:
                storage.update_model_tiers(updates)
                logger.info("模型升降级完成。")
                for model_id, stats in models_to_relegate:
                    logger.info(f"    - 模型 {stats.get('model_name', model_id)} ({stats['rating']}) 已降级。")
                for model_id, stats in models_to_promote:
                    logger.info(f"    - 模型 {stats.get('model_name', model_id)} ({stats['rating']}) 已升级。")
            else:
                logger.info("没有需要升降级的模型。")
                
    except Exception as e:
        logger.error(f"执行模型升降级任务时发生错误: {e}", exc_info=True)


def initialize_model_tiers():
    """
    如果超过一半的模型没有设置等级，则根据排名进行一次性初始化。
    这确保了在系统首次启动或模型大量更新时，等级能被正确设定。
    """
    logger.info("检查模型等级初始化状态...")
    try:
        with storage.transaction():
            all_scores = storage.get_model_scores()
            
            active_models = { model_id: stats for model_id, stats in all_scores.items() if stats.get("is_active", 1) }
            if not active_models:
                logger.info("没有活动模型，跳过等级初始化。")
                return

            models_without_tier = [
                model_id for model_id, stats in active_models.items() 
                if stats.get('tier') not in ('high', 'low')
            ]

            # 如果未设置等级的模型超过一半，或者根本没有高端模型，则执行初始化
            has_high_tier = any(s.get('tier') == 'high' for s in active_models.values())
            if len(models_without_tier) > len(active_models) / 2 or not has_high_tier:
                logger.info("检测到需要进行模型等级初始化。")
                
                sorted_models = sorted(active_models.items(), key=lambda item: item[1]["rating"], reverse=True)
                
                # 模型总数的一半（向上取整）划为高端
                num_high_tier = (len(sorted_models) + 1) // 2
                
                updates: List[Tuple[str, str]] = []
                for i, (model_id, stats) in enumerate(sorted_models):
                    new_tier = 'high' if i < num_high_tier else 'low'
                    if stats.get('tier') != new_tier:
                        updates.append((new_tier, model_id))

                if updates:
                    storage.update_model_tiers(updates)
                    logger.info(f"模型等级初始化完成，更新了 {len(updates)} 个模型。")
            else:
                logger.info("模型等级已初始化，无需操作。")
    except Exception as e:
        logger.error(f"模型等级初始化时发生错误: {e}", exc_info=True)