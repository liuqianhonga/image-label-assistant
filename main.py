import sys
import os
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QListWidget, QTableWidget, QTableWidgetItem
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLineEdit, QHeaderView, QFileDialog, QMessageBox
from PyQt5.QtWidgets import QLabel, QStyledItemDelegate, QDesktopWidget, QTextEdit, QAbstractItemView, QDialog, QComboBox, QDoubleSpinBox, QSpinBox
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from image_labeler import ImageLabeler
from utils import translate_text
import config

# Gemini配置对话框
class GeminiConfigDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Gemini API配置")
        self.setMinimumWidth(500)
        self.layout = QVBoxLayout(self)
        
        # 设置对话框居中显示
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)  # 移除帮助按钮
        
        # 如果没有提供当前配置，使用默认配置
        if not current_config:
            current_config = config.DEFAULT_GEMINI_CONFIG
        
        # API密钥
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API密钥:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入Google AI Studio API密钥")
        if 'api_key' in current_config:
            self.api_key_input.setText(current_config['api_key'])
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        self.layout.addLayout(api_key_layout)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(config.GEMINI_MODELS)
        if 'model' in current_config:
            index = self.model_combo.findText(current_config['model'])
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        self.layout.addLayout(model_layout)
        
        # 温度设置
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度:")
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(current_config.get('temperature', 0.8))
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_spin)
        self.layout.addLayout(temp_layout)
        
        # 最大输出长度
        max_tokens_layout = QHBoxLayout()
        max_tokens_label = QLabel("最大输出长度:")
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 8192)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(current_config.get('max_output_tokens', 2048))
        max_tokens_layout.addWidget(max_tokens_label)
        max_tokens_layout.addWidget(self.max_tokens_spin)
        self.layout.addLayout(max_tokens_layout)
        
        # 提示词
        prompt_layout = QVBoxLayout()
        prompt_label = QLabel("提示词:")
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("输入提示词，指导模型生成描述")
        if 'prompt' in current_config:
            self.prompt_input.setText(current_config['prompt'])
        else:
            self.prompt_input.setText(config.DEFAULT_GEMINI_CONFIG['prompt'])
        self.prompt_input.setMinimumHeight(100)
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.prompt_input)
        self.layout.addLayout(prompt_layout)
        
        # 按钮
        buttons_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        self.layout.addLayout(buttons_layout)
    
    def get_config(self):
        """获取当前配置"""
        return {
            'api_key': self.api_key_input.text().strip(),
            'model': self.model_combo.currentText(),
            'temperature': self.temp_spin.value(),
            'max_output_tokens': self.max_tokens_spin.value(),
            'prompt': self.prompt_input.toPlainText().strip()
        }

# 创建翻译线程类
class TranslateThread(QThread):
    # 定义信号
    translation_done = pyqtSignal(int, str)
    translation_failed = pyqtSignal(int, str)
    all_translations_completed = pyqtSignal(int)  # 新增信号，参数为成功翻译的数量
    
    def __init__(self, text, row):
        super().__init__()
        self.text = text
        self.row = row
        self.batch_mode = False
        self.translations = []  # [(row, text), ...]
        
    def set_batch_mode(self, translations):
        """设置批量翻译模式"""
        self.batch_mode = True
        self.translations = translations
        
    def run(self):
        if self.batch_mode:
            # 批量翻译模式
            translated_count = 0
            for row, text in self.translations:
                try:
                    translated = translate_text(text)
                    if translated.startswith("[翻译失败]"):
                        self.translation_failed.emit(row, translated)
                    else:
                        self.translation_done.emit(row, translated)
                        translated_count += 1
                except Exception as e:
                    self.translation_failed.emit(row, f"[翻译失败] {str(e)}")
                
                # 短暂延时，避免API请求过于频繁
                QThread.msleep(100)
            
            # 所有翻译完成后发送信号
            self.all_translations_completed.emit(translated_count)
        else:
            # 单个翻译模式
            try:
                translated = translate_text(self.text)
                if translated.startswith("[翻译失败]"):
                    self.translation_failed.emit(self.row, translated)
                else:
                    self.translation_done.emit(self.row, translated)
            except Exception as e:
                self.translation_failed.emit(self.row, f"[翻译失败] {str(e)}")

class TextEditDelegate(QStyledItemDelegate):
    """自定义委托，用于实现多行文本编辑"""
    
    def createEditor(self, parent, option, index):
        editor = QTextEdit(parent)
        editor.setMinimumHeight(200)  # 确保编辑器足够高
        return editor
        
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value:
            editor.setText(value)
            
    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.EditRole)
        
    def updateEditorGeometry(self, editor, option, index):
        # 确保编辑器覆盖整个单元格
        editor.setGeometry(option.rect)

class ImageDelegate(QStyledItemDelegate):
    """自定义委托，用于在表格中显示自适应大小的图片"""
    
    def __init__(self):
        super().__init__()
        
    def paint(self, painter, option, index):
        if index.data(Qt.UserRole):
            image_path = index.data(Qt.UserRole)
            # 根据单元格大小调整图片大小
            cell_width = option.rect.width() - 10  # 留一些边距
            cell_height = option.rect.height() - 10
            
            image = QPixmap(image_path)
            # 保持宽高比例缩放
            scaled_image = image.scaled(
                cell_width, 
                cell_height,
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # 绘制图片，在单元格中居中
            x = option.rect.x() + (option.rect.width() - scaled_image.width()) / 2
            y = option.rect.y() + (option.rect.height() - scaled_image.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled_image)
            
            # 在图片下方绘制文件名
            file_name = os.path.basename(image_path)
            painter.drawText(
                option.rect.x() + 5,
                option.rect.y() + option.rect.height() - 5,
                file_name
            )
        else:
            QStyledItemDelegate.paint(self, painter, option, index)
    
    def sizeHint(self, option, index):
        # 设置单元格的默认大小，行高会自动调整
        return QSize(200, 200)  # 增加默认高度

# 创建打标线程类
class LabelingThread(QThread):
    # 定义信号
    labeling_done = pyqtSignal(int, dict)
    labeling_failed = pyqtSignal(int, str)
    all_labeling_completed = pyqtSignal(int)  # 新增信号，参数为成功打标的数量
    
    def __init__(self, image_path, row, labeler):
        super().__init__()
        self.image_path = image_path
        self.row = row
        self.labeler = labeler
        self.batch_mode = False
        self.image_paths = []  # [(row, image_path), ...]
        
    def set_batch_mode(self, image_paths):
        """设置批量打标模式"""
        self.batch_mode = True
        self.image_paths = image_paths
        
    def run(self):
        if self.batch_mode:
            # 批量打标模式
            labeled_count = 0
            for row, image_path in self.image_paths:
                try:
                    # 调用打标器进行打标
                    result = self.labeler.label_image(image_path)
                    
                    # 检查返回结果
                    if isinstance(result, dict) and 'description' in result:
                        self.labeling_done.emit(row, result)
                        labeled_count += 1
                    else:
                        self.labeling_failed.emit(row, f"打标失败: 返回结果格式不正确")
                except Exception as e:
                    self.labeling_failed.emit(row, f"打标失败: {str(e)}")
                
                # 暂停1秒，避免API请求过于频繁
                QThread.sleep(1)  # 增加到1秒
            
            # 所有打标完成后发送信号
            self.all_labeling_completed.emit(labeled_count)
        else:
            # 单个打标模式
            try:
                # 调用打标器进行打标
                result = self.labeler.label_image(self.image_path)
                
                # 检查返回结果
                if isinstance(result, dict) and 'description' in result:
                    self.labeling_done.emit(self.row, result)
                else:
                    self.labeling_failed.emit(self.row, f"打标失败: 返回结果格式不正确")
            except Exception as e:
                self.labeling_failed.emit(self.row, f"打标失败: {str(e)}")

class ImageLabelAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.current_path = ""
        self.image_files = []
        self.content_modified = False  # 标记内容是否被修改
        
        # 加载保存的目录列表和配置
        self.load_data()
        
        # 全屏显示窗口
        self.showMaximized()
        
        # 检查是否配置了Gemini，如果没有则弹出配置页面
        self.check_gemini_config()
        
    def check_gemini_config(self):
        """检查是否配置了Gemini，如果没有则弹出配置页面"""
        # 获取当前Gemini配置
        gemini_config = config.get_gemini_config()
        
        # 如果没有设置API密钥
        if not gemini_config.get('api_key'):
            result = QMessageBox.question(
                self, 
                "Gemini配置", 
                "您尚未配置Gemini API，无法使用图像打标功能。\n\n是否现在配置？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                self.show_gemini_config()
            else:
                QMessageBox.information(self, "功能受限", "由于未配置Gemini API，打标功能将不可用。\n\n您随时可以通过左侧的'配置Gemini API'按钮进行配置。")
        
        # 为labeler应用配置
        self.apply_gemini_config(gemini_config)
    
    def center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        screen_geometry = QDesktopWidget().availableGeometry()
        window_geometry = self.geometry()
        
        # 计算居中位置
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        
        # 移动窗口到居中位置
        self.move(x, y)
        
    def init_ui(self):
        self.setWindowTitle("图像打标助手")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)
        
        # 左侧区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 添加目录的输入框和按钮
        input_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("输入目录路径或点击选择按钮")
        self.browse_btn = QPushButton("选择")
        self.browse_btn.clicked.connect(self.browse_directory)
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_directory)
        
        input_layout.addWidget(self.dir_input)
        input_layout.addWidget(self.browse_btn)
        input_layout.addWidget(self.add_btn)
        
        left_layout.addLayout(input_layout)
        
        # 目录列表
        self.dir_list = QListWidget()
        self.dir_list.clicked.connect(self.on_directory_clicked)
        left_layout.addWidget(self.dir_list)
        
        # 删除目录按钮
        self.remove_btn = QPushButton("删除选中目录")
        self.remove_btn.clicked.connect(self.remove_directory)
        left_layout.addWidget(self.remove_btn)
        
        # 添加Gemini配置按钮
        self.gemini_config_btn = QPushButton("配置Gemini API")
        self.gemini_config_btn.clicked.connect(self.show_gemini_config)
        left_layout.addWidget(self.gemini_config_btn)
        
        main_splitter.addWidget(left_widget)
        
        # 右侧区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 触发词输入框
        trigger_label = QLabel("触发词:")
        self.trigger_input = QLineEdit()
        self.trigger_input.setPlaceholderText("输入触发词，将添加到标签前面")
        
        # 按钮
        self.label_all_btn = QPushButton("一键打标")
        self.label_all_btn.clicked.connect(self.label_all_images)
        self.save_all_btn = QPushButton("一键保存")
        self.save_all_btn.clicked.connect(self.save_all_labels)
        self.translate_all_btn = QPushButton("一键翻译")
        self.translate_all_btn.clicked.connect(self.translate_all_labels)
        
        button_layout.addWidget(trigger_label)
        button_layout.addWidget(self.trigger_input)
        button_layout.addWidget(self.label_all_btn)
        button_layout.addWidget(self.translate_all_btn)
        button_layout.addWidget(self.save_all_btn)
        button_layout.addStretch()
        
        right_layout.addLayout(button_layout)
        
        # 图像表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["图像", "英文打标", "中文翻译", "翻译", "打标"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        # 设置可编辑模式
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        
        # 连接表格修改信号
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        # 设置委托
        self.image_delegate = ImageDelegate()
        self.table.setItemDelegateForColumn(0, self.image_delegate)
        
        # 设置文本编辑委托，仅英文打标使用多行编辑
        self.text_delegate = TextEditDelegate()
        self.table.setItemDelegateForColumn(1, self.text_delegate)  # 英文打标使用多行编辑
        
        # 设置默认行高
        self.table.verticalHeader().setDefaultSectionSize(200)
        
        # 设置行高可以手动调整
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        right_layout.addWidget(self.table)
        
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([300, 900])
        
        self.labeler = ImageLabeler()
    
    def show_gemini_config(self):
        """显示Gemini配置对话框"""
        # 获取当前配置
        current_config = config.get_gemini_config()
        
        # 创建并显示配置对话框
        config_dialog = GeminiConfigDialog(self, current_config)
        
        # 将对话框移动到屏幕中央
        screen_rect = QDesktopWidget().availableGeometry()
        dialog_rect = config_dialog.frameGeometry()
        dialog_rect.moveCenter(screen_rect.center())
        config_dialog.move(dialog_rect.topLeft())
        
        if config_dialog.exec_() == QDialog.Accepted:
            # 获取新配置
            new_config = config_dialog.get_config()
            
            # 应用配置
            self.apply_gemini_config(new_config)
            
            # 保存配置
            config.save_gemini_config(new_config)
            
            # 显示确认消息
            if new_config['api_key']:
                QMessageBox.information(self, "配置成功", "Gemini API配置已保存")
            else:
                QMessageBox.warning(self, "API密钥为空", "请注意，没有设置Gemini API密钥，图像打标功能将无法使用")
    
    def apply_gemini_config(self, config_data):
        """应用Gemini配置"""
        # 配置打标器
        self.labeler.configure_gemini(
            api_key=config_data['api_key'],
            model_name=config_data['model'],
            temperature=config_data['temperature'],
            max_output_tokens=config_data['max_output_tokens'],
            prompt=config_data['prompt']
        )
    
    def load_data(self):
        """从配置模块加载保存的目录列表和配置"""
        # 获取目录列表
        directories = config.get_directories()
        
        # 检查目录是否存在
        valid_directories = [d for d in directories if os.path.isdir(d)]
        
        # 添加有效的目录到列表
        for directory in valid_directories:
            self.dir_list.addItem(directory)
        
        # 如果有目录被过滤掉了，更新配置
        if len(valid_directories) < len(directories):
            config.update_directories(valid_directories)
        
        # 加载并应用Gemini配置
        gemini_config = config.get_gemini_config()
        self.apply_gemini_config(gemini_config)
    
    def save_data(self):
        """保存目录列表到配置模块"""
        # 获取目录列表
        directories = []
        for i in range(self.dir_list.count()):
            directories.append(self.dir_list.item(i).text())
        
        # 更新目录列表
        config.update_directories(directories)
    
    def browse_directory(self):
        """打开文件对话框选择目录，并直接添加到列表"""
        directory = QFileDialog.getExistingDirectory(self, "选择图像目录")
        if directory:
            # 直接设置到输入框
            self.dir_input.setText(directory)
            
            # 检查目录是否有效
            if not os.path.isdir(directory):
                QMessageBox.warning(self, "警告", "所选路径不是有效的目录")
                return
                
            # 检查是否已存在于列表中
            for i in range(self.dir_list.count()):
                if self.dir_list.item(i).text() == directory:
                    # 如果已存在，则直接选中该项
                    self.dir_list.setCurrentRow(i)
                    QMessageBox.information(self, "提示", "该目录已在列表中")
                    return
                    
            # 直接添加到列表
            self.dir_list.addItem(directory)
            # 选中新添加的项
            self.dir_list.setCurrentRow(self.dir_list.count() - 1)
            
            # 保存目录列表
            self.save_data()
            
            # 自动加载所选目录的图像
            self.on_directory_clicked(None)
    
    def add_directory(self):
        """添加目录到列表"""
        directory = self.dir_input.text().strip()
        if not directory:
            QMessageBox.warning(self, "警告", "请输入或选择目录路径")
            return
            
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "所选路径不是有效的目录")
            return
            
        # 检查是否已存在
        for i in range(self.dir_list.count()):
            if self.dir_list.item(i).text() == directory:
                QMessageBox.information(self, "提示", "该目录已在列表中")
                return
                
        # 添加到列表
        self.dir_list.addItem(directory)
        self.dir_input.clear()
        
        # 保存目录列表到配置模块
        self.save_data()
    
    def remove_directory(self):
        """从列表中删除选中的目录"""
        current_item = self.dir_list.currentItem()
        if current_item:
            self.dir_list.takeItem(self.dir_list.row(current_item))
            # 如果删除的是当前正在显示的目录，则清空图像表格
            if current_item.text() == self.current_path:
                self.current_path = ""
                self.image_files = []
                self.update_table()
                
            # 保存目录列表到配置模块
            self.save_data()
        
    def on_directory_clicked(self, index):
        """当点击目录列表项时，加载该目录中的图像"""
        selected_dir = self.dir_list.currentItem().text()
        
        # 如果内容已被修改，显示确认对话框，即使点击的是当前目录
        if self.content_modified:
            action_text = "重新加载" if self.current_path == selected_dir else "切换"
            result = QMessageBox.question(
                self, 
                f"确认{action_text}", 
                f"当前表格内容已修改但未保存，{action_text}目录将丢失这些修改。\n\n是否继续{action_text}？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # 默认选择"否"
            )
            
            if result != QMessageBox.Yes:
                # 用户选择不切换/不重载，不执行任何操作
                return
        
        # 切换目录并重置修改状态
        self.current_path = selected_dir
        self.content_modified = False
        self.load_images_from_directory(selected_dir)
        
    def load_images_from_directory(self, path):
        """加载指定目录中的所有图像文件"""
        self.image_files = []
        
        # 获取目录中的所有图像文件
        try:
            for file in os.listdir(path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    self.image_files.append(os.path.join(path, file))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取目录内容: {str(e)}")
                
        # 更新表格
        self.update_table()
        
    def update_table(self):
        """更新图像表格内容"""
        # 临时断开信号连接，避免触发修改标记
        try:
            self.table.itemChanged.disconnect(self.on_table_item_changed)
        except Exception:
            # 可能尚未连接信号
            pass
            
        self.table.setRowCount(len(self.image_files))
        
        for i, image_path in enumerate(self.image_files):
            # 图像缩略图
            try:
                item = QTableWidgetItem()
                item.setData(Qt.UserRole, image_path)  # 存储图像路径，委托会使用这个路径
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 图像项不可编辑
                self.table.setItem(i, 0, item)
                
                # 检查同名的txt文件
                txt_file_path = os.path.splitext(image_path)[0] + ".txt"
                en_label = ""
                
                if os.path.exists(txt_file_path):
                    try:
                        with open(txt_file_path, 'r', encoding='utf-8') as f:
                            # 读取整个文件内容作为英文标签
                            en_label = f.read().strip()
                    except Exception as e:
                        print(f"读取标签文件出错: {e}")
                
                # 设置英文标签
                if en_label:
                    item = QTableWidgetItem(en_label)
                    item.setFlags(item.flags() | Qt.ItemIsEditable)  # 确保可以编辑
                    self.table.setItem(i, 1, item)
                else:
                    # 创建空的可编辑项
                    item = QTableWidgetItem("")
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    self.table.setItem(i, 1, item)
                
                # 创建中文翻译项（不可编辑）
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
                self.table.setItem(i, 2, item)
                
                # 创建翻译按钮
                translate_button = QPushButton("翻译")
                translate_button.clicked.connect(lambda _, row=i: self.translate_label(row))
                self.table.setCellWidget(i, 3, translate_button)
                
                # 创建标记按钮
                label_button = QPushButton("打标")
                label_button.clicked.connect(lambda _, row=i: self.label_image(row))
                self.table.setCellWidget(i, 4, label_button)
            except Exception as e:
                print(f"加载图像出错: {e}")
            
        # 恢复信号连接
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        # 重置修改状态
        self.content_modified = False
    
    def label_image(self, row):
        """标注单个图像"""
            
        image_path = self.image_files[row]
        
        # 禁用打标按钮并更改文本
        label_button = self.table.cellWidget(row, 4)
        label_button.setText("正在打标...")
        label_button.setEnabled(False)
        
        # 创建并启动打标线程
        self.labeling_thread = LabelingThread(image_path, row, self.labeler)
        self.labeling_thread.labeling_done.connect(self.on_labeling_done)
        self.labeling_thread.labeling_failed.connect(self.on_labeling_failed)
        self.labeling_thread.start()
    
    def on_labeling_done(self, row, result):
        """打标成功的回调函数"""
        # 处理返回结果
        description = result.get('description', '')
        zh_translation = result.get('zh', '')
        
        # 获取触发词
        trigger_word = self.trigger_input.text().strip()
        
        # 如果有触发词，添加到描述前面
        if trigger_word:
            description = f"{trigger_word}, {description}"
        
        # 临时断开信号连接，避免触发修改标记
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        
        # 更新英文描述（只使用description部分）
        item = QTableWidgetItem(description)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.table.setItem(row, 1, item)
        
        # 更新中文翻译，如果有的话
        if zh_translation:
            # Gemini已提供中文翻译
            item = QTableWidgetItem(zh_translation)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row, 2, item)
        else:
            # 需要调用翻译API
            translated = translate_text(description)
            item = QTableWidgetItem(translated)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row, 2, item)
        
        # 恢复信号连接
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        # 将打标也视为内容修改，以便在切换目录时得到保存提示
        self.content_modified = True
        
        # 恢复打标按钮
        label_button = self.table.cellWidget(row, 4)
        label_button.setText("打标")
        label_button.setEnabled(True)
    
    def on_labeling_failed(self, row, error_msg):
        """打标失败的回调函数"""
        # 恢复打标按钮
        label_button = self.table.cellWidget(row, 4)
        if label_button:
            label_button.setText("打标")
            label_button.setEnabled(True)
    
    def translate_label(self, row):
        """翻译单个标签"""
        en_label_item = self.table.item(row, 1)
        
        if not en_label_item or not en_label_item.text():
            QMessageBox.warning(self, "警告", "请先添加英文标签")
            return
        
        # 获取英文标签
        en_label = en_label_item.text()
        
        # 禁用翻译按钮并更改文本
        translate_button = self.table.cellWidget(row, 3)
        translate_button.setText("正在翻译...")
        translate_button.setEnabled(False)
        
        # 创建并启动翻译线程
        self.translate_thread = TranslateThread(en_label, row)
        self.translate_thread.translation_done.connect(self.on_translation_done)
        self.translate_thread.translation_failed.connect(self.on_translation_failed)
        self.translate_thread.start()
    
    def on_translation_done(self, row, translated):
        """翻译成功的回调函数"""
        # 临时断开信号连接，避免触发修改标记
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        
        # 更新中文翻译
        item = QTableWidgetItem(translated)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
        self.table.setItem(row, 2, item)
        
        # 恢复信号连接
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        # 将翻译也视为内容修改，以便在切换目录时得到保存提示
        self.content_modified = True
        
        # 恢复翻译按钮
        translate_button = self.table.cellWidget(row, 3)
        translate_button.setText("翻译")
        translate_button.setEnabled(True)
    
    def on_translation_failed(self, row, error_msg):
        """翻译失败的回调函数"""
        # 更新中文翻译为错误信息
        item = QTableWidgetItem(error_msg)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
        self.table.setItem(row, 2, item)
        
        # 恢复翻译按钮
        translate_button = self.table.cellWidget(row, 3)
        translate_button.setText("翻译")
        translate_button.setEnabled(True)
        
    def translate_all_labels(self):
        """翻译所有标签"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可翻译的标签")
            return
            
        # 禁用一键翻译按钮
        self.translate_all_btn.setText("正在翻译...")
        self.translate_all_btn.setEnabled(False)
        
        # 收集需要翻译的文本和对应的行号
        translations_to_do = []
        for row in range(len(self.image_files)):
            en_label_item = self.table.item(row, 1)
            
            if en_label_item and en_label_item.text():
                # 如果有英文标签但没有中文翻译或中文翻译为空
                zh_label_item = self.table.item(row, 2)
                if not zh_label_item or not zh_label_item.text():
                    # 收集需要翻译的英文文本和行号
                    translations_to_do.append((row, en_label_item.text()))
                    
                    # 禁用该行的翻译按钮
                    translate_button = self.table.cellWidget(row, 3)
                    translate_button.setText("正在翻译...")
                    translate_button.setEnabled(False)
        
        if not translations_to_do:
            self.translate_all_btn.setText("一键翻译")
            self.translate_all_btn.setEnabled(True)
            QMessageBox.information(self, "提示", "没有需要翻译的标签")
            return
        
        # 创建批量翻译线程
        self.batch_translate_thread = TranslateThread("", 0)
        self.batch_translate_thread.set_batch_mode(translations_to_do)
        
        # 连接信号
        self.batch_translate_thread.translation_done.connect(self.on_translation_done)
        self.batch_translate_thread.translation_failed.connect(self.on_translation_failed)
        self.batch_translate_thread.all_translations_completed.connect(self.on_all_translations_completed)
        
        # 启动线程
        self.batch_translate_thread.start()
    
    def on_all_translations_completed(self, translated_count):
        """所有翻译完成后的回调"""
        # 恢复一键翻译按钮
        self.translate_all_btn.setText("一键翻译")
        self.translate_all_btn.setEnabled(True)
        
        # 显示完成消息
        QMessageBox.information(self, "翻译完成", f"已成功翻译 {translated_count} 个标签")
        
    def label_all_images(self):
        """标注所有图像"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可标注的图像")
            return
            
        # 显示确认对话框
        result = QMessageBox.question(
            self, 
            "确认操作", 
            "此操作将对当前目录的所有图像重新打标，已有的标签将被覆盖。是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # 禁用按钮避免重复点击
        self.label_all_btn.setEnabled(False)
        self.label_all_btn.setText("正在打标...")
        
        # 收集所有图像和对应的行号
        images_to_label = []
        for row in range(len(self.image_files)):
            # 所有图像都进行标注，无论是否已经打过标
            images_to_label.append((row, self.image_files[row]))
            
            # 禁用该行的打标按钮
            label_button = self.table.cellWidget(row, 4)
            if label_button:
                label_button.setText("正在打标...")
                label_button.setEnabled(False)
        
        if not images_to_label:
            self.label_all_btn.setText("一键打标")
            self.label_all_btn.setEnabled(True)
            QMessageBox.information(self, "提示", "没有图像可以打标")
            return
        
        # 创建批量打标线程
        self.batch_labeling_thread = LabelingThread("", 0, self.labeler)
        self.batch_labeling_thread.set_batch_mode(images_to_label)
        
        # 连接信号
        self.batch_labeling_thread.labeling_done.connect(self.on_labeling_done)
        self.batch_labeling_thread.labeling_failed.connect(self.on_labeling_failed)
        self.batch_labeling_thread.all_labeling_completed.connect(self.on_all_labeling_completed)
        
        # 启动线程
        self.batch_labeling_thread.start()
    
    def on_all_labeling_completed(self, labeled_count):
        """所有打标完成后的回调"""
        # 恢复一键打标按钮
        self.label_all_btn.setText("一键打标")
        self.label_all_btn.setEnabled(True)
        
        # 修复可能有些按钮没有恢复的问题
        for row in range(len(self.image_files)):
            label_button = self.table.cellWidget(row, 4)
            if label_button and not label_button.isEnabled():
                label_button.setText("打标")
                label_button.setEnabled(True)
        
        # 显示完成消息
        QMessageBox.information(self, "打标完成", f"已成功打标 {labeled_count} 个图像")
    
    def save_all_labels(self):
        """保存所有标签到文本文件"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可保存的标签")
            return
            
        saved_count = 0
        for row in range(len(self.image_files)):
            image_path = self.image_files[row]
            filename = os.path.splitext(os.path.basename(image_path))[0] + ".txt"
            save_path = os.path.join(os.path.dirname(image_path), filename)
            
            # 获取标签内容
            en_label_item = self.table.item(row, 1)
            
            if en_label_item and en_label_item.text():
                en_label = en_label_item.text()
                
                try:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(en_label)
                    saved_count += 1
                except Exception as e:
                    print(f"保存标签时出错: {e}")
        
        # 重置修改状态
        self.content_modified = False
        
        QMessageBox.information(self, "保存成功", f"已成功保存 {saved_count} 个标签文件")

    def on_table_item_changed(self, item):
        """表格内容变化时的回调函数"""
        # 标记内容已被修改
        self.content_modified = True

def load_stylesheet():
    """加载QSS样式表"""
    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.qss')
    
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 应用样式表
    app.setStyleSheet(load_stylesheet())
    
    window = ImageLabelAssistant()
    window.show()
    sys.exit(app.exec_()) 