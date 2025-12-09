from PyQt5.QtCore import QTimer, QObject, Qt, QRect, QEvent
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QPainter, QColor


class DeleteAnimation(QObject):

    def __init__(self, button, duration_ms=800):
        super().__init__(button)
        self.button = button
        self.duration_ms = duration_ms
        self.progress = 0.0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.is_animating = False
        self.original_style = ""

    def start(self):
        if not self.is_animating:
            self.is_animating = True
            self.progress = 0.0
            self.original_style = self.button.styleSheet()
            update_interval = 16
            self.animation_timer.start(update_interval)
            self._update_animation()

    def stop(self):
        if self.is_animating:
            self.is_animating = False
            self.animation_timer.stop()
            self.progress = 0.0
            self.button.setStyleSheet(self.original_style)
            self.button.update()

    def draw_progress_bar(self, painter):
        if self.progress <= 0 or not self.is_animating:
            return
        width = self.button.width()
        height = self.button.height()
        bar_height = 3
        bar_y = height - bar_height
        bg_rect = QRect(0, bar_y, width, bar_height)
        painter.fillRect(bg_rect, QColor(100, 100, 100, 100))
        progress_width = width * self.progress
        if self.progress >= 1.0:
            progress_width = width
        progress_rect = QRect(0, bar_y, int(progress_width), bar_height)
        painter.fillRect(progress_rect, QColor(220, 50, 50, 255))

    def _update_animation(self):
        if not self.is_animating:
            return
        update_interval = 16
        progress_step = update_interval / self.duration_ms
        new_progress = self.progress + progress_step
        if new_progress >= 1.0:
            self.progress = 1.0
            self.button.update()
            self.animation_timer.stop()
            self.is_animating = False
            QTimer.singleShot(100, self._hide_progress)
        else:
            self.progress = new_progress
            self.button.update()

    def _hide_progress(self):
        self.progress = 0.0
        self.button.update()
