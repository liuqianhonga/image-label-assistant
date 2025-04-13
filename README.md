# 图像打标助手

一个用于图像打标的工具，专为训练Lora模型设计。该工具可以使用Google Gemini API或本地Huggingface模型自动为图像生成英文标签，并提供中文翻译，方便用户理解和修改。

## 功能特点

- 手动管理图像目录，添加和删除目录
- 浏览图像，显示缩略图和文件名
- 支持多种打标模型：
  - Google Gemini AI（在线API）
  - 多种Huggingface Florence模型（本地运行）
- 支持中文翻译（使用Google翻译）
- 一键标注整个目录的图像
- 一键保存标注结果到文本文件
- 多行文本编辑支持，便于处理长描述
- 自动检测未保存内容，避免意外丢失
- 全屏显示界面，提供更好的工作体验

## 安装方法

1. 确保已安装Python 3.11或更高版本
2. 克隆或下载本仓库
3. 安装依赖包：

```bash
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu126

pip install -r requirements.txt
```

## 可用的图像打标模型

本工具支持以下模型进行图像打标：

1. **Gemini API（在线）**：
   - 需要Google AI Studio API密钥
   - 提供高质量的图像描述
   - 支持定制化提示词配置

2. **Florence系列模型（本地）**：
   - 无需API密钥，完全本地运行
   - 首次使用时会自动下载模型（约2GB）
   - 支持的模型包括：
     - MiaoshouAI/Florence-2-large-PromptGen-v2.0
     - MiaoshouAI/Florence-2-base-PromptGen-v2.0
     - microsoft/Florence-2-large-ft
     - microsoft/Florence-2-base-ft
     - microsoft/Florence-2-large
     - microsoft/Florence-2-base

### 切换模型

1. 在界面顶部的"模型"下拉菜单中选择所需模型
2. 选择后，"一键打标"按钮的文本会自动更新为当前所选模型
3. Florence模型首次使用时需要下载，请耐心等待
4. 如有GPU，Florence模型将自动使用GPU加速

## 配置 Gemini API

为了使用Gemini API进行图像标注，需要配置Google Gemini API：

1. 首次运行程序时会提示配置Gemini API
2. 获取Gemini API密钥：https://aistudio.google.com/
3. 在配置对话框中输入API密钥和选择模型
4. 可以调整温度和最大输出token等参数，适应不同需求
5. 配置完成后，系统会自动保存设置

### Prompt 配置说明

本程序默认配置了一个针对图像生成优化的prompt，它会指导Gemini API返回JSON格式的结果，包含以下字段：

```json
{
  "description": "A detailed description of the image.",
  "zh": "图像的详细描述。"
}
```

这个JSON格式包含两个关键字段：
- **description**: 英文详细描述，作为主要的图像标签
- **zh**: 中文翻译，帮助中文用户理解

您可以在Gemini配置对话框中自定义prompt，建议保持JSON格式不变，但可以调整提示词的具体要求。默认的prompt会指导模型关注图像的各个方面，包括：

1. 图像主体和动作
2. 场景与氛围
3. 艺术风格
4. 服装和外观特征
5. 构图和视角
6. 光线和色彩
7. 细节和纹理

## 使用方法

运行主程序：

```bash
python main.py
```

### 基本使用流程

1. 点击"选择"按钮通过文件对话框选择图像目录，目录会自动添加到列表
2. 在左侧列表中点击目录，右侧表格会显示该目录中的所有图像
3. 在顶部下拉菜单中选择要使用的模型（Gemini或Florence系列模型）
4. 点击单个图像旁的"打标"按钮生成标签，或使用顶部的"一键打标"批量处理
5. 可以输入"触发词"作为前缀添加到每个标签的开始
6. 手动编辑英文标签（支持多行编辑）
7. 点击"翻译"按钮获取中文翻译
8. 使用"一键保存"将所有标签保存为文本文件
9. 如需删除目录，选中左侧列表中的目录后点击"删除选中目录"按钮

### 内容修改提示

- 当表格内容被修改（无论手动修改、打标或翻译）后，切换目录时会提示保存
- 点击"一键保存"会将所有标签保存到文本文件，并清除修改标记

## 标签保存格式

标签将保存为与原图像同名的`.txt`文件，保存内容为标签的英文描述。

## 技术特性

- 使用PyQt5构建图形界面
- 多线程处理图像标注和翻译，避免界面冻结
- 支持在线API和本地模型的混合使用
- 使用Google Gemini API进行在线图像标注
- 使用Huggingface的Florence系列模型进行本地图像标注
- 使用Google翻译服务进行文本翻译
- 本地模型自动缓存，避免重复下载
- 数据缓存和配置保存

## 许可证

MIT