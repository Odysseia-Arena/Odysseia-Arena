# model_client.py
"""支持多种API格式的模型客户端"""

import os
import re
import asyncio
from typing import Optional, List, Dict
from dotenv import load_dotenv
from curl_cffi.requests import AsyncSession
from src.utils import config

load_dotenv()

class ModelCallError(Exception):
    """模型调用失败时的特定异常。"""
    pass

MAX_ATTEMPTS_PER_KEY = 3
RETRY_DELAY = 1

def _strip_think_block(text: str) -> str:
    """移除响应文本中被 <think>...</think> 包裹的内容。"""
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()

async def _call_openai_format(session: AsyncSession, model_id_to_call: str, prompt: str, api_key: str, api_url: str, model_config: dict) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_id_to_call,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "stream": False
    }
    
    # 根据模型配置动态添加 thinking 参数
    if model_config.get("enable_thinking"):
        payload["thinking"] = {"type": "enabled"}

    response = await session.post(
        api_url, headers=headers, json=payload, timeout=config.GENERATION_TIMEOUT, impersonate="chrome110"
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError("API返回空响应")
    return _strip_think_block(content)

async def _call_anthropic_format(session: AsyncSession, model_id_to_call: str, prompt: str, api_key: str, api_url: str) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    payload = {
        "model": model_id_to_call,
        "max_tokens": 32000,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0
    }
    response = await session.post(
        api_url, headers=headers, json=payload, timeout=config.GENERATION_TIMEOUT, impersonate="chrome110"
    )
    response.raise_for_status()
    data = response.json()
    content_list = data.get("content", [])
    if content_list and isinstance(content_list, list) and len(content_list) > 0:
        first_block = content_list[0]
        if first_block.get("type") == "text":
            content = first_block.get("text", "")
            if not content:
                raise ValueError("API返回空响应")
            return _strip_think_block(content)
    raise ValueError("API返回了非预期的格式")

async def call_model(model: dict, prompt: str) -> str:
    """
    (异步) 调用模型API，在函数内部管理Session，实现渠道和密钥轮询。
    """
    load_dotenv(override=True)
    
    public_id = model['id']
    api_format = model.get('api_format', 'openai')
    
    channels_to_try = []
    internal_models = model.get("internal_models")
    if internal_models and isinstance(internal_models, list) and len(internal_models) > 0:
        channels_to_try = internal_models
    else:
        channels_to_try.append({
            "internal_id": public_id,
            "api_url": model.get("api_url"),
            "api_keys": model.get("api_keys") or [os.getenv("API_KEY", "")]
        })

    last_exception = None
    
    async with AsyncSession() as session:
        for channel in channels_to_try:
            model_id_to_call = channel.get("internal_id")
            api_url = channel.get("api_url")
            api_keys = channel.get("api_keys")

            if not all([model_id_to_call, api_url, api_keys is not None]):
                print(f"警告: 跳过一个不完整的渠道配置: {channel}")
                continue

            for key_index, api_key in enumerate(api_keys):
                # 移除对空key的检查，允许无key调用
                for attempt in range(MAX_ATTEMPTS_PER_KEY):
                    try:
                        print(f"INFO: 调用模型 '{public_id}' (渠道: {model_id_to_call}, Key #{key_index + 1}, 尝试 #{attempt + 1})")
                        if api_format == 'anthropic':
                            # 注意：anthropic 格式调用也需要传递 model 字典，以备未来扩展
                            return await _call_anthropic_format(session, model_id_to_call, prompt, api_key, api_url)
                        else:
                            # 将完整的 model 字典传递给 openai 格式调用函数
                            return await _call_openai_format(session, model_id_to_call, prompt, api_key, api_url, model_config=model)
                    
                    except Exception as e:
                        last_exception = e
                        print(f"警告: 调用失败 (渠道: {model_id_to_call}, Key #{key_index + 1}, 尝试 #{attempt + 1}): {e}")
                        if attempt < MAX_ATTEMPTS_PER_KEY - 1:
                            await asyncio.sleep(RETRY_DELAY)
                        else:
                            break 
            
            print(f"INFO: 渠道 '{model_id_to_call}' 的所有Key均调用失败，尝试下一个渠道...")

    raise ModelCallError(f"模型 '{public_id}' 在用尽所有内部渠道和API Key后仍调用失败。") from last_exception