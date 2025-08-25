# glicko2_rating.py
from typing import Dict, List, Tuple
from . import storage
from . import glicko2 # 导入我们自己的、修改过的 glicko2 模块

def process_battle_result(model_a_id: str, model_b_id: str, winner: str):
    """
    处理对战结果，使用 Glicko-2 算法更新模型评分和统计数据。

    :param model_a_id: 模型A的ID
    :param model_b_id: 模型B的ID
    :param winner: 获胜者 ("model_a", "model_b", 或 "tie")
    """
    # 1. 获取所有模型的当前评分数据
    scores = storage.get_model_scores()

    # 2. 确保模型存在于评分表中
    if model_a_id not in scores or model_b_id not in scores:
        print(f"错误: 尝试更新评分时找不到模型 {model_a_id} 或 {model_b_id}")
        return

    # 3. 为模型A和模型B创建 Glicko-2 Player 对象
    model_a_stats = scores[model_a_id]
    player_a = glicko2.Player(
        rating=model_a_stats['rating'],
        rd=model_a_stats['rating_deviation'],
        vol=model_a_stats['volatility']
    )

    model_b_stats = scores[model_b_id]
    player_b = glicko2.Player(
        rating=model_b_stats['rating'],
        rd=model_b_stats['rating_deviation'],
        vol=model_b_stats['volatility']
    )

    # 4. 确定比赛结果值 (1.0 for win, 0.5 for tie, 0.0 for loss)
    if winner == "model_a":
        outcome_a, outcome_b = 1.0, 0.0
    elif winner == "model_b":
        outcome_a, outcome_b = 0.0, 1.0
    else:  # tie
        outcome_a, outcome_b = 0.5, 0.5

    # 5. 更新评分
    # player_a 和 player_b 进行了一场比赛
    player_a.update_player([model_b_stats['rating']], [model_b_stats['rating_deviation']], [outcome_a])
    player_b.update_player([model_a_stats['rating']], [model_a_stats['rating_deviation']], [outcome_b])

    # 6. 更新 scores 字典中的统计数据
    # 更新模型A
    scores[model_a_id]['rating'] = player_a.getRating()
    scores[model_a_id]['rating_deviation'] = player_a.getRd()
    scores[model_a_id]['volatility'] = player_a.vol
    scores[model_a_id]['battles'] += 1
    if winner == "model_a":
        scores[model_a_id]['wins'] += 1
    elif winner == "tie":
        scores[model_a_id]['ties'] = scores[model_a_id].get('ties', 0) + 1
    
    # 更新模型B
    scores[model_b_id]['rating'] = player_b.getRating()
    scores[model_b_id]['rating_deviation'] = player_b.getRd()
    scores[model_b_id]['volatility'] = player_b.vol
    scores[model_b_id]['battles'] += 1
    if winner == "model_b":
        scores[model_b_id]['wins'] += 1
    elif winner == "tie":
        scores[model_b_id]['ties'] = scores[model_b_id].get('ties', 0) + 1

    # 7. 保存更新后的所有模型数据到数据库
    storage.save_model_scores(scores)

def generate_leaderboard() -> List[Dict]:
    """
    生成排行榜。
    直接从数据库读取最新数据，包含 Glicko-2 评分和 RD。
    """
    scores = storage.get_model_scores()
    leaderboard = []

    for model_id, stats in scores.items():
        if not stats.get("is_active", 1):
            continue

        display_name = stats.get("model_name", model_id)
        rating = stats["rating"]
        rating_deviation = stats.get("rating_deviation", 350.0)
        battles = stats["battles"]
        wins = stats["wins"]
        ties = stats.get("ties", 0)
        
        # 胜率计算保持不变
        win_rate = ((wins + 0.5 * ties) / battles * 100) if battles > 0 else 0

        volatility = stats.get("volatility", 0.06)

        leaderboard.append({
            "model_id": model_id, # 添加 model_id 以便稳定引用
            "model_name": display_name,
            "rating": round(rating), # 评分取整更美观
            "rating_deviation": round(rating_deviation), # RD也取整
            "volatility": round(volatility, 4), # Glicko-2 新增参数
            "battles": battles,
            "wins": wins,
            "ties": ties,
            "win_rate_percentage": round(win_rate, 2)
        })

    # 按评分降序排序
    leaderboard.sort(key=lambda x: x["rating"], reverse=True)

    # 添加排名
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard