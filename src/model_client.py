# model_client.py
"""简单的OpenAI格式API客户端"""

import os
import requests
import time
from typing import Optional
from dotenv import load_dotenv

# 在模块加载时执行一次，确保.env文件被找到
load_dotenv()

MAX_RETRIES = 2  # 最大重试次数（包括首次请求）
RETRY_DELAY = 1  # 重试间隔（秒）

def call_model(model: dict, prompt: str) -> str:
    """
    调用模型API生成响应，支持专属/全局配置和配置热更新
    
    Args:
        model: 模型对象 (包含 id, name, api_url, api_key)
        prompt: 提示词
        
    Returns:
        生成的文本响应
        
    Raises:
        ValueError: API_KEY未设置或模型持续返回空响应
        Exception: API调用失败
    """
    # 热更新：每次调用时都强制重新加载.env文件以获取最新的全局配置
    load_dotenv(override=True)
    
    model_id = model['id']
    
    # 分层配置逻辑
    # 1. 优先使用模型专属配置 (确保检查 .get 的结果不为空字符串)
    api_url = model.get('api_url')
    api_key = model.get('api_key')

    # 2. 如果专属配置为空，则回退到全局环境变量
    if not api_url:
        api_url = os.getenv("API_ENDPOINT", "https://api.openai.com/v1/chat/completions")
    if not api_key:
        api_key = os.getenv("API_KEY", "")

    # 3. 最终检查配置是否存在
    if not api_key:
        raise ValueError(f"模型 '{model_id}' 既无专属API Key也无全局API Key配置。")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.0,
        "stream": False
    }
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=360
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                content = content.strip()
                
                if content:
                    return content
                else:
                    print(f"警告: 模型 {model_id} 返回空响应 (尝试 {attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise ValueError(f"模型 {model_id} 在 {MAX_RETRIES} 次尝试后仍返回空响应")
            else:
                raise Exception(f"API调用失败 ({response.status_code}): {response.text}")
        
        except requests.exceptions.Timeout:
            last_error = f"API调用超时 (model: {model_id})"
            if attempt < MAX_RETRIES - 1:
                print(f"警告: {last_error} (尝试 {attempt + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(last_error)
        except ValueError:
            raise
        except Exception as e:
            last_error = f"API调用错误 (model: {model_id}): {str(e)}"
            if attempt < MAX_RETRIES - 1:
                print(f"警告: {last_error} (尝试 {attempt + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(last_error)
    
    raise Exception(f"意外错误: 重试逻辑失败 (model: {model_id})")