import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QListWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLineEdit, QHeaderView, QFileDialog, QMessageBox,
    QLabel, QStyledItemDelegate, QDesktopWidget, QTextEdit, QAbstractItemView, QComboBox, QDoubleSpinBox, QSpinBox,
    QTabWidget, QRadioButton, QButtonGroup, QGroupBox, QFormLayout, QDialog
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from image_labeler import ImageLabeler, LabelerType
from utils import translate_text
from windows.model_config_dialog import ModelConfigDialog
from windows.image_dialog import ImageDialog
import config

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
        # 仅在英文打标列被编辑时设置内容修改
        # 递归查找父级窗口，直到找到 ImageLabelAssistant 实例
        widget = model.parent()
        while widget is not None:
            if widget.metaObject().className() == 'ImageLabelAssistant':
                widget.content_modified = True
                break
            widget = widget.parent()
            
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
        
class ImageDelegate(QStyledItemDelegate):
    """自定义委托，用于在表格中显示自适应大小的图片"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent  # 允许访问主窗口方法

    def paint(self, painter, option, index):
        if index.data(Qt.UserRole):
            image_path = index.data(Qt.UserRole)
            # 先从缓存获取原始缩略图（100x100），再根据单元格实际大小缩放显示
            if self.parent_widget and hasattr(self.parent_widget, 'get_thumbnail'):
                base_thumbnail = self.parent_widget.get_thumbnail(image_path)
            else:
                base_thumbnail = QPixmap(image_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 跟随单元格大小等比例缩放
            cell_width = option.rect.width() - 10  # 保持原有边距
            cell_height = option.rect.height() - 10
            scaled_image = base_thumbnail.scaled(
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
    
    def __init__(self, image_path, row, labeler, current_directory=None):
        super().__init__()
        self.image_path = image_path
        self.row = row
        
        # 确保复制labeler的配置，而不是直接引用
        self.labeler = labeler
        
        # 添加当前目录路径
        self.current_directory = current_directory
        
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
                    # 调用打标器进行打标，传入当前目录参数
                    result = self.labeler.label_image(image_path, self.current_directory)
                    
                    # 检查返回结果
                    if isinstance(result, dict) and 'description' in result:
                        self.labeling_done.emit(row, result)
                        labeled_count += 1
                    else:
                        error_msg = f"打标失败: 返回结果格式不正确"
                        self.labeling_failed.emit(row, error_msg)
                except Exception as e:
                    error_msg = f"打标失败: {str(e)}"
                    self.labeling_failed.emit(row, error_msg)
                
                # 暂停1秒，避免API请求过于频繁
                QThread.sleep(1)  # 增加到1秒
            
            # 所有打标完成后发送信号
            self.all_labeling_completed.emit(labeled_count)
        else:
            # 单个打标模式
            try:
                # 调用打标器进行打标，传入当前目录参数
                result = self.labeler.label_image(self.image_path, self.current_directory)
                
                # 检查返回结果
                if isinstance(result, dict) and 'description' in result:
                    self.labeling_done.emit(self.row, result)
                else:
                    error_msg = f"打标失败: 返回结果格式不正确"
                    self.labeling_failed.emit(self.row, error_msg)
            except Exception as e:
                error_msg = f"打标失败: {str(e)}"
                self.labeling_failed.emit(self.row, error_msg)

class ImageLabelAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thumbnail_cache = {}  # 缩略图缓存
        self.init_ui()
        self.current_path = ""
        self.image_files = []
        self.content_modified = False  # 标记内容是否被修改
        
        # 初始化标注器
        self.labeler = ImageLabeler()
        
        # 加载保存的目录列表和配置
        self.load_data()
        
        # 全屏显示窗口
        self.showMaximized()
            
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
        
        # 添加目录的输入框和按钮（应放在最顶部）
        input_layout = QHBoxLayout()
        # 改为提示Label，不可编辑
        self.dir_input = QLabel("点击‘选择’按钮添加数据集目录")
        self.dir_input.setStyleSheet("color: #888; padding-left: 4px;")
        input_layout.addWidget(self.dir_input)
        self.browse_btn = QPushButton("选择")
        self.browse_btn.clicked.connect(self.browse_directory)
        input_layout.addWidget(self.browse_btn)
        # 删除目录按钮移到这里，并设置为红色
        self.remove_btn = QPushButton("删除")
        self.remove_btn.setStyleSheet("QPushButton { color: white; background-color: red; border-radius: 4px; padding: 4px 12px; }")
        self.remove_btn.clicked.connect(self.remove_directory)
        input_layout.addWidget(self.remove_btn)
        left_layout.addLayout(input_layout)

        # 数据集列表（必须先定义）
        self.dir_list = QListWidget()
        self.dir_list.clicked.connect(self.on_directory_clicked)
        # 触发词和提示词区域合并为整体
        trigger_prompt_widget = QWidget()
        trigger_prompt_layout = QVBoxLayout(trigger_prompt_widget)
        trigger_prompt_layout.setContentsMargins(0, 0, 0, 0)
        # 触发词输入框区域
        trigger_layout = QHBoxLayout()
        trigger_label = QLabel("触发词:")
        self.trigger_input = QLineEdit()
        self.trigger_input.setPlaceholderText("自动提取或手动输入触发词")
        trigger_layout.addWidget(trigger_label)
        trigger_layout.addWidget(self.trigger_input)
        trigger_layout.setContentsMargins(0, 10, 0, 0)  # 上下各留10像素
        trigger_prompt_layout.addLayout(trigger_layout)
        # 数据集提示词配置区域
        prompt_group = QGroupBox("当前数据集提示词配置")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("输入当前数据集的提示词配置")
        self.prompt_input.setMinimumHeight(100)
        prompt_layout.addWidget(self.prompt_input)
        self.save_prompt_btn = QPushButton("保存提示词配置")
        self.save_prompt_btn.clicked.connect(self.save_directory_prompt)
        prompt_layout.addWidget(self.save_prompt_btn)
        trigger_prompt_layout.addWidget(prompt_group)
        trigger_prompt_layout.setStretch(0, 0)
        trigger_prompt_layout.setStretch(1, 1)
        # splitter分隔目录和触发词+提示词整体
        dir_trigger_splitter = QSplitter(Qt.Vertical)
        dir_trigger_splitter.addWidget(self.dir_list)
        dir_trigger_splitter.addWidget(trigger_prompt_widget)
        left_layout.addWidget(dir_trigger_splitter)

        # 设置分割条初始高度，上方60%，下方40%
        def set_splitter_sizes():
            total = dir_trigger_splitter.height()
            if total < 100:
                total = 400  # 防止窗口尚未显示时高度为0
            dir_trigger_splitter.setSizes([int(total * 0.6), int(total * 0.4)])
        QTimer.singleShot(0, set_splitter_sizes)

        # 添加Gemini配置按钮
        self.model_config_btn = QPushButton("配置模型")
        self.model_config_btn.clicked.connect(lambda: self.show_model_config(0))
        left_layout.addWidget(self.model_config_btn)
        
        main_splitter.addWidget(left_widget)
        
        # 右侧区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()

        # 创建横向布局，用于放置模型选择和标签
        model_selection_layout = QHBoxLayout()

        # 模型选择下拉菜单
        model_selection_layout.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Gemini",
            "Florence2",
            "智谱AI"
        ])
        self.model_combo.setCurrentIndex(1)  # 默认使用Florence2
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        model_selection_layout.addWidget(self.model_combo)

        button_layout.addLayout(model_selection_layout)

        # 按钮
        self.label_all_btn = QPushButton()
        selected_model = self.model_combo.currentText()
        if not selected_model:
            selected_model = "Florence2"
        self.label_all_btn.setText(f"一键打标 ({selected_model})")
        self.label_all_btn.clicked.connect(self.label_all_images)
        self.save_all_btn = QPushButton("一键保存")
        self.save_all_btn.clicked.connect(self.save_all_labels)
        self.translate_all_btn = QPushButton("一键翻译")
        self.translate_all_btn.clicked.connect(self.translate_all_labels)
        
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
        self.image_delegate = ImageDelegate(self)
        self.table.setItemDelegateForColumn(0, self.image_delegate)
        # 设置文本编辑委托，仅英文打标使用多行编辑
        self.text_delegate = TextEditDelegate()
        self.table.setItemDelegateForColumn(1, self.text_delegate)  # 英文打标使用多行编辑
        # 设置默认行高
        self.table.verticalHeader().setDefaultSectionSize(200)
        # 设置行高可以手动调整
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # 绑定双击信号
        self.table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        # 懒加载支持：滚动时动态加载可见区域的内容
        self.table.viewport().installEventFilter(self)
        right_layout.addWidget(self.table)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([300, 900])
        
    def show_model_config(self, tab_index=0):
        """显示模型配置对话框
        
        Args:
            tab_index: 默认显示的选项卡索引，0为Gemini，1为智谱AI，2为Florence2
        """

        
        # 创建并显示配置对话框
        config_dialog = ModelConfigDialog(self)
        
        # 设置默认显示的选项卡
        config_dialog.tabs.setCurrentIndex(tab_index)
        
        # 将对话框移动到屏幕中央
        # 先显示对话框，然后再调整位置，这样可以确保对话框大小已经计算出来
        config_dialog.show()
        frameGm = config_dialog.frameGeometry()
        screen = QDesktopWidget().availableGeometry().center()
        frameGm.moveCenter(screen)
        config_dialog.move(frameGm.topLeft())
        config_dialog.hide()
        
        if config_dialog.exec_() == QDialog.Accepted:
            # 获取新配置
            new_gemini_config = config_dialog.get_gemini_config()
            new_zhipu_translate_config = config_dialog.get_zhipu_translate_config()
            new_zhipu_label_config = config_dialog.get_zhipu_label_config()
            new_florence2_config = config_dialog.get_florence2_config()
            
            # 应用配置
            config.save_gemini_config(new_gemini_config)
            config.save_zhipu_translate_config(new_zhipu_translate_config)
            config.save_zhipu_label_config(new_zhipu_label_config)
            config.save_florence2_config(new_florence2_config)
            
            # 显示确认消息
            QMessageBox.information(self, "配置成功", "模型配置已保存")
    
    def load_data(self):
        """从配置模块加载保存的目录列表和配置"""
        # 获取目录列表
        directories = config.get_directories()
        
        # 检查目录是否存在
        valid_directories = [d for d in directories if os.path.isdir(d['path'])]
        
        # 添加有效的目录到列表
        for directory in valid_directories:
            self.dir_list.addItem(directory['path'])
        
        # 如果有目录被过滤掉了，更新配置
        if len(valid_directories) < len(directories):
            config.update_directories(valid_directories)
    
    def save_data(self):
        """保存目录列表到配置模块"""
        # 获取目录列表
        directories = []
        dir_prompts = config.get_directory_prompts()
        
        for i in range(self.dir_list.count()):
            path = self.dir_list.item(i).text()
            # 保留原有提示词配置，如果有的话
            prompt = dir_prompts.get(path, config.DEFAULT_PROMPT)
            directories.append({"path": path, "prompt": prompt})
        
        # 更新目录列表
        config.update_directories(directories)
    
    def browse_directory(self):
        """打开文件对话框选择目录，并直接添加到列表"""
        directory = QFileDialog.getExistingDirectory(self, "选择图像目录")
        if directory:
            # 只做提示Label，不再 setText
            # 检查目录是否有效
            if not os.path.isdir(directory):
                QMessageBox.warning(self, "警告", "所选路径不是有效的目录")
                return
            # 检查是否已存在于列表中
            for i in range(self.dir_list.count()):
                if self.dir_list.item(i).text() == directory:
                    self.dir_list.setCurrentRow(i)
                    QMessageBox.information(self, "提示", "该目录已在列表中")
                    return
            # 直接添加到列表
            self.dir_list.addItem(directory)
            self.dir_list.setCurrentRow(self.dir_list.count() - 1)
            self.save_data()
            self.on_directory_clicked(None)
    
    def remove_directory(self):
        """从列表中删除选中的目录"""
        current_item = self.dir_list.currentItem()
        if current_item:
            # 弹出确认对话框
            result = QMessageBox.question(
                self, 
                "确认删除", 
                f"确定要删除目录 '{current_item.text()}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # 默认选择"否"
            )
            
            if result != QMessageBox.Yes:
                return
                
            self.dir_list.takeItem(self.dir_list.row(current_item))
            # 如果删除的是当前正在显示的目录，则清空图像表格
            if current_item.text() == self.current_path:
                self.current_path = ""
                self.image_files = []
                self.update_table()
                
            # 保存目录列表到配置模块
            self.save_data()
        
    def load_directory_prompt(self, directory_path):
        """加载目录的提示词配置"""
        dir_prompts = config.get_directory_prompts()
        prompt = dir_prompts.get(directory_path, config.DEFAULT_PROMPT)
        self.prompt_input.setText(prompt)
    
    def save_directory_prompt(self):
        """保存当前目录的提示词配置"""
        if not self.current_path:
            QMessageBox.warning(self, "警告", "请先选择一个目录")
            return
            
        prompt = self.prompt_input.toPlainText()
        if not prompt:
            QMessageBox.warning(self, "警告", "提示词不能为空")
            return
            
        # 保存提示词
        config.set_directory_prompt(self.current_path, prompt)
        
        QMessageBox.information(self, "保存成功", "提示词配置已保存")
    
    def on_directory_clicked(self, index):
        """当点击目录列表项时，加载该目录中的图像，并自动提取触发词"""
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
                return

        # 切换目录并重置修改状态
        self.current_path = selected_dir
        self.content_modified = False

        # 加载该目录的提示词配置
        self.load_directory_prompt(selected_dir)

        # 加载目录中的图像
        self.load_images_from_directory(selected_dir)

        # 自动提取触发词
        self.auto_extract_trigger_word()

    def auto_extract_trigger_word(self):
        """自动从任意两张图像的打标文本中提取触发词"""
        labels = []
        # 收集所有非空英文打标文本
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item and item.text():
                labels.append(item.text().strip())
            if len(labels) == 2:
                break
        if len(labels) < 2:
            self.trigger_input.setText("")
            return
        # 提取第一个英文逗号前的部分
        def get_prefix(label):
            idx = label.find(",")
            return label[:idx].strip() if idx != -1 else label.strip()
        prefix1 = get_prefix(labels[0])
        prefix2 = get_prefix(labels[1])
        if prefix1 and prefix1 == prefix2:
            self.trigger_input.setText(prefix1)
        else:
            self.trigger_input.setText("")
    
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
        """更新图像表格内容（支持懒加载）"""
        try:
            self.table.itemChanged.disconnect(self.on_table_item_changed)
        except Exception:
            pass
        self.table.setRowCount(len(self.image_files))
        for i, image_path in enumerate(self.image_files):
            # 只创建空的 QTableWidgetItem，实际缩略图数据懒加载
            try:
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 0, item)
                txt_file_path = os.path.splitext(image_path)[0] + ".txt"
                en_label = ""
                if os.path.exists(txt_file_path):
                    try:
                        with open(txt_file_path, 'r', encoding='utf-8') as f:
                            en_label = f.read().strip()
                    except Exception as e:
                        print(f"读取标签文件出错: {e}")
                if en_label:
                    item = QTableWidgetItem(en_label)
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    self.table.setItem(i, 1, item)
                else:
                    item = QTableWidgetItem("")
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    self.table.setItem(i, 1, item)
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 2, item)
                translate_button = QPushButton("翻译")
                translate_button.clicked.connect(lambda _, row=i: self.translate_label(row))
                self.table.setCellWidget(i, 3, translate_button)
                label_button = QPushButton("打标")
                label_button.clicked.connect(lambda _, row=i: self.label_image(row))
                self.table.setCellWidget(i, 4, label_button)
            except Exception as e:
                print(f"加载图像出错: {e}")
        self.content_modified = False
        self.table.itemChanged.connect(self.on_table_item_changed)
        # 懒加载首次触发
        self.lazy_load_table_images()
    
    def eventFilter(self, obj, event):
        # 针对表格的懒加载优化
        if obj == self.table.viewport():
            from PyQt5.QtCore import QEvent
            if event.type() in (QEvent.Paint, QEvent.Resize, QEvent.Wheel, QEvent.Scroll):
                self.lazy_load_table_images()
        return super().eventFilter(obj, event)

    def lazy_load_table_images(self):
        # 只加载当前可见区域的图像缩略图，提升大数据集性能
        visible_rows = self.get_visible_rows()
        for row in visible_rows:
            item = self.table.item(row, 0)
            if item and not item.data(Qt.UserRole):
                # 只在未加载过缩略图时加载
                image_path = self.image_files[row]
                item.setData(Qt.UserRole, image_path)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        # 强制刷新可见区域
        self.table.viewport().update()

    def get_visible_rows(self):
        # 获取表格当前可见的行索引
        viewport = self.table.viewport()
        rect = viewport.rect()
        first = self.table.rowAt(rect.top())
        last = self.table.rowAt(rect.bottom())
        if last == -1:
            last = self.table.rowCount() - 1
        return range(max(0, first), min(self.table.rowCount(), last + 1))

    def label_image(self, row):
        """标注单个图像"""
        # 如果使用非Gemini和非智谱AI的模型，显示加载提示
        if self.model_combo.currentIndex() > 0 and self.model_combo.currentText() != "智谱AI":  # Huggingface模型
            # 获取当前选择的模型名称
            model_id = self.model_combo.currentText()
            model_short_name = model_id.split('/')[-1]
            
            # 如果是首次使用该模型，显示加载提示
            if self.labeler.hf_model is None or self.labeler.hf_model.get("model_id") != model_id:
                # 显示加载消息
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setText(f"正在加载模型 {model_short_name}，这可能需要几分钟时间...\n首次使用时需要下载模型（约2GB）")
                msg.setWindowTitle("加载模型")
                msg.show()
                QApplication.processEvents()  # 确保UI能够更新
                self.msg = msg  # 保存引用以便后续关闭
        
        image_path = self.image_files[row]
        
        # 禁用打标按钮并更改文本
        label_button = self.table.cellWidget(row, 4)
        label_button.setText("正在打标...")
        label_button.setEnabled(False)
        
        # 同时禁用翻译按钮，避免用户在打标过程中尝试翻译
        translate_button = self.table.cellWidget(row, 3)
        if translate_button:
            translate_button.setEnabled(False)
        
        # 创建并启动打标线程，传入当前目录
        self.labeling_thread = LabelingThread(image_path, row, self.labeler, self.current_path)
        self.labeling_thread.labeling_done.connect(self.on_labeling_done)
        self.labeling_thread.labeling_failed.connect(self.on_labeling_failed)
        self.labeling_thread.start()
        
        # 关闭加载提示（如果存在）
        if hasattr(self, 'msg') and self.msg.isVisible():
            self.msg.close()
    
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

        # 恢复信号连接
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        # 将打标也视为内容修改，以便在切换目录时得到保存提示
        self.content_modified = True
        
        # 恢复打标按钮
        label_button = self.table.cellWidget(row, 4)
        label_button.setText("打标")
        label_button.setEnabled(True)
        
        # 恢复翻译按钮
        translate_button = self.table.cellWidget(row, 3)
        if translate_button:
            translate_button.setText("翻译")
            translate_button.setEnabled(True)
    
    def on_labeling_failed(self, row, error_msg):
        """打标失败的回调函数"""
        # 恢复打标按钮
        label_button = self.table.cellWidget(row, 4)
        if label_button:
            label_button.setText("打标")
            label_button.setEnabled(True)
            
        # 恢复翻译按钮
        translate_button = self.table.cellWidget(row, 3)
        if translate_button:
            translate_button.setText("翻译")
            translate_button.setEnabled(True)
    
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
    
    def on_all_translations_completed(self, success_count):
        """所有翻译完成时的处理"""
        # 恢复按钮状态
        self.translate_all_btn.setText("一键翻译")
        self.translate_all_btn.setEnabled(True)
        
        # 确保所有翻译按钮都已启用
        for row in range(len(self.image_files)):
            translate_button = self.table.cellWidget(row, 3)
            if translate_button and not translate_button.isEnabled():
                translate_button.setText("翻译")
                translate_button.setEnabled(True)
        
        # 根据是否有成功翻译的标签显示不同消息
        if success_count > 0:
            QMessageBox.information(self, "翻译完成", f"成功翻译了 {success_count} 个标签")
        else:
            QMessageBox.information(self, "翻译完成", "没有标签被成功翻译")
    
    def label_all_images(self):
        """标注所有图像"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可标注的图像")
            return
            
        # 确认操作
        result = QMessageBox.question(
            self, 
            "确认操作", 
            "此操作将标注所有未标注的图像，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # 如果使用非Gemini和非智谱AI的模型，显示加载提示
        if self.model_combo.currentIndex() > 0 and self.model_combo.currentText() != "智谱AI":  # Huggingface模型
            # 获取当前选择的模型名称
            model_id = self.model_combo.currentText()
            model_short_name = model_id.split('/')[-1]
            
            # 如果是首次使用该模型，显示加载提示
            if self.labeler.hf_model is None or self.labeler.hf_model.get("model_id") != model_id:
                # 显示加载消息
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setText(f"正在加载模型 {model_short_name}，这可能需要几分钟时间...\n首次使用时需要下载模型（约2GB）")
                msg.setWindowTitle("加载模型")
                msg.show()
                QApplication.processEvents()  # 确保UI能够更新
                self.msg = msg  # 保存引用以便后续关闭
        
        # 收集需要标注的图像
        images_to_label = []
        for row in range(len(self.image_files)):
            # 获取英文标签
            en_label_item = self.table.item(row, 1)
            
            # 如果英文标签为空，则需要标注
            if not en_label_item or not en_label_item.text():
                images_to_label.append((row, self.image_files[row]))
                
                # 禁用该行的打标按钮
                label_button = self.table.cellWidget(row, 4)
                if label_button:
                    label_button.setText("正在打标...")
                    label_button.setEnabled(False)
        
        if not images_to_label:
            QMessageBox.information(self, "提示", "所有图像已标注")
            return
        
        # 禁用一键打标按钮
        self.label_all_btn.setEnabled(False)
        
        # 创建批量打标线程，传入当前目录
        self.batch_labeling_thread = LabelingThread("", 0, self.labeler, self.current_path)
        self.batch_labeling_thread.set_batch_mode(images_to_label)
        
        # 连接信号
        self.batch_labeling_thread.labeling_done.connect(self.on_labeling_done)
        self.batch_labeling_thread.labeling_failed.connect(self.on_labeling_failed)
        self.batch_labeling_thread.all_labeling_completed.connect(self.on_all_labeling_completed)
        
        # 启动线程
        self.batch_labeling_thread.start()
        
        # 关闭加载提示（如果存在）
        if hasattr(self, 'msg') and self.msg.isVisible():
            self.msg.close()
    
    def on_all_labeling_completed(self, success_count):
        """所有标注完成时的处理"""
        # 恢复按钮状态
        self.label_all_btn.setText("一键打标")
        self.label_all_btn.setEnabled(True)
        
        # 检查所有行，确保所有翻译按钮和打标按钮都已启用
        for row in range(len(self.image_files)):
            # 恢复翻译按钮
            translate_button = self.table.cellWidget(row, 3)
            if translate_button and not translate_button.isEnabled():
                translate_button.setText("翻译")
                translate_button.setEnabled(True)
                
            # 恢复打标按钮
            label_button = self.table.cellWidget(row, 4)
            if label_button and not label_button.isEnabled():
                label_button.setText("打标")
                label_button.setEnabled(True)
        
        # 根据是否有成功标注的图像显示不同消息
        if success_count > 0:
            QMessageBox.information(self, "标注完成", f"成功标注了 {success_count} 张图像")
        else:
            QMessageBox.information(self, "标注完成", "没有图像被成功标注")
    
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
        # 现在仅作占位，所有内容修改逻辑已交由 TextEditDelegate 处理
        pass

    def on_model_changed(self):
        """模型选择变化时的回调函数"""
        selected_model = self.model_combo.currentText()
        if selected_model == "Gemini":
            # 检查是否配置Gemini API
            gemini_config = config.get_gemini_config()
            if not gemini_config.get('api_key'):
                result = QMessageBox.question(
                    self,
                    "API配置",
                    "您尚未配置Gemini API，无法使用Gemini打标功能。\n\n是否现在配置？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if result == QMessageBox.Yes:
                    self.show_gemini_config(0)  # 显示Gemini选项卡
                else:
                    QMessageBox.information(self, "功能受限", "由于未配置Gemini API，打标功能将不可用。\n\n您随时可以通过左侧的'配置API'按钮进行配置。")
                    self.model_combo.setCurrentIndex(1)
                    return
            self.labeler.labeler_type = LabelerType.GEMINI
        elif selected_model == "Florence2":
            self.labeler.labeler_type = LabelerType.FLORENCE2
        elif selected_model == "智谱AI":
            # 检查是否配置智谱API
            zhipu_config = config.get_zhipu_label_config()
            if not zhipu_config.get('api_key'):
                result = QMessageBox.question(
                    self,
                    "API配置",
                    "您尚未配置智谱 API，无法使用智谱打标功能。\n\n是否现在配置？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if result == QMessageBox.Yes:
                    self.show_gemini_config(1)  # 显示智谱AI选项卡
                else:
                    QMessageBox.information(self, "功能受限", "由于未配置智谱 API，打标功能将不可用。\n\n您随时可以通过左侧的'配置API'按钮进行配置。")
                    self.model_combo.setCurrentIndex(1)
                    return
            self.labeler.labeler_type = LabelerType.ZHIPU
        # 统一设置一键打标按钮文本
        self.label_all_btn.setText(f"一键打标 ({selected_model})")
        print(f"当前选择的模型: {selected_model}")

    def get_thumbnail(self, image_path):
        # 缓存大尺寸缩略图，避免放大导致模糊
        max_thumb_size = 400
        if image_path in self.thumbnail_cache:
            return self.thumbnail_cache[image_path]
        pixmap = QPixmap(image_path)
        # 只缩小，不放大
        if pixmap.width() > max_thumb_size or pixmap.height() > max_thumb_size:
            thumbnail = pixmap.scaled(
                max_thumb_size, max_thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            thumbnail = pixmap
        self.thumbnail_cache[image_path] = thumbnail
        return thumbnail

    def on_table_cell_double_clicked(self, row, column):
        # 仅对图片列（第0列）响应
        if column == 0:
            item = self.table.item(row, 0)
            if item is not None:
                image_path = item.data(Qt.UserRole)
                if image_path:
                    dlg = ImageDialog(image_path, self)
                    dlg.exec_()

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
