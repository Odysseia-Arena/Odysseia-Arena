# config.py
import json
import os

# 定义配置文件的路径
CONFIG_DIR = "config"
MODELS_FILE = os.path.join(CONFIG_DIR, "models.json")
FIXED_PROMPTS_FILE = os.path.join(CONFIG_DIR, "fixed_prompts.json")
DATA_DIR = "data"
FIXED_PROMPT_RESPONSES_FILE = os.path.join(DATA_DIR, "fixed_prompt_responses.json")

# ELO评分系统配置
DEFAULT_ELO_RATING = 1200
K_FACTOR = 32

# 投票配置 (秒)
VOTE_TIME_WINDOW = 30 * 60 # 30分钟内不能重复投票
USER_RATE_LIMIT_WINDOW = 60 * 60 # 1小时
USER_MAX_VOTES_PER_HOUR = 100 # 每个用户每小时最大投票数（设高一点以方便测试）


def load_models():
    """从 models.json 加载可用模型对象列表"""
    if not os.path.exists(MODELS_FILE):
        print(f"错误: 找不到模型配置文件 {MODELS_FILE}")
        return []
    try:
        with open(MODELS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 验证基本结构
            models = data.get("models", [])
            if not isinstance(models, list):
                print(f"错误: {MODELS_FILE} 中的 'models' 应该是一个列表")
                return []
            # 验证每个模型对象是否包含'id'和'name'
            for model in models:
                if "id" not in model or "name" not in model:
                    print(f"警告: 跳过一个无效的模型条目，因为它缺少'id'或'name'字段。")
                    continue
            return models
    except json.JSONDecodeError:
        print(f"错误: 无法解析 {MODELS_FILE}")
        return []

def load_fixed_prompts():
    """从 fixed_prompts.json 加载固定提示词列表"""
    if not os.path.exists(FIXED_PROMPTS_FILE):
        print(f"警告: 找不到固定提示词文件 {FIXED_PROMPTS_FILE}")
        return []
    try:
        with open(FIXED_PROMPTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("prompts", [])
    except json.JSONDecodeError:
        print(f"错误: 无法解析 {FIXED_PROMPTS_FILE}")
        return []

# 可用模型列表
AVAILABLE_MODELS = load_models()
# 创建一个从 model_id 到 model 对象的快速查找映射
MODELS_BY_ID = {model['id']: model for model in AVAILABLE_MODELS}

def get_model_by_id(model_id: str):
    """根据ID获取模型对象"""
    return MODELS_BY_ID.get(model_id)

# 配置验证函数
def validate_configuration():
    """验证系统配置是否满足最低运行要求"""
    errors = []
    
    # 至少需要2个模型才能进行对战
    if len(AVAILABLE_MODELS) < 2:
        errors.append(f"系统至少需要2个模型才能运行对战")
    
    # 检查固定提示词文件是否存在且有效
    prompts = load_fixed_prompts()
    if not prompts:
        errors.append("固定提示词文件不存在、为空或格式错误")
    
    # 检查必要的目录是否存在
    if not os.path.exists(CONFIG_DIR):
        errors.append(f"配置目录不存在: {CONFIG_DIR}")
    
    if not os.path.exists(DATA_DIR):
        # 数据目录不存在时自动创建
        try:
            os.makedirs(DATA_DIR)
            print(f"已创建数据目录: {DATA_DIR}")
        except Exception as e:
            errors.append(f"无法创建数据目录 {DATA_DIR}: {e}")
    
    is_valid = len(errors) == 0
    return is_valid, errors