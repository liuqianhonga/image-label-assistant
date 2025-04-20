import translators as ts

def translate_text(text, from_lang='en', to_lang='zh'):
    """
    使用Bing翻译服务翻译文本（通过translators库实现），默认从英文(en)翻译为中文(zh)
    """
    if not text:
        return ""
    
    try:
        # 使用translators库调用Bing翻译
        result = ts.translate_text(text, translator='bing', from_language=from_lang, to_language=to_lang)
        return result
    except Exception as e:
        return f"[翻译失败] {str(e)}"
