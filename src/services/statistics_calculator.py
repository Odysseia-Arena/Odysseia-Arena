import pandas as pd
from src.data import storage
from collections import defaultdict

def get_battle_statistics():
    """
    计算并返回模型对战的胜率和场次统计数据 (SQL优化版)。
    """
    conn = storage._connect()
    try:
        # --- 1. 获取所有模型名称 ---
        models_df = pd.read_sql_query("SELECT DISTINCT model_name FROM models", conn)
        if models_df.empty:
            return {"win_rate_matrix": {}, "match_count_matrix": {}}
        models = models_df['model_name'].tolist()

        # --- 2. 计算总对战场次 ---
        query_counts = "SELECT model_a_name, model_b_name FROM battles WHERE status = 'completed' AND winner != 'skip'"
        counts_df = pd.read_sql_query(query_counts, conn)
        match_counts = defaultdict(lambda: defaultdict(int))
        for _, row in counts_df.iterrows():
            match_counts[row['model_a_name']][row['model_b_name']] += 1
            if row['model_a_name'] != row['model_b_name']:
                 match_counts[row['model_b_name']][row['model_a_name']] += 1

        # --- 3. 计算胜利次数 (SQL聚合) ---
        query_wins = """
        SELECT
            CASE winner WHEN 'model_a' THEN model_a_name ELSE model_b_name END as winning_model,
            CASE winner WHEN 'model_a' THEN model_b_name ELSE model_a_name END as losing_model,
            COUNT(*) as win_count
        FROM battles
        WHERE status = 'completed' AND winner IN ('model_a', 'model_b')
        GROUP BY winning_model, losing_model
        """
        wins_df = pd.read_sql_query(query_wins, conn)
        
        wins = defaultdict(lambda: defaultdict(int))
        for _, row in wins_df.iterrows():
            wins[row['winning_model']][row['losing_model']] = row['win_count']

        # --- 4. 组装胜率矩阵 ---
        win_rate_matrix = defaultdict(lambda: defaultdict(lambda: None))
        for model_a in models:
            for model_b in models:
                if model_a == model_b:
                    continue
                
                wins_a_vs_b = wins[model_a].get(model_b, 0)
                wins_b_vs_a = wins[model_b].get(model_a, 0)
                total_nontie = wins_a_vs_b + wins_b_vs_a

                if total_nontie > 0:
                    win_rate_matrix[model_a][model_b] = wins_a_vs_b / total_nontie
                else:
                    win_rate_matrix[model_a][model_b] = None

    finally:
        conn.close()

    return {
        "win_rate_matrix": dict(win_rate_matrix),
        "match_count_matrix": dict(match_counts)
    }

def get_prompt_statistics():
    """
    计算并返回基于每个提示词的对战统计数据。
    """
    conn = storage._connect()
    try:
        # 使用一条SQL查询聚合所有需要的数据，以获得最佳性能
        query = """
        SELECT
            prompt,
            prompt_theme,
            COUNT(*) AS total_battles,
            SUM(CASE WHEN winner = 'tie' THEN 1 ELSE 0 END) AS tie_count,
            GROUP_CONCAT(model_a_name || ',' || model_b_name) AS all_models,
            GROUP_CONCAT(
                CASE
                    WHEN winner = 'model_a' THEN model_a_name
                    WHEN winner = 'model_b' THEN model_b_name
                    ELSE NULL
                END
            ) AS winning_models
        FROM battles
        WHERE status = 'completed' AND winner != 'skip'
        GROUP BY prompt, prompt_theme
        ORDER BY total_battles DESC;
        """
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        # 1. 计算模型出场次数
        model_counts = defaultdict(int)
        if row['all_models']:
            for model in row['all_models'].split(','):
                if model: model_counts[model] += 1
        
        # 2. 计算模型获胜次数
        win_counts = defaultdict(int)
        if row['winning_models']:
            for model in row['winning_models'].split(','):
                if model: win_counts[model] += 1
        
        # 3. 计算每个模型的胜率
        model_win_rates = {}
        for model, count in model_counts.items():
            wins = win_counts.get(model, 0)
            model_win_rates[model] = wins / count if count > 0 else 0

        results.append({
            "prompt": row['prompt'],
            "prompt_theme": row['prompt_theme'],
            "total_battles": row['total_battles'],
            "model_battle_counts": dict(model_counts),
            "model_win_rates": model_win_rates
        })

    return results

def get_all_models_stats():
    """
    通过单次高效的SQL查询，计算并返回所有模型的全局统计数据（总对战数、胜场、平局）。
    """
    conn = storage._connect()
    try:
        # 这是一个复杂的查询，它将 battles 表进行两次非枢轴转换（一次用于模型A，一次用于模型B），
        # 然后将结果合并，最后按模型名称进行分组和聚合。
        query = """
        SELECT
            model_name,
            COUNT(*) AS total_battles,
            SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) AS total_wins,
            SUM(CASE WHEN is_tie = 1 THEN 1 ELSE 0 END) AS total_ties,
            SUM(CASE WHEN is_skip = 1 THEN 1 ELSE 0 END) AS total_skips
        FROM (
            -- Unpivot for model_a
            SELECT
                model_a_name AS model_name,
                CASE WHEN winner = 'model_a' THEN 1 ELSE 0 END AS is_win,
                CASE WHEN winner = 'tie' THEN 1 ELSE 0 END AS is_tie,
                CASE WHEN winner = 'skip' THEN 1 ELSE 0 END AS is_skip
            FROM battles
            WHERE status = 'completed'
            UNION ALL
            -- Unpivot for model_b
            SELECT
                model_b_name AS model_name,
                CASE WHEN winner = 'model_b' THEN 1 ELSE 0 END AS is_win,
                CASE WHEN winner = 'tie' THEN 1 ELSE 0 END AS is_tie,
                CASE WHEN winner = 'skip' THEN 1 ELSE 0 END AS is_skip
            FROM battles
            WHERE status = 'completed'
        ) AS unpivoted_battles
        GROUP BY model_name;
        """
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    # 将DataFrame转换为所需的字典格式 {model_name: {battles: x, wins: y, ties: z, skips: s, win_rate_percentage: p}}
    stats_dict = {}
    for _, row in df.iterrows():
        total_battles = row['total_battles']
        total_wins = row['total_wins']
        total_ties = row['total_ties']
        total_skips = row['total_skips']
        
        # 计算有效对战场次 (总场次 - 平局 - 跳过)
        effective_battles = total_battles - total_ties - total_skips
        
        # 计算胜率
        if effective_battles > 0:
            win_rate = total_wins / effective_battles
        else:
            win_rate = 0
            
        stats_dict[row['model_name']] = {
            "battles": total_battles,
            "wins": total_wins,
            "ties": total_ties,
            "skips": total_skips,
            "win_rate_percentage": round(win_rate * 100, 2)  # 以百分比形式返回，保留两位小数
        }
    
    return stats_dict