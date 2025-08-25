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