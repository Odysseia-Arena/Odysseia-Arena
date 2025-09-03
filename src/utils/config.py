# config.py
import json
import os
import time
from dotenv import load_dotenv
from typing import List, Dict, Optional
from src.utils.logger_config import logger

load_dotenv() # 加载 .env 文件

# --- 核心路径定义 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(BASE_DIR, "src")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
MODELS_FILE = os.path.join(CONFIG_DIR, "models.json")
PRESET_MODELS_FILE = os.path.join(CONFIG_DIR, "preset_models.json") # 预制模型配置文件
MODEL_PRESET_MAPPING_FILE = os.path.join(CONFIG_DIR, "model_preset_mapping.json") # 模型可用预设映射
FIXED_PROMPTS_FILE = os.path.join(CONFIG_DIR, "fixed_prompts.json")
MODEL_SCORES_FILE = os.path.join(CONFIG_DIR, "model_scores.json") # 新增文件路径
PRESET_ANSWERS_DIR = os.path.join(CONFIG_DIR, "preset_answers") # 预制回答文件夹
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
GLICKO2_DEFAULT_RD = 100.0
# 新模型的初始波动性 (volatility / sigma)
GLICKO2_DEFAULT_VOL = 0.06

# --- 投票与对战速率限制 ---
VOTE_TIME_WINDOW = 30 * 60 # 30分钟内不能重复投票
BATTLE_CREATION_WINDOW = 60 * 60  # 1小时
MAX_BATTLES_PER_HOUR = int(os.getenv("MAX_BATTLES_PER_HOUR", 20))
MIN_BATTLE_INTERVAL = int(os.getenv("MIN_BATTLE_INTERVAL", 30))
# 并行对战限制 (0 表示无限制)
MAX_CONCURRENT_BATTLES = int(os.getenv("MAX_CONCURRENT_BATTLES", 1))

# --- 对战清理配置 ---
# API 请求和对战生成超时时间（秒）
GENERATION_TIMEOUT = int(os.getenv("GENERATION_TIMEOUT_SECONDS", 12 * 60))

# --- 回答选项生成器配置 ---
OPTION_LLM_API_URL = os.getenv("OPTION_LLM_API_URL", "http://127.0.0.1:5000/v1/chat/completions")
OPTION_LLM_API_KEY = os.getenv("OPTION_LLM_API_KEY", "your_api_key_here")
OPTION_LLM_MODEL = os.getenv("OPTION_LLM_MODEL", "your_model_id_here")

# --- 等级与升降级系统配置 ---
PROMOTION_RELEGATION_COUNT = 3      # 每日升降级模型的数量
TRANSITION_ZONE_SIZE = 5          # 过渡区大小（从每个等级中选出N个模型）
# --- 动态加载的匹配概率 ---
def get_match_probabilities() -> dict:
    """
    动态加载并返回匹配概率，以实现热重载。
    每次调用此函数都会重新加载 .env 文件。
    """
    load_dotenv() # 重新加载 .env 文件
    
    probabilities = {
        "transition_zone": float(os.getenv("TRANSITION_ZONE_PROBABILITY", 0.18)),
        "cross_tier_challenge": float(os.getenv("GLOBAL_RANDOM_MATCH_PROBABILITY", 0.20))
    }
    return probabilities

# --- 热更新配置 ---
class HotReloadConfig:
    def __init__(self, file_path, loader_func):
        self.file_path = file_path
        self.loader_func = loader_func
        self._cache = None
        self._last_mtime = 0

    def get_data(self):
        """获取数据，如果文件或目录已更新则重新加载"""
        try:
            current_mtime = 0
            # 检查是文件还是目录
            if os.path.isdir(self.file_path):
                # 目录：遍历所有文件，找到最新的修改时间
                latest_mtime = self._last_mtime
                if not os.path.exists(self.file_path):
                     os.makedirs(self.file_path)
                for filename in os.listdir(self.file_path):
                    filepath = os.path.join(self.file_path, filename)
                    if os.path.isfile(filepath):
                        try:
                            latest_mtime = max(latest_mtime, os.path.getmtime(filepath))
                        except FileNotFoundError:
                            pass # 文件可能在遍历时被删除
                current_mtime = latest_mtime
            elif os.path.isfile(self.file_path):
                # 文件：获取文件的修改时间
                current_mtime = os.path.getmtime(self.file_path)
            else:
                # 路径不存在
                if self._cache is None:
                    logger.error(f"错误: 找不到配置文件或目录 {self.file_path}")
                    self._cache = self.loader_func(self.file_path) # 尝试加载，让加载函数处理错误
                return self._cache

            if current_mtime > self._last_mtime:
                logger.info(f"检测到配置更新: {self.file_path}，重新加载...")
                self._cache = self.loader_func(self.file_path)
                self._last_mtime = current_mtime
                # 对字典和列表提供不同的日志输出
                if isinstance(self._cache, (dict, list)):
                    logger.info(f"成功加载 {len(self._cache)} 个条目。")
                else:
                    logger.info("成功加载配置。")

        except FileNotFoundError:
            if self._cache is None: # 首次加载失败
                logger.error(f"错误: 找不到配置文件 {self.file_path}")
                # 根据加载函数的预期返回类型，返回空字典或空列表
                self._cache = {} if "dict" in str(self.loader_func.__annotations__.get('return')).lower() else []
        except Exception as e:
            logger.error(f"加载配置文件 {self.file_path} 时出错: {e}")
            if self._cache is None:
                self._cache = {} if "dict" in str(self.loader_func.__annotations__.get('return')).lower() else []
        
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

def _load_prompts_from_file(file_path: str) -> Dict[str, str]:
    """从文件加载提示词字典"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 现在 prompts 是一个字典，直接返回它
        prompts_dict = data.get("prompts", {})
        if not isinstance(prompts_dict, dict):
            logger.error(f"错误: {file_path} 中的 'prompts' 应该是一个字典")
            return {}
        return prompts_dict
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {file_path}")
        return {}
    except Exception as e:
        logger.error(f"读取提示词文件 {file_path} 时发生未知错误: {e}")
        return {}

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

def _load_preset_models_from_file(file_path: str) -> List[Dict]:
    """从文件加载和验证预制模型列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        models = data.get("preset_models", [])
        if not isinstance(models, list):
            logger.error(f"错误: {file_path} 中的 'preset_models' 应该是一个列表")
            return []
        
        valid_models = []
        for model in models:
            if all(k in model for k in ["id", "api_url", "api_key", "filename"]):
                valid_models.append(model)
            else:
                logger.warning(f"警告: 跳过一个无效的预制模型条目，缺少必要字段。")
        return valid_models
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {file_path}")
        return []
    except Exception as e:
        logger.error(f"读取预制模型文件 {file_path} 时发生未知错误: {e}")
        return []

def _load_json_file(file_path: str) -> Dict:
    """通用JSON文件加载器"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"警告: 找不到配置文件 {file_path}。")
        return {}
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析JSON文件 {file_path}")
        return {}
    except Exception as e:
        logger.error(f"读取JSON文件 {file_path} 时发生未知错误: {e}")
        return {}

def _load_preset_answers_from_dir(dir_path: str) -> Dict[str, Dict]:
    """从目录加载所有预制回答JSON文件"""
    preset_answers = {}
    if not os.path.isdir(dir_path):
        logger.warning(f"预设回答目录不存在: {dir_path}")
        return {}
    
    for filename in os.listdir(dir_path):
        if filename.endswith(".json"):
            file_path = os.path.join(dir_path, filename)
            # 使用文件名（不含扩展名）作为key
            model_name = os.path.splitext(filename)[0]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "answer" in data and isinstance(data["answer"], dict):
                         preset_answers[model_name] = data["answer"]
                         logger.info(f"成功加载预制回答: {filename}")
                    else:
                        logger.warning(f"警告: 预制回答文件 {filename} 格式不正确，缺少 'answer' 字典。")
            except json.JSONDecodeError:
                logger.error(f"错误: 无法解析预制回答文件 {file_path}")
            except Exception as e:
                logger.error(f"读取预制回答文件 {file_path} 时发生未知错误: {e}")
    return preset_answers


# 初始化热更新配置
_models_config = HotReloadConfig(MODELS_FILE, _load_models_from_file)
_preset_models_config = HotReloadConfig(PRESET_MODELS_FILE, _load_preset_models_from_file)
_prompts_config = HotReloadConfig(FIXED_PROMPTS_FILE, _load_prompts_from_file)
_initial_scores_config = HotReloadConfig(MODEL_SCORES_FILE, _load_initial_scores_from_file)
_preset_answers_config = HotReloadConfig(PRESET_ANSWERS_DIR, _load_preset_answers_from_dir)
_model_preset_mapping_config = HotReloadConfig(MODEL_PRESET_MAPPING_FILE, _load_json_file)

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

def load_fixed_prompts() -> Dict[str, str]:
    """获取固定提示词字典（支持热更新）"""
    return _prompts_config.get_data()

def get_preset_answers() -> Dict[str, Dict]:
    """获取所有预制回答（支持热更新）"""
    return _preset_answers_config.get_data()

def get_preset_models() -> List[Dict]:
    """获取所有预制模型配置（支持热更新）"""
    return _preset_models_config.get_data()

def get_model_preset_mapping() -> Dict[str, List[str]]:
    """获取模型到其可用预设列表的映射（支持热更新）"""
    return _model_preset_mapping_config.get_data()


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