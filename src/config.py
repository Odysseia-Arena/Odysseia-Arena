# config.py
import json
import os
import time
from dotenv import load_dotenv
from typing import List, Dict, Optional
from .logger_config import logger

load_dotenv() # 加载 .env 文件

# --- 核心路径定义 ---
CONFIG_DIR = "config"
MODELS_FILE = os.path.join(CONFIG_DIR, "models.json")
FIXED_PROMPTS_FILE = os.path.join(CONFIG_DIR, "fixed_prompts.json")
MODEL_SCORES_FILE = os.path.join(CONFIG_DIR, "model_scores.json") # 新增文件路径
DATA_DIR = "data"
FIXED_PROMPT_RESPONSES_FILE = os.path.join(DATA_DIR, "fixed_prompt_responses.json")

# --- Glicko-2 评分系统配置 ---
# --- Glicko-2 评分周期配置 ---
# 定义评分更新的周期（分钟）。
# 设置为 0 表示实时更新（每场比赛后立即更新）。
# 设置为大于 0 的值（例如 60）表示每 60 分钟批量更新一次周期内的所有比赛评分。
RATING_UPDATE_PERIOD_MINUTES = int(os.getenv("RATING_UPDATE_PERIOD_MINUTES", 0))

# Glicko-2 系统常量 (tau)，用于约束波动性随时间的变化。较小的值可防止波动性剧烈变化。
GLICKO2_TAU = 0.5
# 新模型的初始评分 (rating / mu)
GLICKO2_DEFAULT_RATING = 1500.0
# 新模型的初始评分偏差 (rating_deviation / phi)
GLICKO2_DEFAULT_RD = 350.0
# 新模型的初始波动性 (volatility / sigma)
GLICKO2_DEFAULT_VOL = 0.06

# --- 投票与对战速率限制 ---
VOTE_TIME_WINDOW = 30 * 60 # 30分钟内不能重复投票
BATTLE_CREATION_WINDOW = 60 * 60  # 1小时
MAX_BATTLES_PER_HOUR = int(os.getenv("MAX_BATTLES_PER_HOUR", 20))
MIN_BATTLE_INTERVAL = int(os.getenv("MIN_BATTLE_INTERVAL", 30))
ENABLE_SERIAL_BATTLE_LIMIT = os.getenv("ENABLE_SERIAL_BATTLE_LIMIT", "False").lower() in ('true', '1', 't')

# --- 对战清理配置 ---
GENERATION_TIMEOUT = 12 * 60      # 12分钟生成超时

# --- 等级与升降级系统配置 ---
PROMOTION_RELEGATION_COUNT = 3      # 每日升降级模型的数量
TRANSITION_ZONE_SIZE = 3          # 过渡区大小（从每个等级中选出N个模型）
TRANSITION_ZONE_PROBABILITY = 0.15 # 匹配到过渡区对战的概率 (15%)

# --- 热更新配置 ---
class HotReloadConfig:
    def __init__(self, file_path, loader_func):
        self.file_path = file_path
        self.loader_func = loader_func
        self._cache = None
        self._last_mtime = 0

    def get_data(self):
        """获取数据，如果文件已更新则重新加载"""
        try:
            current_mtime = os.path.getmtime(self.file_path)
            if current_mtime > self._last_mtime:
                logger.info(f"检测到配置文件更新: {self.file_path}，重新加载...")
                self._cache = self.loader_func(self.file_path)
                self._last_mtime = current_mtime
                logger.info(f"成功加载 {len(self._cache)} 个条目。")
        except FileNotFoundError:
            if self._cache is None: # 首次加载失败
                logger.error(f"错误: 找不到配置文件 {self.file_path}")
                self._cache = [] # 返回空列表以避免崩溃
        except Exception as e:
            logger.error(f"加载配置文件 {self.file_path} 时出错: {e}")
            if self._cache is None:
                self._cache = []
        
        return self._cache

    def force_reload(self):
        """强制重新加载配置文件"""
        try:
            self._cache = self.loader_func(self.file_path)
            self._last_mtime = os.path.getmtime(self.file_path)
            logger.info(f"已通过 force_reload 成功加载 {self.file_path} ({len(self._cache)} 个条目)。")
        except Exception as e:
            logger.error(f"强制重新加载配置文件 {self.file_path} 时失败: {e}")

def _load_models_from_file(file_path: str) -> List[Dict]:
    """从文件加载和验证模型列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        models = data.get("models", [])
        if not isinstance(models, list):
            logger.error(f"错误: {file_path} 中的 'models' 应该是一个列表")
            return []
        
        valid_models = []
        for model in models:
            if "id" in model and "name" in model:
                valid_models.append(model)
            else:
                logger.warning(f"警告: 跳过一个无效的模型条目，因为它缺少'id'或'name'字段。")
        return valid_models
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {file_path}")
        return []
    except Exception as e:
        logger.error(f"读取模型文件 {file_path} 时发生未知错误: {e}")
        return []

def _load_prompts_from_file(file_path: str) -> List[str]:
    """从文件加载提示词列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("prompts", [])
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {file_path}")
        return []
    except Exception as e:
        logger.error(f"读取提示词文件 {file_path} 时发生未知错误: {e}")
        return []

def _load_initial_scores_from_file(file_path: str) -> Dict:
    """从文件加载初始模型评分"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"警告: 找不到初始评分文件 {file_path}，将为所有新模型使用默认值。")
        return {}
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {file_path}")
        return {}
    except Exception as e:
        logger.error(f"读取初始评分文件 {file_path} 时发生未知错误: {e}")
        return {}

# 初始化热更新配置
_models_config = HotReloadConfig(MODELS_FILE, _load_models_from_file)
_prompts_config = HotReloadConfig(FIXED_PROMPTS_FILE, _load_prompts_from_file)
_initial_scores_config = HotReloadConfig(MODEL_SCORES_FILE, _load_initial_scores_from_file)

def get_initial_scores() -> Dict:
    """获取初始模型评分（支持热更新）"""
    return _initial_scores_config.get_data()

def get_models() -> List[Dict]:
    """获取当前可用的模型列表（支持热更新）"""
    return _models_config.get_data()

def get_model_by_id(model_id: str) -> Optional[Dict]:
    """根据ID获取模型对象（支持热更新）"""
    models = get_models()
    return next((model for model in models if model['id'] == model_id), None)

def load_fixed_prompts() -> List[str]:
    """获取固定提示词列表（支持热更新）"""
    return _prompts_config.get_data()


# --- 配置验证函数 ---
def validate_configuration():
    """验证系统配置是否满足最低运行要求"""
    errors = []
    
    models = get_models()
    if len(models) < 2:
        errors.append(f"系统至少需要2个模型才能运行对战 (当前: {len(models)})")
    
    prompts = load_fixed_prompts()
    if not prompts:
        errors.append("固定提示词文件不存在、为空或格式错误")
    
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            print(f"已创建数据目录: {DATA_DIR}")
        except Exception as e:
            errors.append(f"无法创建数据目录 {DATA_DIR}: {e}")
            
    is_valid = len(errors) == 0
    return is_valid, errors