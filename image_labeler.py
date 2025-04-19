import os
import requests
from PIL import Image
from io import BytesIO
import base64
import json
import time
import google.generativeai as genai
from config import DEFAULT_GEMINI_CONFIG, DEFAULT_PROMPT
import torch
from transformers import AutoModelForCausalLM, AutoProcessor
from huggingface_hub import snapshot_download
import shutil
import config
from zhipuai import ZhipuAI
from enum import Enum

class LabelerType(Enum):
    GEMINI = "gemini"
    FLORENCE2 = "florence2"
    ZHIPU = "zhipu"

class ImageLabeler:
    """图像标注类，用于处理图像识别和标注"""
    
    def __init__(self):
        # 打标服务类型："gemini", "zhipu", "florence2"
        self.labeler_type = LabelerType.FLORENCE2  # 默认使用florence2模型
        
        # 模型实例缓存
        self.gemini_model = None  # Gemini模型实例
        self.hf_model = None      # Huggingface模型实例
        
        # Huggingface模型相关配置
        self.hf_model_id = "MiaoshouAI/Florence-2-large-PromptGen-v2.0"  # 默认模型ID
        
        # 创建models目录
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
    def label_image(self, image_path, current_directory=None):
        """
        对图片进行标注，返回英文描述
        根据 labeler_type 字段判断使用打标服务类型："gemini", "zhipu", "florence2"
        
        参数：
            image_path: 图片路径
            current_directory: 当前目录路径，用于获取目录特定的提示词
        """
        # 1. 使用Gemini打标服务
        if self.labeler_type == LabelerType.GEMINI:
            print("使用Gemini打标服务")
            return self.label_with_gemini(image_path, current_directory)
        
        # 2. 使用智谱打标服务
        elif self.labeler_type == LabelerType.ZHIPU:
            # 从配置中获取具体的模型名称
            zhipu_config = config.get_zhipu_label_config()
            model = zhipu_config.get('model', 'glm-4v-plus-0111')
            print(f"使用智谱打标服务: {model}")
            return self.label_with_zhipu_v_model(image_path, current_directory)
        
        # 3. 使用Florence2本地模型打标
        elif self.labeler_type == LabelerType.FLORENCE2:
            print(f"使用Florence2本地模型打标")
            try:
                return self.label_with_florence2_model(image_path)
            except Exception as e:
                print(f"Florence2模型打标出错: {e}")
                return None
        
        # 默认情况（应该不会进入这里，但为了安全起见）
        else:
            print(f"未知的打标服务类型: {self.labeler_type}，尝试使用Florence2模型")
            try:
                return self.label_with_florence2_model(image_path)
            except Exception as e:
                print(f"Florence2模型打标出错: {e}")
                return None
    
    def label_with_gemini(self, image_path, current_directory=None):
        """使用Gemini模型对图片进行标注"""
        try:
            # 从配置中获取Gemini配置
            gemini_config = config.get_gemini_config()
            api_key = gemini_config.get('api_key', '')
            model_name = gemini_config.get('model', 'gemini-2.0-flash-exp')
            temperature = gemini_config.get('temperature', 0.8)
            max_output_tokens = gemini_config.get('max_output_tokens', 2048)
            
            # 获取目录特定的提示词
            prompt = DEFAULT_PROMPT
            if current_directory:
                dir_prompts = config.get_directory_prompts()
                if current_directory in dir_prompts:
                    prompt = dir_prompts[current_directory]
            
            # 确保API密钥已配置
            if not api_key:
                print("Gemini API key not configured")
                return {"description": "[调用失败] Gemini API密钥未配置", "zh": ""}
                
            # 配置API
            genai.configure(api_key=api_key)
            
            # 初始化模型（如果尚未初始化或模型名称已更改）
            if not self.gemini_model or getattr(self.gemini_model, 'model_name', '') != model_name:
                print(f"初始化Gemini模型: {model_name}")
                self.gemini_model = genai.GenerativeModel(model_name)
            
            # 加载图像
            with Image.open(image_path) as img:
                # 如果需要，可以调整图像大小
                if max(img.width, img.height) > 2048:
                    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            
            # 生成响应
            response = self.gemini_model.generate_content(
                [prompt, img],
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens
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
    
    def label_with_zhipu_v_model(self, image_path, current_directory=None):
        """使用智谱多模态模型对图片进行标注"""
        try:
            # 获取智谱AI配置
            zhipu_config = config.get_zhipu_label_config()
            api_key = zhipu_config.get('api_key', '')
            model = zhipu_config.get('model', 'glm-4v-plus-0111')
            temperature = zhipu_config.get('temperature', 0.7)
            max_tokens = zhipu_config.get('max_tokens', 2048)
            
            # 获取目录特定的提示词
            # 使用与Gemini相同的默认提示词
            prompt = DEFAULT_PROMPT
            if current_directory:
                dir_prompts = config.get_directory_prompts()
                if current_directory in dir_prompts:
                    prompt = dir_prompts[current_directory]
            
            if not api_key:
                return {"description": "[调用失败] 智谱AI API密钥未配置", "zh": ""}
            
            # 读取图像并转换为base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 已经在方法开始获取了提示词，这里不需要再获取
            
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
                    # 检查是否是Markdown代码块包裹的JSON
                    if result_text.startswith('```') and '```' in result_text[3:]:
                        # 提取代码块内容
                        code_block = result_text.split('```', 2)[1]
                        if code_block.startswith('json'):
                            code_block = code_block[4:].strip()
                        else:
                            code_block = code_block.strip()
                        result_text = code_block
                    
                    # 尝试提取JSON部分
                    if '{' in result_text and '}' in result_text:
                        start_idx = result_text.find('{')
                        end_idx = result_text.rfind('}') + 1
                        if start_idx >= 0 and end_idx > start_idx:
                            json_text = result_text[start_idx:end_idx]
                            result = json.loads(json_text)
                            if 'description' in result:
                                return result
                    
                    # 直接尝试解析整个文本
                    result = json.loads(result_text)
                    if 'description' in result:
                        return result
                        
                except json.JSONDecodeError as e:
                    print(f"智谱模型返回的JSON解析失败: {e}")
                    print(f"原始响应: {result_text}")
                
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

    def label_with_florence2_model(self, image_path):
        """使用Florence2模型在本地对图片进行标注"""
        florence2_config = config.get_florence2_config()
        model_id = florence2_config.get('model', 'MiaoshouAI/Florence-2-large-PromptGen-v2.0')
        prompt = florence2_config.get('prompt', '<DETAILED_CAPTION>')
        max_new_tokens = florence2_config.get('max_new_tokens', 1024)
        do_sample = florence2_config.get('do_sample', True)
        temperature = florence2_config.get('temperature', 0.6)
        num_beams = florence2_config.get('num_beams', 4)
        top_p = florence2_config.get('top_p', 0.9)
        try:
            # 正常打开图像文件
            image = Image.open(image_path)
            
            # 初始化模型和处理器
            if self.hf_model is None:
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
            if self.hf_model.get("model_id") != model_id:
                print(f"模型ID已更改，从 {self.hf_model.get('model_id')} 切换到 {model_id}")
                # 清空模型以强制重新加载
                self.hf_model = None
                # 递归调用自身以加载新模型
                return self.label_with_florence2_model(image_path)
            
            # 准备提示词 - 使用配置中的prompt
            inputs = processor(text=prompt, images=image, return_tensors="pt", do_rescale=False).to(model_dtype).to(device)
            
            print("开始生成描述...")
            # 生成描述
            with torch.no_grad():
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=max_new_tokens,
                    do_sample=do_sample,
                    temperature=temperature,
                    num_beams=num_beams,
                    top_p=top_p,
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
            error_message = f"Florence2模型标注图像时出错: {e}"
            print(error_message)
            import traceback
            traceback.print_exc()
            raise Exception(error_message)
