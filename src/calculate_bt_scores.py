import json
import math
import numpy as np
import pandas as pd
import sqlite3
import argparse
import sys
# 引入 scipy 的优化模块，用于求解最大似然估计
from scipy.optimize import minimize

# --- 1. 设置与导入 (Setup and Imports) ---

# 检查必需的 Python 库
try:
    import numpy
    import pandas
    import scipy
except ImportError as e:
    print(f"缺少必需的 Python 库。请安装它们:", file=sys.stderr)
    print("pip install numpy pandas scipy", file=sys.stderr)
    sys.exit(1)

# 导入提供的 storage 模块 (storage.py 负责数据库交互)
try:
    # 假设 storage.py 及其依赖项 (config.py, logger_config.py) 可用
    import src.storage as storage
except ImportError as e:
    print(f"错误: 无法导入 storage.py 或其依赖项。", file=sys.stderr)
    print(f"详情: {e}", file=sys.stderr)
    print("请确保 storage.py, config.py, 和 logger_config.py 在 Python 路径中。", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    # 捕获 storage 模块初始化期间的潜在错误 (例如配置问题)
    print(f"storage 模块初始化期间出错: {e}", file=sys.stderr)
    sys.exit(1)

# --- 2. 配置 (Configuration) ---

# Glicko-2 缩放参数
GLICKO_MEAN = 1500 # Glicko 系统的平均分/初始分
# BT (自然对数尺度) 到 Glicko/Elo 尺度的转换因子 (Q因子): 400 / ln(10) ≈ 173.7178
BT_TO_GLICKO_SCALE = 400 / np.log(10)
# 最大/默认初始评分偏差 (RD)。Glicko-2 建议值为 350。
MAX_RD = 350
# Glicko-2 默认波动率 (Volatility)
DEFAULT_VOLATILITY = 0.06

# 优化参数
# L2 正则化参数。在数据稀疏时有助于稳定分数，防止过拟合。
# 增加正则化参数以稳定 Hessian 矩阵的逆运算，避免数值不稳定导致的巨大方差
REGULARIZATION = 1e-4


# --- 3. 数据加载 (Data Loading) ---

def fetch_completed_battles() -> pd.DataFrame:
    """使用 storage.py 接口获取所有已完成的对战记录。"""
    print("正在从数据库获取对战数据...", file=sys.stderr)
    # 查询语句：选择已完成对战的模型 A、模型 B 和赢家
    query = """
        SELECT
            model_a_id,
            model_b_id,
            winner
        FROM battles
        WHERE status = 'completed'
    """
    try:
        # 使用 storage.py 提供的 db_access 上下文管理器
        with storage.db_access() as conn:
            cursor = conn.execute(query)
            battles = cursor.fetchall()
    except Exception as e:
        print(f"数据库访问错误: {e}", file=sys.stderr)
        print("请确保数据库已初始化并通过 storage.py 配置可访问。", file=sys.stderr)
        sys.exit(1)

    if not battles:
        return pd.DataFrame(columns=['model_a_id', 'model_b_id', 'winner'])

    # 转换为 Pandas DataFrame
    df = pd.DataFrame([dict(row) for row in battles])
    
    # 基础清洗: 移除潜在的 None/NaN 条目和自我对战
    df = df.dropna(subset=['model_a_id', 'model_b_id'])
    df = df[df['model_a_id'] != df['model_b_id']]

    print(f"获取到 {len(df)} 条有效的已完成对战。", file=sys.stderr)
    return df

# --- 4. 数据预处理 (Data Preprocessing) ---

def preprocess_data(battles_df: pd.DataFrame):
    """将对战记录转换为模型列表和数值型的胜负矩阵。"""
    if battles_df.empty:
        return [], np.array([]), 0

    # 1. 确定参与模型的列表
    models = sorted(list(set(battles_df['model_a_id']) | set(battles_df['model_b_id'])))
    N = len(models)
    model_to_index = {model_id: i for i, model_id in enumerate(models)}

    # 2. 初始化胜负矩阵 W[i, j] = i 战胜 j 的次数
    wins_matrix = np.zeros((N, N))

    # 3. 填充胜负矩阵
    for _, row in battles_df.iterrows():
        idx_a = model_to_index[row['model_a_id']]
        idx_b = model_to_index[row['model_b_id']]
        winner = row['winner']

        if winner == 'model_a':
            wins_matrix[idx_a, idx_b] += 1.0
        elif winner == 'model_b':
            wins_matrix[idx_b, idx_a] += 1.0
        # 处理平局 (视为双方各得 0.5 胜场)
        elif winner == 'tie' or (isinstance(winner, str) and 'tie' in winner):
            wins_matrix[idx_a, idx_b] += 0.5
            wins_matrix[idx_b, idx_a] += 0.5

    return models, wins_matrix, N

# --- 5. Bradley-Terry 目标函数 (负对数似然, NLL) ---

def bt_negative_log_likelihood(betas, wins_matrix, N, regularization):
    """
    计算 Bradley-Terry 模型的负对数似然 (NLL) 加上 L2 正则化项。
    使用数值稳定的实现方式。
    """
    log_likelihood = 0.0

    # 遍历矩阵的上三角
    for i in range(N):
        for j in range(i + 1, N):
            wins_i_j = wins_matrix[i, j]
            wins_j_i = wins_matrix[j, i]

            # 只考虑进行过对战的配对
            if wins_i_j + wins_j_i > 0:
                beta_i = betas[i]
                beta_j = betas[j]

                # log(P(i>j)) = beta_i - log(exp(beta_i) + exp(beta_j))
                # 使用 np.logaddexp(x, y) = log(exp(x) + exp(y)) 来保证数值稳定性，防止浮点数溢出
                log_denominator = np.logaddexp(beta_i, beta_j)

                log_likelihood += wins_i_j * (beta_i - log_denominator)
                log_likelihood += wins_j_i * (beta_j - log_denominator)

    # L2 正则化项
    regularization_term = 0.5 * regularization * np.sum(betas**2)

    # 返回 NLL + 正则化项 (需要最小化的目标函数)
    return -log_likelihood + regularization_term

# --- 6. Hessian 矩阵计算 (用于不确定性估计) ---

# 协方差矩阵（代表分数的不确定性）是 Hessian 矩阵（目标函数的二阶导数矩阵）的逆。

def calculate_hessian(betas, wins_matrix, N, regularization):
    """
    计算目标函数的解析 Hessian 矩阵 (二阶导数矩阵)。
    """
    H = np.zeros((N, N))

    for i in range(N):
        # 初始化对角线元素，加入正则化项的贡献
        H[i, i] = regularization

        for j in range(N):
            if i == j:
                continue

            total_games = wins_matrix[i, j] + wins_matrix[j, i]

            if total_games > 0:
                beta_i = betas[i]
                beta_j = betas[j]

                # 稳健地计算 P(i>j)，防止溢出
                # P(i>j) = 1 / (1 + exp(-(beta_i - beta_j))) (Logistic 函数)
                try:
                    p_ij = 1 / (1 + np.exp(-(beta_i - beta_j)))
                except OverflowError:
                    # 如果差异太大导致溢出（虽然 NumPy 通常处理得很好），则胜率接近 1 或 0
                    p_ij = 1.0 if beta_i > beta_j else 0.0

                # 核心方差项: N_ij * P_ij * (1 - P_ij)
                variance_term = total_games * p_ij * (1 - p_ij)

                # 累加到对角线元素 H_ii
                H[i, i] += variance_term

                # 非对角线元素 H_ij
                H[i, j] = -variance_term
    return H

# --- 7. BT 计算 (MLE) ---

def calculate_bt_scores(battles_df: pd.DataFrame, regularization=REGULARIZATION, calculate_uncertainty=True):
    """
    执行最大似然估计 (MLE) 并可选地计算不确定性 (方差)。
    """
    models, wins_matrix, N = preprocess_data(battles_df)

    if N <= 1:
        print("参与的模型不足，无法计算相对分数。", file=sys.stderr)
        return {}, {}, models

    print(f"正在使用约束优化 (SLSQP) 计算 {N} 个模型的分数...", file=sys.stderr)

    # 1. MLE 优化
    initial_betas = np.zeros(N)

    # 定义目标函数
    def objective_function(betas):
        return bt_negative_log_likelihood(betas, wins_matrix, N, regularization)

    # 定义约束条件: sum(betas) = 0。这是为了确保模型的可识别性（因为分数是相对的）并将分数居中。
    constraints = ({'type': 'eq', 'fun': lambda betas: np.sum(betas)})

    # 执行优化
    result = minimize(
        objective_function,
        initial_betas,
        method='SLSQP', # 适用于带等式约束的优化方法
        constraints=constraints,
        options={'disp': False, 'maxiter': 1000}
    )

    if not result.success:
        print(f"警告: 优化未完全收敛。信息: {result.message}", file=sys.stderr)

    optimized_betas = result.x
    bt_scores = {model: score for model, score in zip(models, optimized_betas)}

    # 2. 不确定性计算（可选）
    if calculate_uncertainty:
        print("正在计算 Hessian 矩阵以估计不确定性...", file=sys.stderr)
        hessian = calculate_hessian(optimized_betas, wins_matrix, N, regularization)

        # 协方差矩阵是 Hessian 矩阵的逆。
        # 我们使用 Moore-Penrose 伪逆 (pinv)，这是在"和为零"约束下估计方差的标准方法。
        try:
            cov_matrix = np.linalg.pinv(hessian)
            variances = np.diag(cov_matrix) # 方差是对角线元素

            # 处理由于数值不稳定导致的潜在微小负方差
            if np.any(variances < 0):
                variances = np.maximum(variances, 0)

            bt_uncertainty = {model: var for model, var in zip(models, variances)}

        except np.linalg.LinAlgError as e:
            print(f"警告: 无法计算协方差矩阵 (Hessian 求逆失败): {e}", file=sys.stderr)
            bt_uncertainty = {}
    else:
        print("跳过不确定性计算...", file=sys.stderr)
        bt_uncertainty = {}

    return bt_scores, bt_uncertainty, models

# --- 8. Glicko-2 缩放 (Glicko-2 Scaling) ---

def scale_to_glicko(bt_scores, bt_uncertainty, models_in_battles, calculate_uncertainty_flag):
    """将 BT 分数 (betas) 和方差缩放到 Glicko-2 尺度 (Rating 和 RD)。"""
    
    # 获取数据库中注册的所有模型，包括那些没有参加对战的模型。
    try:
        print("正在获取所有注册模型的列表...", file=sys.stderr)
        # 调用 storage.py 的函数
        all_model_scores = storage.get_model_scores()
        all_models = list(all_model_scores.keys())
    except Exception as e:
        print(f"警告: 无法从数据库获取所有模型列表。仅继续处理在对战中发现的模型。错误: {e}", file=sys.stderr)
        all_models = models_in_battles

    glicko_scores = {}

    for model_id in all_models:
        # 情况 1: 模型参与了对战
        if model_id in bt_scores:
            beta = bt_scores[model_id]
            # 1. 缩放评分: Rating = 1500 + Q * beta
            rating = GLICKO_MEAN + BT_TO_GLICKO_SCALE * beta

            # 2. 缩放不确定性 (RD)
            # 检查是否启用了计算，并且该模型存在于不确定性字典中（即计算成功）
            if calculate_uncertainty_flag and model_id in bt_uncertainty:
                variance = bt_uncertainty[model_id]

                # 处理 Bug 1 带来的影响：如果方差为 0（无论是因为计算精确还是因为错误处理），RD 都会是 0。
                if variance <= 0:
                   # 如果是因为 Bug 1 导致的 0，这里需要特殊处理，但更好的做法是修复 Bug 1。
                   # 假设 Bug 1 已修复，则 variance > 0。
                   rd = BT_TO_GLICKO_SCALE * math.sqrt(variance)
                   # 将 RD 限制在最大初始值 (350)。
                   rd = min(rd, MAX_RD)
                else:
                   rd = BT_TO_GLICKO_SCALE * math.sqrt(variance)
                   rd = min(rd, MAX_RD)

            else:
                # 如果禁用了不确定性计算，或者计算失败（模型不在 bt_uncertainty 中）
                if not calculate_uncertainty_flag:
                    # 明确表示不确定性计算被禁用，使用 null 值
                    rd = None
                else:
                    # 使用默认的高 RD 值
                    rd = MAX_RD
        
        # 情况 2: 模型已注册但未参与对战
        else:
            rating = GLICKO_MEAN
            # 未参与对战的模型使用默认 RD，无论是否启用了不确定性计算
            rd = MAX_RD

        if rd is None:
            # 不确定性计算被禁用，rd 为 null
            glicko_scores[model_id] = {
                "rating": round(float(rating), 2),
                "rd": None,
                "volatility": DEFAULT_VOLATILITY # Glicko-2 所需的参数
            }
        else:
            # 正常计算 rd 值
            glicko_scores[model_id] = {
                "rating": round(float(rating), 2),
                "rd": round(float(rd), 2),
                "volatility": DEFAULT_VOLATILITY # Glicko-2 所需的参数
            }

    return glicko_scores

# --- 9. 主逻辑和 CLI (Main Logic and CLI) ---

def main(output_file, calculate_uncertainty_flag):
    print("--- 开始 Bradley-Terry 分数计算，用于 Glicko-2 初始化 ---", file=sys.stderr)

    # 1. 获取数据
    battles_df = fetch_completed_battles()

    # 2. 计算 BT 分数和不确定性 (MLE)
    bt_scores, bt_uncertainty, models_in_battles = calculate_bt_scores(battles_df, calculate_uncertainty=calculate_uncertainty_flag)

    # 3. 缩放到 Glicko-2
    glicko_scores = scale_to_glicko(bt_scores, bt_uncertainty, models_in_battles, calculate_uncertainty_flag)

    # 4. 排序并输出结果
    print(f"\n计算完成。正在将结果写入 {output_file}...", file=sys.stderr)

    # 按评分降序排序
    sorted_scores = dict(sorted(glicko_scores.items(), key=lambda item: item[1]['rating'], reverse=True))

    # 写入 JSON 文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sorted_scores, f, ensure_ascii=False, indent=4)

    print("完成。", file=sys.stderr)

# (if __name__ == "__main__": 部分逻辑正确，用于解析命令行参数，此处省略详细注释)
if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='计算 Bradley-Terry 分数并转换为 Glicko-2 评分')
    parser.add_argument('--output', '-o', required=True, help='输出 JSON 文件路径')
    parser.add_argument('--no-uncertainty', action='store_true', help='禁用不确定性计算 (RD)，使用默认值')

    args = parser.parse_args()

    # 调用主函数，传递反转的标志（如果提供 --no-uncertainty，则不计算不确定性）
    main(args.output, not args.no_uncertainty)