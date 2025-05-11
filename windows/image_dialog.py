from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

class ImageDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("原图预览")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setMinimumSize(300, 200)

        # 加载原图并自适应窗口显示全部内容
        self.pixmap = QPixmap(image_path)
        self.update_pixmap()
        # 根据图片宽高比例设置窗口初始大小，最大不超过1200x900
        if not self.pixmap.isNull():
            max_w, max_h = 1200, 900
            w, h = self.pixmap.width(), self.pixmap.height()
            scale = min(max_w / w, max_h / h, 1.0)
            self.resize(int(w * scale) + 40, int(h * scale) + 40)

    def resizeEvent(self, event):
        # 窗口大小变化时，图片自适应缩放，保证完整显示
        self.update_pixmap()
        super().resizeEvent(event)

    def update_pixmap(self):
        if not self.pixmap.isNull():
            w = max(self.width() - 40, 100)
            h = max(self.height() - 40, 100)
            scaled = self.pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.label.setPixmap(scaled)