import os
import requests
from PIL import Image
from io import BytesIO
import base64
import json
import time
import google.generativeai as genai
from config import DEFAULT_GEMINI_CONFIG, GEMINI_MODELS

class ImageLabeler:
    """图像标注类，用于处理图像识别和标注"""
    
    # 可用的Gemini模型列表
    GEMINI_MODELS = GEMINI_MODELS
    
    def __init__(self):
        # Gemini相关配置
        self.api_key = DEFAULT_GEMINI_CONFIG['api_key']
        self.model_name = DEFAULT_GEMINI_CONFIG['model']
        self.gemini_model = None
        self.temperature = DEFAULT_GEMINI_CONFIG['temperature']
        self.max_output_tokens = DEFAULT_GEMINI_CONFIG['max_output_tokens']
        self.prompt = DEFAULT_GEMINI_CONFIG['prompt']
        
    def configure_gemini(self, api_key, model_name="gemini-2.0-flash-exp", temperature=0.8, max_output_tokens=2048, prompt=None):
        """配置Gemini API"""
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        if prompt:
            self.prompt = prompt
            
        # 重置模型实例
        self.gemini_model = None
        
    def label_image(self, image_path):
        """
        对图片进行标注，返回英文描述
        使用Gemini模型进行图像标注
        """
        # 统一使用Gemini模式
        return self.label_with_gemini(image_path)
    
    def label_with_gemini(self, image_path):
        """使用Gemini模型对图片进行标注"""
        try:
            # 确保API密钥已配置
            if not self.api_key:
                print("Gemini API key not configured")
                return {"description": "Gemini API key not configured", "zh": "", "tags": []}
                
            # 配置API
            genai.configure(api_key=self.api_key)
            
            # 初始化模型（如果尚未初始化或模型名称已更改）
            if not self.gemini_model or self.gemini_model.model_name != self.model_name:
                self.gemini_model = genai.GenerativeModel(self.model_name)
            
            # 加载图像
            with Image.open(image_path) as img:
                # 如果需要，可以调整图像大小
                if max(img.width, img.height) > 2048:
                    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            
            # 生成响应
            response = self.gemini_model.generate_content(
                [self.prompt, img],
                generation_config=genai.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens
                )
            )
            
            # 获取响应文本
            response_text = response.text.strip()
            
            # 尝试解析JSON响应
            try:
                # 检查是否有可能是JSON格式
                if '{' in response_text and '}' in response_text:
                    # 提取JSON部分（可能需要处理模型输出的多余文本）
                    json_text = response_text
                    # 如果JSON前后有文本，尝试提取JSON部分
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_text = response_text[start_idx:end_idx]
                    
                    # 解析JSON
                    result = json.loads(json_text)
                    
                    # 检查是否包含所需字段
                    if 'description' in result:
                        # 返回包含JSON数据的字典
                        return result
                    
            except json.JSONDecodeError:
                # JSON解析失败，使用普通文本处理
                pass
            
            # 如果无法解析为JSON或缺少所需字段，返回原始响应
            result = {"description": response_text, "zh": "", "tags": []}
            return result
            
        except Exception as e:
            error_message = f"使用Gemini标注图像时出错: {e}"
            print(error_message)
            # 保留这一个错误打印，用于调试
            import traceback
            traceback.print_exc()
            # 返回错误信息
            return {"description": error_message, "zh": "", "tags": []} 