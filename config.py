import os
import json

# 定义保存配置的JSON文件路径
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

# Gemini相关默认配置
DEFAULT_GEMINI_CONFIG = {
    'api_key': '',
    'model': 'gemini-2.0-flash-exp',
    'temperature': 0.8,
    'max_output_tokens': 2048,
    'prompt': """Describe this image in detail for AI image generation. Focus on visual elements, style, composition, and important details.

Use this JSON schema:
{
  "description": "A detailed description of the image.",
  "zh": "图像的详细描述。"
}

Your response should focus on:
1. The main subject and actions
2. Scene and atmosphere
3. Artistic style
4. Clothing and appearance
5. Composition and perspective
6. Lighting and colors
7. Details and textures

Return only the JSON object with these two fields."""
}

# 可用的Gemini模型列表
GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro"
]

def load_config():
    """加载配置文件"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
    return {'directories': [], 'gemini_config': DEFAULT_GEMINI_CONFIG}

def save_config(config_data):
    """保存配置到文件"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存配置文件时出错: {e}")
        return False

def get_gemini_config():
    """获取Gemini配置"""
    config = load_config()
    if 'gemini_config' in config:
        return config['gemini_config']
    return DEFAULT_GEMINI_CONFIG

def save_gemini_config(gemini_config):
    """保存Gemini配置"""
    config = load_config()
    config['gemini_config'] = gemini_config
    return save_config(config)

def update_directories(directories):
    """更新目录列表"""
    config = load_config()
    config['directories'] = directories
    return save_config(config)

def get_directories():
    """获取目录列表"""
    config = load_config()
    if 'directories' in config:
        return config['directories']
    return [] 