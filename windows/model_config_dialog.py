from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QTabWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPushButton, QGroupBox, QCheckBox, QFormLayout
)
from PyQt5.QtCore import Qt
import config

class ModelConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API配置")
        self.setMinimumWidth(800)
        self.layout = QVBoxLayout(self)
        
        # 设置对话框居中显示
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)  # 移除帮助按钮
        
        # 创建选项卡
        self.tabs = QTabWidget()
        self.gemini_tab = QWidget()
        self.zhipu_tab = QWidget()
        self.florence2_tab = QWidget()
        
        self.tabs.addTab(self.gemini_tab, "Gemini配置")
        self.tabs.addTab(self.zhipu_tab, "智谱AI配置")
        self.tabs.addTab(self.florence2_tab, "Florence2配置")
        
        self.layout.addWidget(self.tabs)
        
        # 获取当前配置
        current_gemini_config = config.get_gemini_config()
        current_zhipu_translate_config = config.get_zhipu_translate_config()
        current_zhipu_label_config = config.get_zhipu_label_config()
        current_florence2_config = config.get_florence2_config()

        # 如果没有提供当前配置，使用默认配置
        if not current_gemini_config:
            current_gemini_config = config.DEFAULT_GEMINI_CONFIG
            
        if not current_zhipu_translate_config:
            current_zhipu_translate_config = config.get_zhipu_translate_config()
        
        if not current_zhipu_label_config: 
            current_zhipu_label_config = config.get_zhipu_label_config()
            
        if not current_florence2_config:
            current_florence2_config = config.get_florence2_config()
            
        # 设置Gemini选项卡
        self.setup_gemini_tab(current_gemini_config)
        
        # 设置智谱AI选项卡
        self.setup_zhipu_tab(current_zhipu_translate_config, current_zhipu_label_config)
        
        # 设置Florence2选项卡
        self.setup_florence2_tab(current_florence2_config)
        
        # 按钮
        buttons_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        self.layout.addLayout(buttons_layout)
    
    def setup_gemini_tab(self, current_config):
        """设置Gemini选项卡"""
        gemini_layout = QVBoxLayout(self.gemini_tab)
        
        # API密钥
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API密钥:")
        self.gemini_api_key_input = QLineEdit()
        self.gemini_api_key_input.setPlaceholderText("输入Google AI Studio API密钥")
        if 'api_key' in current_config:
            self.gemini_api_key_input.setText(current_config['api_key'])
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.gemini_api_key_input)
        gemini_layout.addLayout(api_key_layout)
        
        # Gemini配置区域
        config_group = QGroupBox("Gemini配置")
        config_layout = QVBoxLayout(config_group)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型:")
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems(config.GEMINI_MODELS)
        if 'model' in current_config:
            index = self.gemini_model_combo.findText(current_config['model'])
            if index >= 0:
                self.gemini_model_combo.setCurrentIndex(index)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.gemini_model_combo)
        config_layout.addLayout(model_layout)
        
        # 温度设置
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度:")
        self.gemini_temp_spin = QDoubleSpinBox()
        self.gemini_temp_spin.setRange(0.0, 2.0)
        self.gemini_temp_spin.setSingleStep(0.1)
        self.gemini_temp_spin.setValue(current_config.get('temperature', 0.8))
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.gemini_temp_spin)
        config_layout.addLayout(temp_layout)
        
        # 最大输出长度
        max_tokens_layout = QHBoxLayout()
        max_tokens_label = QLabel("最大输出长度:")
        self.gemini_max_tokens_spin = QSpinBox()
        self.gemini_max_tokens_spin.setRange(1, 8192)
        self.gemini_max_tokens_spin.setSingleStep(100)
        self.gemini_max_tokens_spin.setValue(current_config.get('max_output_tokens', 2048))
        max_tokens_layout.addWidget(max_tokens_label)
        max_tokens_layout.addWidget(self.gemini_max_tokens_spin)
        config_layout.addLayout(max_tokens_layout)
        
        # 添加配置组到主布局
        gemini_layout.addWidget(config_group)
        
        # 添加弹性空间
        gemini_layout.addStretch(1)
        
    def setup_zhipu_tab(self, current_translate_config, current_label_config):
        """设置智谱AI选项卡"""
        zhipu_layout = QVBoxLayout(self.zhipu_tab)
        
        # API密钥
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API密钥:")
        self.zhipu_api_key_input = QLineEdit()
        self.zhipu_api_key_input.setPlaceholderText("输入智谱GLM API密钥")
        self.zhipu_api_key_input.setText(current_translate_config.get('api_key', ''))
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.zhipu_api_key_input)
        zhipu_layout.addLayout(api_key_layout)
        
        # 翻译配置区域
        translate_group = QGroupBox("翻译配置")
        translate_layout = QVBoxLayout(translate_group)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型:")
        self.zhipu_translate_model = QComboBox()
        self.zhipu_translate_model.addItems(config.GLM_TRANSLATE_MODELS)
        self.zhipu_translate_model.setCurrentText(current_translate_config.get('model', 'glm-4-flash-250414'))
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.zhipu_translate_model)
        translate_layout.addLayout(model_layout)
        
        # 温度设置
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度:")
        self.zhipu_translate_temp = QDoubleSpinBox()
        self.zhipu_translate_temp.setRange(0.0, 2.0)
        self.zhipu_translate_temp.setSingleStep(0.1)
        self.zhipu_translate_temp.setValue(current_translate_config.get('temperature', 0.7))
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.zhipu_translate_temp)
        translate_layout.addLayout(temp_layout)
        
        # 最大输出长度
        max_tokens_layout = QHBoxLayout()
        max_tokens_label = QLabel("最大输出长度:")
        self.zhipu_translate_max_tokens = QSpinBox()
        self.zhipu_translate_max_tokens.setRange(10, 8192)
        self.zhipu_translate_max_tokens.setSingleStep(100)
        self.zhipu_translate_max_tokens.setValue(current_translate_config.get('max_tokens', 2048))
        max_tokens_layout.addWidget(max_tokens_label)
        max_tokens_layout.addWidget(self.zhipu_translate_max_tokens)
        translate_layout.addLayout(max_tokens_layout)
        
        zhipu_layout.addWidget(translate_group)
        
        # 打标配置区域
        label_group = QGroupBox("打标配置")
        label_layout = QVBoxLayout(label_group)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型:")
        self.zhipu_label_model = QComboBox()
        self.zhipu_label_model.addItems(config.GLM_LABEL_MODELS)
        self.zhipu_label_model.setCurrentText(current_label_config.get('model', 'glm-4v-flash'))
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.zhipu_label_model)
        label_layout.addLayout(model_layout)
        
        # 温度设置
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度:")
        self.zhipu_label_temp = QDoubleSpinBox()
        self.zhipu_label_temp.setRange(0.0, 2.0)
        self.zhipu_label_temp.setSingleStep(0.1)
        self.zhipu_label_temp.setValue(current_label_config.get('temperature', 0.7))
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.zhipu_label_temp)
        label_layout.addLayout(temp_layout)
        
        # 最大输出长度
        max_tokens_layout = QHBoxLayout()
        max_tokens_label = QLabel("最大输出长度:")
        self.zhipu_label_max_tokens = QSpinBox()
        self.zhipu_label_max_tokens.setRange(10, 8192)
        self.zhipu_label_max_tokens.setSingleStep(100)
        self.zhipu_label_max_tokens.setValue(current_label_config.get('max_tokens', 2048))
        max_tokens_layout.addWidget(max_tokens_label)
        max_tokens_layout.addWidget(self.zhipu_label_max_tokens)
        label_layout.addLayout(max_tokens_layout)
        
        zhipu_layout.addWidget(label_group)
        
        # 添加功能说明
        features_group_box = QGroupBox("功能说明")
        features_layout = QVBoxLayout(features_group_box)
        
        # 翻译功能说明
        translate_label = QLabel("• 翻译：系统使用智谱AI进行高质量翻译，自动将英文标签翻译为中文。")
        translate_label.setWordWrap(True)
        features_layout.addWidget(translate_label)
        
        # 未来可能的功能说明
        future_label = QLabel("• 其它：智谱AI还可用于多种自然语言处理任务，后续版本可能增加更多功能。")
        future_label.setWordWrap(True)
        features_layout.addWidget(future_label)
        
        zhipu_layout.addWidget(features_group_box)
        
        # 添加提示说明
        note_label = QLabel("注意: 使用智谱AI需要在智谱AI官网注册并创建API密钥，详见 https://www.bigmodel.cn/")
        note_label.setWordWrap(True)
        zhipu_layout.addWidget(note_label)
        
        # 添加空白占位
        zhipu_layout.addStretch()
    
    def setup_florence2_tab(self, current_config):
        """设置Florence2选项卡（新版布局，参考智谱AI）"""
        florence2_layout = QVBoxLayout(self.florence2_tab)
        # Florence2配置组
        config_group = QGroupBox("Florence2模型配置")
        config_layout = QFormLayout(config_group)
        # 模型选择
        self.florence2_model_combo = QComboBox()
        self.florence2_model_combo.addItems(config.FLORENCE2_MODELS)
        if 'model' in current_config:
            index = self.florence2_model_combo.findText(current_config['model'])
            if index >= 0:
                self.florence2_model_combo.setCurrentIndex(index)
        config_layout.addRow(QLabel("模型："), self.florence2_model_combo)
        # prompt选择
        self.florence2_prompt_combo = QComboBox()
        self.florence2_prompt_combo.addItems(config.FLORENCE2_PROMPT_OPTIONS)
        if 'prompt' in current_config:
            index = self.florence2_prompt_combo.findText(current_config['prompt'])
            if index >= 0:
                self.florence2_prompt_combo.setCurrentIndex(index)
        config_layout.addRow(QLabel("提示词类型："), self.florence2_prompt_combo)
        # max_new_tokens
        self.florence2_max_new_tokens = QSpinBox()
        self.florence2_max_new_tokens.setRange(1, 4096)
        self.florence2_max_new_tokens.setValue(current_config.get('max_new_tokens', 1024))
        config_layout.addRow(QLabel("最大新Token数："), self.florence2_max_new_tokens)
        # temperature
        self.florence2_temperature = QDoubleSpinBox()
        self.florence2_temperature.setRange(0.0, 2.0)
        self.florence2_temperature.setSingleStep(0.01)
        self.florence2_temperature.setValue(current_config.get('temperature', 0.6))
        config_layout.addRow(QLabel("温度(temperature)："), self.florence2_temperature)
        # top_p
        self.florence2_top_p = QDoubleSpinBox()
        self.florence2_top_p.setRange(0.0, 1.0)
        self.florence2_top_p.setSingleStep(0.01)
        self.florence2_top_p.setValue(current_config.get('top_p', 0.9))
        config_layout.addRow(QLabel("Top-p采样："), self.florence2_top_p)
        # num_beams
        self.florence2_num_beams = QSpinBox()
        self.florence2_num_beams.setRange(1, 32)
        self.florence2_num_beams.setValue(current_config.get('num_beams', 4))
        config_layout.addRow(QLabel("束宽(num_beams)："), self.florence2_num_beams)
        # do_sample
        self.florence2_do_sample = QCheckBox("使用采样(do_sample)")
        self.florence2_do_sample.setChecked(current_config.get('do_sample', True))
        config_layout.addRow(self.florence2_do_sample)
        config_group.setLayout(config_layout)
        florence2_layout.addWidget(config_group)
        florence2_layout.addStretch(1)

    def get_gemini_config(self):
        """获取Gemini配置"""
        return {
            'api_key': self.gemini_api_key_input.text().strip(),
            'model': self.gemini_model_combo.currentText(),
            'temperature': self.gemini_temp_spin.value(),
            'max_output_tokens': self.gemini_max_tokens_spin.value()
            # prompt字段已移除，现在与目录一起配置
        }
    
    def get_zhipu_translate_config(self):
        """获取智谱AI翻译配置"""
        return {
            'api_key': self.zhipu_api_key_input.text().strip(),
            'model': self.zhipu_translate_model.currentText(),
            'temperature': self.zhipu_translate_temp.value(),
            'max_tokens': self.zhipu_translate_max_tokens.value()
        }
        
    def get_zhipu_label_config(self):
        """获取智谱AI打标配置"""
        return {
            'api_key': self.zhipu_api_key_input.text().strip(),
            'model': self.zhipu_label_model.currentText(),
            'temperature': self.zhipu_label_temp.value(),
            'max_tokens': self.zhipu_label_max_tokens.value()
        }
    
    def get_florence2_config(self):
        """获取Florence2配置"""
        return {
            'model': self.florence2_model_combo.currentText(),
            'prompt': self.florence2_prompt_combo.currentText(),
            'max_new_tokens': self.florence2_max_new_tokens.value(),
            'do_sample': self.florence2_do_sample.isChecked(),
            'temperature': self.florence2_temperature.value(),
            'num_beams': self.florence2_num_beams.value(),
            'top_p': self.florence2_top_p.value(),
        }