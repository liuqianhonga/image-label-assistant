import os
import requests
from PIL import Image
from io import BytesIO
import base64
import json
import time
import google.generativeai as genai
from config import DEFAULT_GEMINI_CONFIG, GEMINI_MODELS
import torch
from transformers import AutoModelForCausalLM, AutoProcessor
from huggingface_hub import snapshot_download
import shutil
import config
from zhipuai import ZhipuAI

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
        
        # Huggingface模型相关配置
        self.hf_model = None
        self.hf_model_id = "MiaoshouAI/Florence-2-large-PromptGen-v2.0"  # 默认模型ID
        self.use_hf_model = False  # 默认不使用Huggingface模型
        
        # 创建models目录
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
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
        根据配置使用Gemini、Huggingface或智谱多模态模型
        """
        # 判断使用哪个模型
        if self.model_name in ['glm-4v-flash', 'glm-4v']:
            print(f"使用智谱多模态模型: {self.model_name}")
            return self.label_with_zhipu_v_model(image_path)
        elif self.use_hf_model:
            print(f"使用Huggingface模型: {self.hf_model_id}")
            try:
                return self.label_with_hf_model(image_path)
            except Exception as e:
                error_message = f"使用Huggingface模型标注图像时出错: {e}"
                print(error_message)
                import traceback
                traceback.print_exc()
                return {"description": error_message, "zh": ""}
        else:
            # 使用Gemini模型
            return self.label_with_gemini(image_path)
    
    def label_with_gemini(self, image_path):
        """使用Gemini模型对图片进行标注"""
        try:
            # 确保API密钥已配置
            if not self.api_key:
                print("Gemini API key not configured")
                return {"description": "Gemini API key not configured", "zh": ""}
                
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
            result = {"description": response_text, "zh": ""}
            return result
            
        except Exception as e:
            error_message = f"使用Gemini标注图像时出错: {e}"
            print(error_message)
            # 保留这一个错误打印，用于调试
            import traceback
            traceback.print_exc()
            # 返回错误信息
            return {"description": error_message, "zh": ""}
    
    def get_model_local_path(self, model_id):
        """获取模型的本地路径，如果不存在则下载"""
        # 模型ID的最后一部分作为目录名
        model_name = model_id.split("/")[-1]
        local_model_path = os.path.join(self.models_dir, model_name)
        
        # 检查本地是否已存在模型
        if os.path.exists(local_model_path) and os.path.isdir(local_model_path):
            # 检查是否是有效的模型目录(至少包含config.json文件)
            if os.path.exists(os.path.join(local_model_path, "config.json")):
                print(f"模型已存在于本地: {local_model_path}")
                return local_model_path
        
        # 模型不存在，使用huggingface_hub下载
        print(f"模型不存在，正在从HuggingFace下载到 {local_model_path}...")
        try:
            # 使用snapshot_download下载模型
            snapshot_path = snapshot_download(
                repo_id=model_id,
                local_dir=local_model_path,
                local_dir_use_symlinks=False
            )
            print(f"模型下载完成: {snapshot_path}")
            return local_model_path
        except Exception as e:
            print(f"模型下载失败: {e}")
            # 如果下载失败，返回原始model_id，让transformers自行处理
            return model_id
    
    def label_with_zhipu_v_model(self, image_path):
        """使用智谱多模态模型对图片进行标注"""
        try:
            # 获取智谱AI配置
            zhipu_config = config.get_zhipu_label_config()
            api_key = zhipu_config.get('api_key', '')
            model = zhipu_config.get('model', 'glm-4v-flash')
            temperature = zhipu_config.get('temperature', 0.7)
            max_tokens = zhipu_config.get('max_tokens', 2048)
            
            if not api_key:
                return {"description": "[调用失败] 智谱AI API密钥未配置", "zh": ""}
            
            # 读取图像并转换为base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 构建提示词
            prompt = f"""请详细描述这张图片的内容，包括：
1. 主要对象和动作
2. 场景和氛围
3. 艺术风格
4. 服装和外观
5. 构图和视角
6. 光线和色彩
7. 细节和纹理

使用以下JSON格式返回结果：
{{
  "description": "英文描述",
  "zh": "中文描述"
}}"""
            
            # 初始化客户端
            client = ZhipuAI(api_key=api_key)
            
            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
            
            # 调用API
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 处理响应
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                result_text = response.choices[0].message.content.strip()
                
                # 尝试解析JSON
                try:
                    result = json.loads(result_text)
                    if 'description' in result:
                        return result
                except json.JSONDecodeError:
                    pass
                
                # 如果无法解析为JSON，返回原始文本
                return {"description": result_text, "zh": ""}
            else:
                return {"description": f"[调用失败] 响应格式错误: {response}", "zh": ""}
                
        except Exception as e:
            error_message = f"使用智谱多模态模型标注图像时出错: {str(e)}"
            print(error_message)
            import traceback
            traceback.print_exc()
            return {"description": error_message, "zh": ""}

    def label_with_hf_model(self, image_path):
        """使用huggingface模型在本地对图片进行标注"""
        
        try:
            # 正常打开图像文件
            image = Image.open(image_path)
            
            # 初始化模型和处理器
            if self.hf_model is None:
                # 使用设置的模型ID
                model_id = self.hf_model_id
                
                print(f"正在加载模型: {model_id}")
                
                # 设置设备并提供更多调试信息
                cuda_available = torch.cuda.is_available()
                if cuda_available:
                    device = "cuda"
                    gpu_name = torch.cuda.get_device_name(0)
                    print(f"检测到GPU: {gpu_name}")
                    print(f"CUDA版本: {torch.version.cuda}")
                else:
                    device = "cpu"
                    print("未检测到GPU或CUDA环境有问题，将使用CPU进行处理，速度可能较慢")
                    print(f"PyTorch版本: {torch.__version__}")
                    if hasattr(torch, 'cuda') and hasattr(torch.cuda, 'is_available'):
                        print(f"CUDA是否可用: {torch.cuda.is_available()}")
                    
                print(f"使用设备: {device}")
                
                # 获取模型的本地路径
                local_model_path = self.get_model_local_path(model_id)
                
                # 加载处理器 - 添加trust_remote_code=True参数
                processor = AutoProcessor.from_pretrained(local_model_path, trust_remote_code=True)
                
                # 加载模型 - 添加trust_remote_code=True参数
                # 对于CUDA，使用float16，对于CPU，使用float32
                model_dtype = torch.float16 if cuda_available else torch.float32
                model = AutoModelForCausalLM.from_pretrained(
                    local_model_path, 
                    torch_dtype=model_dtype,
                    trust_remote_code=True
                )
                model.to(device)
                
                # 保存到实例变量中
                self.hf_model = {"model": model, "processor": processor, "device": device, "dtype": model_dtype, "model_id": model_id}
            
            # 获取保存的模型和处理器
            model = self.hf_model["model"]
            processor = self.hf_model["processor"]
            device = self.hf_model["device"]
            model_dtype = self.hf_model["dtype"]
            
            # 如果当前加载的模型ID与设置的模型ID不匹配，则需要重新加载模型
            if self.hf_model.get("model_id") != self.hf_model_id:
                print(f"模型ID已更改，从 {self.hf_model.get('model_id')} 切换到 {self.hf_model_id}")
                # 清空模型以强制重新加载
                self.hf_model = None
                # 递归调用自身以加载新模型
                return self.label_with_hf_model(image_path)
            
            # 准备提示词 - 使用配置中的提示词
            prompt = self.prompt
            
            # 处理图像和文本
            inputs = processor(text=prompt, images=image, return_tensors="pt", do_rescale=False).to(model_dtype).to(device)
            
            print("开始生成描述...")
            # 生成描述
            with torch.no_grad():
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    do_sample=True,
                    temperature=0.6,
                    num_beams=4,
                    top_p=0.9,
                )

            # 解码生成的文本
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # 获取生成的描述文本
            description = generated_text.strip()
            
            # 尝试解析生成的文本为JSON格式，与Gemini模型处理方式保持一致
            result = {"description": description, "zh": ""}
            
            print(description)

            try:
                # 检查是否有可能是JSON格式
                if '{' in description and '}' in description:
                    # 提取JSON部分（可能需要处理模型输出的多余文本）
                    json_text = description
                    # 如果JSON前后有文本，尝试提取JSON部分
                    start_idx = description.find('{')
                    end_idx = description.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_text = description[start_idx:end_idx]
                    
                    # 解析JSON
                    parsed_result = json.loads(json_text)
                    
                    # 检查是否包含所需字段
                    if 'description' in parsed_result:
                        # 返回包含JSON数据的字典
                        result = parsed_result
            except json.JSONDecodeError:
                # JSON解析失败，使用普通文本处理
                pass
            
            return result
        
        except Exception as e:
            error_message = f"使用Huggingface模型标注图像时出错: {e}"
            print(error_message)
            import traceback
            traceback.print_exc()
            raise Exception(error_message)
