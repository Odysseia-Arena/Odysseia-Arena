import json

def calculate_probabilities():
    """
    根据当前的匹配机制，计算每个模型被抽中的概率。
    """
    # --- 1. 定义系统参数 ---
    NUM_HIGH_TIER = 18
    NUM_LOW_TIER = 17
    TRANSITION_ZONE_SIZE = 5

    PROB_CROSS_TIER = 0.07
    PROB_TRANSITION_ZONE = 0.13
    PROB_STANDARD = 1 - PROB_CROSS_TIER - PROB_TRANSITION_ZONE

    # --- 2. 假设模型权重 ---
    # 为了简化，我们假设所有模型的权重都是1.0。
    # 在实际情况中，需要从 config/models.json 读取真实权重。
    # 但由于大部分模型权重为1，这个假设对整体概率分布影响不大，可以快速得到一个近似结果。
    
    high_tier_models = [f"H{i+1}" for i in range(NUM_HIGH_TIER)]
    low_tier_models = [f"L{i+1}" for i in range(NUM_LOW_TIER)]
    all_models = high_tier_models + low_tier_models

    # 定义过渡区
    transition_zone_models = high_tier_models[-TRANSITION_ZONE_SIZE:] + low_tier_models[:TRANSITION_ZONE_SIZE]

    model_probabilities = {model: 0.0 for model in all_models}
    high_choice_probs = {model: 0.0 for model in all_models}
    low_choice_probs = {model: 0.0 for model in all_models}

    # --- 3. 模拟计算 ---

    # 场景A: 用户选择 "high_tier" 对战
    # A.1: 常规匹配 (high vs high)
    base_pool = high_tier_models
    prob_per_model_in_std = 2 / len(base_pool) if base_pool else 0
    for model in base_pool:
        high_choice_probs[model] += PROB_STANDARD * prob_per_model_in_std

    # A.2: 跨级挑战 (high vs all)
    base_pool = high_tier_models
    opponent_pool = all_models
    prob_model1 = 1 / len(base_pool) if base_pool else 0
    prob_model2 = 1 / len(opponent_pool) if opponent_pool else 0
    for model in all_models:
        prob = 0
        if model in base_pool:
            prob += prob_model1
        if model in opponent_pool:
            prob += prob_model2
        high_choice_probs[model] += PROB_CROSS_TIER * prob

    # A.3: 过渡区挑战
    base_pool_trans = [m for m in high_tier_models if m in transition_zone_models]
    opponent_pool_trans = transition_zone_models
    prob_model1_trans = 1 / len(base_pool_trans) if base_pool_trans else 0
    prob_model2_trans = 1 / len(opponent_pool_trans) if opponent_pool_trans else 0
    for model in all_models:
        prob = 0
        if model in base_pool_trans:
            prob += prob_model1_trans
        if model in opponent_pool_trans:
            prob += prob_model2_trans
        high_choice_probs[model] += PROB_TRANSITION_ZONE * prob

    # 场景B: 用户选择 "low_tier" 对战
    # B.1: 常规匹配 (low vs low)
    base_pool = low_tier_models
    prob_per_model_in_std = 2 / len(base_pool) if base_pool else 0
    for model in base_pool:
        low_choice_probs[model] += PROB_STANDARD * prob_per_model_in_std

    # B.2: 跨级挑战 (low vs all)
    base_pool = low_tier_models
    opponent_pool = all_models
    prob_model1 = 1 / len(base_pool) if base_pool else 0
    prob_model2 = 1 / len(opponent_pool) if opponent_pool else 0
    for model in all_models:
        prob = 0
        if model in base_pool:
            prob += prob_model1
        if model in opponent_pool:
            prob += prob_model2
        low_choice_probs[model] += PROB_CROSS_TIER * prob

    # B.3: 过渡区挑战
    base_pool_trans = [m for m in low_tier_models if m in transition_zone_models]
    opponent_pool_trans = transition_zone_models
    prob_model1_trans = 1 / len(base_pool_trans) if base_pool_trans else 0
    prob_model2_trans = 1 / len(opponent_pool_trans) if opponent_pool_trans else 0
    for model in all_models:
        prob = 0
        if model in base_pool_trans:
            prob += prob_model1_trans
        if model in opponent_pool_trans:
            prob += prob_model2_trans
        low_choice_probs[model] += PROB_TRANSITION_ZONE * prob

    # 综合概率 (假设用户选择 high/low 的概率各为50%)
    for model in all_models:
        model_probabilities[model] = 0.5 * high_choice_probs[model] + 0.5 * low_choice_probs[model]
        
    # --- 4. 打印结果 ---
    print("--- 模型抽取概率计算结果 (假设权重为1) ---")
    print(f"总模型数: {len(all_models)}, High: {NUM_HIGH_TIER}, Low: {NUM_LOW_TIER}")
    print(f"过渡区大小: {len(transition_zone_models)}")
    print(f"概率: 常规={PROB_STANDARD:.2f}, 跨级={PROB_CROSS_TIER:.2f}, 过渡区={PROB_TRANSITION_ZONE:.2f}\n")

    print("--- 综合平均概率 ---")
    print("--- High Tier 模型 ---")
    for i in range(NUM_HIGH_TIER):
        model_id = f"H{i+1}"
        prob = model_probabilities[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")
    print("\n--- Low Tier 模型 ---")
    for i in range(NUM_LOW_TIER):
        model_id = f"L{i+1}"
        prob = model_probabilities[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")
    
    print("\n\n--- 若用户选择 [High Tier Battle] ---")
    print("--- High Tier 模型 ---")
    for i in range(NUM_HIGH_TIER):
        model_id = f"H{i+1}"
        prob = high_choice_probs[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")
    print("\n--- Low Tier 模型 ---")
    for i in range(NUM_LOW_TIER):
        model_id = f"L{i+1}"
        prob = high_choice_probs[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")

    print("\n\n--- 若用户选择 [Low Tier Battle] ---")
    print("--- High Tier 模型 ---")
    for i in range(NUM_HIGH_TIER):
        model_id = f"H{i+1}"
        prob = low_choice_probs[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")
    print("\n--- Low Tier 模型 ---")
    for i in range(NUM_LOW_TIER):
        model_id = f"L{i+1}"
        prob = low_choice_probs[model_id]
        zone_info = "(过渡区)" if model_id in transition_zone_models else ""
        print(f"{model_id:<5}: {prob:.4%} {zone_info}")

    print(f"\n--- 总概率校验 ---")
    total_prob = sum(model_probabilities.values())
    print(f"所有模型概率之和: {total_prob:.4f} (理论值应为 2.0，因为每场对战选2个模型)")


if __name__ == "__main__":
    calculate_probabilities()