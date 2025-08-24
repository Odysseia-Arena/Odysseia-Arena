# model_client.py
"""支持多种API格式的模型客户端"""

import os
import requests
import time
from typing import Optional
from dotenv import load_dotenv

# 在模块加载时执行一次，确保.env文件被找到
load_dotenv()

MAX_RETRIES = 2  # 最大重试次数（包括首次请求）
RETRY_DELAY = 1  # 重试间隔（秒）

def _call_openai_format(model: dict, prompt: str, api_key: str, api_url: str) -> str:
    """使用OpenAI格式调用模型"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model['id'],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "stream": False
    }
    response = requests.post(api_url, headers=headers, json=payload, timeout=360)
    
    if response.status_code == 200:
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip()
    else:
        raise Exception(f"API调用失败 ({response.status_code}): {response.text}")

def _call_anthropic_format(model: dict, prompt: str, api_key: str, api_url: str) -> str:
    """使用requests手动构建对Anthropic API的调用"""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model['id'],
        "max_tokens": 32000,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0
    }
    
    # 如果用户没有在config/models.json中提供api_url，则使用默认值
    final_api_url = api_url if api_url else "https://api.anthropic.com/v1/messages"

    response = requests.post(final_api_url, headers=headers, json=payload, timeout=360)

    if response.status_code == 200:
        data = response.json()
        content_list = data.get("content", [])
        if content_list and isinstance(content_list, list) and len(content_list) > 0:
            first_block = content_list[0]
            if first_block.get("type") == "text":
                return first_block.get("text", "").strip()
        return "" # 如果响应格式不符合预期，返回空字符串
    else:
        raise Exception(f"API调用失败 ({response.status_code}): {response.text}")

def call_model(model: dict, prompt: str) -> str:
    """
    调用模型API生成响应，支持多种API格式和配置热更新
    """
    load_dotenv(override=True)
    
    model_id = model['id']
    api_format = model.get('api_format', 'openai') # 默认为openai格式

    api_url = model.get('api_url')
    api_key = model.get('api_key')

    if not api_key:
        api_key = os.getenv("API_KEY", "")
    
    # 为两种格式设置默认URL（如果未提供）
    if not api_url:
        if api_format == 'anthropic':
            api_url = "https://api.anthropic.com/v1/messages"
        else: # openai
            api_url = os.getenv("API_ENDPOINT", "https://api.openai.com/v1/chat/completions")

    if not api_key:
        raise ValueError(f"模型 '{model_id}' 既无专属API Key也无全局API Key配置。")

    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            content = ""
            if api_format == 'anthropic':
                content = _call_anthropic_format(model, prompt, api_key, api_url)
            else: # 默认为 openai
                content = _call_openai_format(model, prompt, api_key, api_url)
            
            if content:
                return content
            else:
                print(f"警告: 模型 {model_id} 返回空响应 (尝试 {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    raise ValueError(f"模型 {model_id} 在 {MAX_RETRIES} 次尝试后仍返回空响应")

        except requests.exceptions.Timeout:
            last_error = f"API调用超时 (model: {model_id})"
        except ValueError:
            raise
        except Exception as e:
            last_error = f"API调用错误 (model: {model_id}): {str(e)}"
        
        print(f"警告: {last_error} (尝试 {attempt + 1}/{MAX_RETRIES})")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            raise Exception(last_error)
            
    raise Exception(f"意外错误: 重试逻辑失败 (model: {model_id})")