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

def call_model(model: str, prompt: str) -> str:
    """
    调用模型API生成响应，包含空响应重试机制和配置热更新
    
    Args:
        model: 模型名称
        prompt: 提示词
        
    Returns:
        生成的文本响应
        
    Raises:
        ValueError: API_KEY未设置或模型持续返回空响应
        Exception: API调用失败
    """
    # 热更新：每次调用时都强制重新加载.env文件
    load_dotenv(override=True)
    api_endpoint = os.getenv("API_ENDPOINT", "https://api.openai.com/v1/chat/completions")
    api_key = os.getenv("API_KEY", "")

    if not api_key:
        raise ValueError("API_KEY 未设置，请在 .env 文件中配置")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7,
        "stream": False
    }
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 去除空白字符后检查是否为空
                content = content.strip()
                
                if content:
                    # 成功获取非空响应
                    return content
                else:
                    # 空响应，记录并可能重试
                    print(f"警告: 模型 {model} 返回空响应 (尝试 {attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise ValueError(f"模型 {model} 在 {MAX_RETRIES} 次尝试后仍返回空响应")
            else:
                raise Exception(f"API调用失败 ({response.status_code}): {response.text}")
        
        except requests.exceptions.Timeout:
            last_error = f"API调用超时 (model: {model})"
            if attempt < MAX_RETRIES - 1:
                print(f"警告: {last_error} (尝试 {attempt + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(last_error)
        except ValueError:
            # 空响应错误，直接抛出不重试
            raise
        except Exception as e:
            last_error = f"API调用错误 (model: {model}): {str(e)}"
            if attempt < MAX_RETRIES - 1:
                print(f"警告: {last_error} (尝试 {attempt + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(last_error)
    
    # 理论上不应该到达这里
    raise Exception(f"意外错误: 重试逻辑失败 (model: {model})")