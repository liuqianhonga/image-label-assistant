import requests
import json
import os
import time

def translate_text(text, from_lang='en', to_lang='zh'):
    """
    翻译文本，使用Google翻译API（免费，无需密钥）
    从英文(en)翻译为中文(zh)
    """
    if not text:
        return ""
    
    return google_translate(text, from_lang, to_lang)

def google_translate(text, from_lang='en', to_lang='zh'):
    """
    使用Google翻译的免费API（无需密钥）
    """
    try:
        # 避免请求过于频繁
        time.sleep(0.5)
        
        # 注意：这是一个未经官方授权的免费使用方式，可能会有稳定性问题
        url = "https://translate.googleapis.com/translate_a/single"
        
        params = {
            "client": "gtx",
            "sl": from_lang,
            "tl": to_lang,
            "dt": "t",
            "q": text
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            result = response.json()
            
            # 提取翻译结果
            translated_text = ""
            if result and isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
                for item in result[0]:
                    if item and isinstance(item, list) and len(item) > 0:
                        translated_text += item[0]
            
            return translated_text
    except Exception as e:
        print(f"Google翻译API请求失败: {e}")
        return f"[翻译失败] {text}"
    