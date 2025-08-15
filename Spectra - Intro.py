import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, Property, QEasingCurve
from PySide6.QtGui import QPainter, QImage, QPixmap, QGuiApplication, QFont, QColor, QFontMetrics
from PIL import ImageGrab, ImageFilter, Image

class BlurOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())
        self._s_pos = QPoint(self.width() // 2, self.height() + 100)  # Start: unten mittig
        self._pectra_pos = QPoint(self.width(), self.height() // 2)   # Start: rechts außerhalb
        self.s_visible = False
        self.pectra_visible = False
        self._s_opacity = 1.0
        self._pectra_opacity = 1.0

        # Screenshot und Blur-Stufen vorbereiten
        self.screenshot = self.get_screenshot()
        self.blur_levels = self.prepare_blur_levels(self.screenshot, max_blur=16, steps=16)
        self.current_blur_index = len(self.blur_levels) - 1  # Start: kein Blur
        self.bg = self.blur_levels[self.current_blur_index]

        # Blur smooth einblenden
        self.blur_in_timer = QTimer(self)
        self.blur_in_timer.timeout.connect(self.update_blur_in)
        self.blur_in_timer.start(40)  # ca. 40ms pro Frame

        self.blur_in_done = False

    def get_screenshot(self):
        bbox = QGuiApplication.primaryScreen().geometry().getRect()
        img = ImageGrab.grab(bbox=bbox)
        return img.convert("RGBA")

    def prepare_blur_levels(self, img, max_blur=16, steps=16):
        levels = []
        for i in range(steps, -1, -1):
            blur = max_blur * i / steps
            blurred = img.filter(ImageFilter.GaussianBlur(radius=blur))
            data = blurred.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            levels.append(QPixmap.fromImage(qimg))
        return levels

    def start_s_animation(self):
        self.s_visible = True
        self.update()
        self.anim = QPropertyAnimation(self, b"s_pos")
        self.anim.setDuration(800)
        self.anim.setStartValue(QPoint(self.width() // 2, self.height() + 100))
        self.anim.setEndValue(QPoint(self.width() // 2, self.height() // 2))
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self.update)
        self.anim.finished.connect(self.start_spectra_animation)
        self.anim.start()

    def start_spectra_animation(self):
        # Berechne Zielpositionen für S und PECTRA, damit "SPECTRA" mittig ist
        font = QFont("Arial", int(self.height() * 0.25), QFont.Bold)
        metrics = QFontMetrics(font)
        spectra_width = metrics.horizontalAdvance("SPECTRA")
        s_width = metrics.horizontalAdvance("S")
        pectra_width = metrics.horizontalAdvance("PECTRA")

        # Ziel: S nach links, sodass "SPECTRA" mittig steht
        spectra_left = (self.width() - spectra_width) // 2
        s_target_x = spectra_left + s_width // 2
        self._spectra_left = spectra_left  # merken für PECTRA

        # Kurze Pause bevor das S nach links fährt
        def animate_s_left():
            self.slide_anim = QPropertyAnimation(self, b"s_pos")
            self.slide_anim.setDuration(500)
            self.slide_anim.setStartValue(QPoint(self.width() // 2, self.height() // 2))
            self.slide_anim.setEndValue(QPoint(s_target_x, self.height() // 2))
            self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)
            self.slide_anim.valueChanged.connect(self.update)
            self.slide_anim.finished.connect(self.start_pectra_animation)
            self.slide_anim.start()

        QTimer.singleShot(250, animate_s_left)  # 250 ms Pause

    def start_pectra_animation(self):
        # PECTRA von rechts nach mittig animieren
        font = QFont("Arial", int(self.height() * 0.25), QFont.Bold)
        metrics = QFontMetrics(font)
        s_width = metrics.horizontalAdvance("S")
        pectra_width = metrics.horizontalAdvance("PECTRA")

        s_target_x = self._spectra_left + s_width // 2
        pectra_target_x = s_target_x + s_width // 2 + pectra_width // 2

        self.pectra_visible = True

        self.pectra_anim = QPropertyAnimation(self, b"pectra_pos")
        self.pectra_anim.setDuration(500)
        self.pectra_anim.setStartValue(QPoint(self.width() + pectra_width, self.height() // 2))
        self.pectra_anim.setEndValue(QPoint(pectra_target_x, self.height() // 2))
        self.pectra_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.pectra_anim.valueChanged.connect(self.update)
        self.pectra_anim.start()

    def start_unblur_animation(self):
        # S und PECTRA ausfaden
        self.s_fade_anim = QPropertyAnimation(self, b"s_opacity")
        self.s_fade_anim.setDuration(700)
        self.s_fade_anim.setStartValue(1.0)
        self.s_fade_anim.setEndValue(0.0)
        self.s_fade_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.s_fade_anim.valueChanged.connect(self.update)
        self.s_fade_anim.start()

        self.pectra_fade_anim = QPropertyAnimation(self, b"pectra_opacity")
        self.pectra_fade_anim.setDuration(700)
        self.pectra_fade_anim.setStartValue(1.0)
        self.pectra_fade_anim.setEndValue(0.0)
        self.pectra_fade_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.pectra_fade_anim.valueChanged.connect(self.update)
        self.pectra_fade_anim.start()

        # Starte das Unblur
        self.unblur_timer = QTimer(self)
        self.unblur_timer.timeout.connect(self.update_blur)
        self.unblur_timer.start(40)  # ca. 40ms pro Frame, ergibt ~0.7s für 16 Schritte

    def update_blur(self):
        if self.current_blur_index < len(self.blur_levels) - 1:
            self.current_blur_index += 1
            self.bg = self.blur_levels[self.current_blur_index]
            self.update()
        else:
            self.unblur_timer.stop()
            self.close()

    def update_blur_in(self):
        if self.current_blur_index > 0:
            self.current_blur_index -= 1
            self.bg = self.blur_levels[self.current_blur_index]
            self.update()
        else:
            self.blur_in_timer.stop()
            self.blur_in_done = True
            # Starte S-Animation und Unblur-Timer wie gehabt
            QTimer.singleShot(200, self.start_s_animation)  # S nach kurzer Pause
            QTimer.singleShot(3200, self.start_unblur_animation)  # Blur bleibt ca. 3s voll sichtbar

    # S-Position Property
    def get_s_pos(self):
        return self._s_pos

    def set_s_pos(self, pos):
        self._s_pos = pos
        self.update()

    s_pos = Property(QPoint, get_s_pos, set_s_pos)

    # S-Opacity Property
    def get_s_opacity(self):
        return self._s_opacity

    def set_s_opacity(self, value):
        self._s_opacity = value
        self.update()

    s_opacity = Property(float, get_s_opacity, set_s_opacity)

    # PECTRA-Position Property
    def get_pectra_pos(self):
        return self._pectra_pos

    def set_pectra_pos(self, pos):
        self._pectra_pos = pos
        self.update()

    pectra_pos = Property(QPoint, get_pectra_pos, set_pectra_pos)

    # PECTRA-Opacity Property
    def get_pectra_opacity(self):
        return self._pectra_opacity

    def set_pectra_opacity(self, value):
        self._pectra_opacity = value
        self.update()

    pectra_opacity = Property(float, get_pectra_opacity, set_pectra_opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bg)
        font = QFont("Arial", int(self.height() * 0.25), QFont.Bold)
        painter.setFont(font)

        # Farben für Verlauf: Dunkles Lila zu Helles Lila
        dark_purple = QColor(80, 0, 120)
        light_purple = QColor(180, 120, 255)

        # S
        if self.s_visible and self._s_opacity > 0.01:
            painter.save()
            painter.setOpacity(self._s_opacity)
            s_text = "S"
            s_rect = painter.fontMetrics().boundingRect(s_text)
            s_rect.moveCenter(self._s_pos + QPoint(4, 4))
            # Schatten
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.drawText(s_rect, Qt.AlignCenter, s_text)
            # Dunkles Lila S
            s_rect.moveCenter(self._s_pos)
            painter.setPen(dark_purple)
            painter.drawText(s_rect, Qt.AlignCenter, s_text)
            painter.restore()

        # PECTRA mit Farbverlauf von dunkel nach hell
        if self.pectra_visible and self._pectra_opacity > 0.01:
            painter.save()
            painter.setOpacity(self._pectra_opacity)
            pectra_text = "PECTRA"
            pectra_rect = painter.fontMetrics().boundingRect(pectra_text)
            pectra_rect.moveCenter(self._pectra_pos + QPoint(4, 4))
            # Schatten
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.drawText(pectra_rect, Qt.AlignCenter, pectra_text)
            # Farbverlauf für PECTRA (Buchstabe für Buchstabe)
            pectra_rect.moveCenter(self._pectra_pos)
            for i, char in enumerate(pectra_text):
                ratio = i / (len(pectra_text) - 1)
                color = QColor(
                    int(dark_purple.red()   + (light_purple.red()   - dark_purple.red())   * ratio),
                    int(dark_purple.green() + (light_purple.green() - dark_purple.green()) * ratio),
                    int(dark_purple.blue()  + (light_purple.blue()  - dark_purple.blue())  * ratio)
                )
                painter.setPen(color)
                char_rect = painter.fontMetrics().boundingRect(char)
                # Positioniere jeden Buchstaben nebeneinander
                offset_x = painter.fontMetrics().horizontalAdvance(pectra_text[:i])
                char_rect.moveCenter(self._pectra_pos + QPoint(-pectra_rect.width()//2 + offset_x + char_rect.width()//2, 0))
                painter.drawText(char_rect, Qt.AlignCenter, char)
            painter.restore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = BlurOverlay()
    overlay.show()
    sys.exit(app.exec())
