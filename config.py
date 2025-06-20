import os
import json

# 定义保存配置的JSON文件路径
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

# 默认打标提示词配置
DEFAULT_PROMPT = """Describe this image in detail for AI image generation. Focus on visual elements, style, composition, and important details.

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

# Gemini相关默认配置
DEFAULT_GEMINI_CONFIG = {
    'api_key': '',
    'model': 'gemini-2.0-flash-exp',
    'temperature': 0.8,
    'max_output_tokens': 2048
}

# 默认智谱AI语言模型配置
DEFAULT_ZHIPU_LLM_CONFIG = {
    'api_key': '',
    'model': 'glm-4-flash-250414', 
    'temperature': 0.7,
    'max_tokens': 2048
}

# 默认智谱AI打标配置
DEFAULT_ZHIPU_LABEL_CONFIG = {
    'api_key': '',
    'model': 'glm-4v-plus-0111',  # 多模态打标模型，仅支持 glm-4v-plus-0111（收费）
    'temperature': 0.7,
    'max_tokens': 2048
}

# Florence2模型默认配置
DEFAULT_FLORENCE2_CONFIG = {
    'model': 'MiaoshouAI/Florence-2-large-PromptGen-v2.0',
    'device': 'cuda',  # 或 'cpu'
    'dtype': 'auto',   # 可选: 'auto', 'float16', 'float32' 等
    'prompt': '<DETAILED_CAPTION>',
    'max_new_tokens': 1024,
    'do_sample': True,
    'temperature': 0.6,
    'num_beams': 4,
    'top_p': 0.9,
}

# 可用Florence2 prompt选项
FLORENCE2_PROMPT_OPTIONS = [
    '<CAPTION>',
    '<DETAILED_CAPTION>',
    '<MORE_DETAILED_CAPTION>',
]

# 可用的Gemini模型列表
GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro"
]

# 可用的GLM模型列表
GLM_LLM_MODELS = ['glm-4-flash-250414']
# 可用的GLM打标模型列表
GLM_LABEL_MODELS = ['glm-4v-plus-0111']

# 可用Florence2模型列表
FLORENCE2_MODELS = [
    'MiaoshouAI/Florence-2-large-PromptGen-v2.0',
    'MiaoshouAI/Florence-2-base-PromptGen-v2.0',
    'microsoft/Florence-2-large-ft',
    'microsoft/Florence-2-base-ft',
    'microsoft/Florence-2-large',
    'microsoft/Florence-2-base',
]

def load_config():
    """加载配置文件"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'directories': [],
        'gemini_config': DEFAULT_GEMINI_CONFIG,
        'zhipu_llm_config': DEFAULT_ZHIPU_LLM_CONFIG,
        'zhipu_label_config': DEFAULT_ZHIPU_LABEL_CONFIG,
        'florence2_config': DEFAULT_FLORENCE2_CONFIG
    }

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

def get_zhipu_llm_config():
    """获取智谱AI语言模型配置"""
    config = load_config()
    if 'zhipu_llm_config' in config:
        return config['zhipu_llm_config']
    return DEFAULT_ZHIPU_LLM_CONFIG

def save_zhipu_llm_config(config_data):
    """保存智谱AI语言模型配置"""
    config = load_config()
    config['zhipu_llm_config'] = config_data
    return save_config(config)

def get_zhipu_label_config():
    """获取智谱AI打标配置"""
    config = load_config()
    if 'zhipu_label_config' in config:
        return config['zhipu_label_config']
    return DEFAULT_ZHIPU_LABEL_CONFIG

def save_zhipu_label_config(config_data):
    """保存智谱AI打标配置"""
    config = load_config()
    config['zhipu_label_config'] = config_data
    return save_config(config)

def get_florence2_config():
    """获取Florence2配置"""
    config_data = load_config()
    if 'florence2_config' in config_data:
        return config_data['florence2_config']
    return DEFAULT_FLORENCE2_CONFIG

def save_florence2_config(florence2_config):
    """保存Florence2配置"""
    config_data = load_config()
    config_data['florence2_config'] = florence2_config
    return save_config(config_data)

def update_directories(directories):
    """
    更新目录列表（支持带 prompt 字段）
    兼容字符串列表和 dict 列表
    """
    config = load_config()
    # 自动升级为 dict 格式
    dirs = []
    for d in directories:
        if isinstance(d, str):
            dirs.append({"path": d, "prompt": DEFAULT_PROMPT})
        elif isinstance(d, dict):
            # 兼容无 prompt 字段
            if 'prompt' not in d:
                d['prompt'] = DEFAULT_PROMPT
            dirs.append(d)
    config['directories'] = dirs
    return save_config(config)

def get_directories():
    """
    获取目录列表，返回 [{"path":..., "prompt":...}]，兼容老格式
    """
    config = load_config()
    dirs = config.get('directories', [])
    # 兼容老格式（字符串列表）
    if dirs and isinstance(dirs[0], str):
        dirs = [{"path": d, "prompt": DEFAULT_PROMPT} for d in dirs]
        config['directories'] = dirs
        save_config(config)
    # 兼容无 prompt 字段
    for d in dirs:
        if 'prompt' not in d:
            d['prompt'] = DEFAULT_PROMPT
    return dirs

def get_directory_prompts():
    """
    获取所有目录的 prompt 映射 {path: prompt}
    """
    return {d['path']: d.get('prompt', DEFAULT_PROMPT) for d in get_directories()}

def set_directory_prompt(path, prompt):
    """
    设置某个目录的 prompt
    """
    dirs = get_directories()
    updated = False
    for d in dirs:
        if d['path'] == path:
            d['prompt'] = prompt
            updated = True
            break
    if updated:
        update_directories(dirs)
    return updated

def update_directories_with_prompts(dirs_with_prompts):
    """
    批量更新目录及其 prompt，参数为 [{path, prompt}]
    """
    update_directories(dirs_with_prompts)
    return True
