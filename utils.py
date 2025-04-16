import requests
import json
import os
import time
import config
from zhipuai import ZhipuAI

def translate_text(text, from_lang='en', to_lang='zh'):
    """
    使用智谱GLM模型翻译文本，默认从英文(en)翻译为中文(zh)
    """
    if not text:
        return ""
    
    # 准备提示词
    prompt = f"请将以下{from_lang}语言文本翻译成{to_lang}语言，仅返回翻译结果，不要有任何额外说明：\n\n{text}"

    # 获取智谱AI配置
    zhipu_config = config.get_zhipu_translate_config()
    
    # 从配置中获取API密钥和参数
    api_key = zhipu_config.get('api_key', '')
    model = zhipu_config.get('model', 'glm-4-flash-250414')
    temperature = zhipu_config.get('temperature', 0.7)
    max_tokens = zhipu_config.get('max_tokens', 2048)
    
    if not api_key:
        return "[调用失败] 智谱AI API密钥未配置，请在配置对话框中设置"
    
    # 避免请求过于频繁
    time.sleep(0.2)
    
    # 初始化客户端
    client = ZhipuAI(api_key=api_key)
    
    # 准备消息
    messages = [{"role": "user", "content": prompt}]
    
    # 调用API
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # 提取生成的文本
    if response and hasattr(response, 'choices') and len(response.choices) > 0:
        result_text = response.choices[0].message.content.strip()
        return result_text
    else:
        return f"[调用失败] 响应格式错误: {response}"
