from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
import cv2
import numpy as np
import re


class CapturePopup(Popup):
    def __init__(self, capture_callback, **kwargs):
        super(CapturePopup, self).__init__(**kwargs)
        self.title = "Register"
        self.size_hint = (0.8, 0.3)

        # 布局
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # 姓名输入框
        self.name_input = TextInput(hint_text="Input Name", multiline=False)
        layout.add_widget(self.name_input)

        # 身份证号输入框
        self.id_input = TextInput(hint_text="Input ID number", multiline=False)
        self.id_input.bind(text=self.validate_id)  # 绑定输入事件
        layout.add_widget(self.id_input)

        # 确认按钮
        self.confirm_button = Button(text="submit", size_hint=(1, 0.8), disabled=True, background_color=[0.5,0.5,0.5,1])
        self.confirm_button.bind(on_press=lambda instance: capture_callback(self.name_input.text, self.id_input.text))
        layout.add_widget(self.confirm_button)

        self.content = layout

    def validate_id(self, instance, value):
        """验证身份证号格式"""
        # 身份证号正则表达式（简单验证，18位数字）
        id_pattern = r"^\d{17}[\dXx]$"
        if re.match(id_pattern, value):
            self.confirm_button.disabled = False  # 格式正确，启用确认按钮
        else:
            self.confirm_button.disabled = True  # 格式错误，禁用确认按钮
    def set_button_color(self, is_valid):
        if is_valid:
            self.confirm_button.disabled = False
            self.confirm_button.background_color = [0,1,0,1]
        else:
            self.confirm_button.disabled = True
            self.confirm_button.background_color = [0.5,0.5,0.5,1]

class CameraLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(CameraLayout, self).__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 10
        self.spacing = 10

        # 视频显示区域
        self.camera_image = Image(size_hint=(1, 0.85))
        self.add_widget(self.camera_image)

        # 提示标签
        self.hint_label = Label(text="Please place your palm inside the circle.", size_hint=(1, 0.075), font_size=24)
        self.add_widget(self.hint_label)

        # 采集按钮
        self.capture_button = Button(text="Capture", size_hint=(1, 0.075))
        self.capture_button.bind(on_press=self.show_capture_popup)
        self.add_widget(self.capture_button)

        # 初始化摄像头
        self.capture = cv2.VideoCapture(0)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # 定时更新视频流
        Clock.schedule_interval(self.update_frame, 1.0 / 30.0)

    def update_frame(self, dt):
        """更新摄像头帧"""
        ret, frame = self.capture.read()
        if ret:
            # 在帧上绘制圆形提示框
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            radius = min(w, h) // 3
            cv2.circle(frame, center, radius, (0, 255, 0), 2)

            # 将 OpenCV 图像转换为 Kivy 纹理
            buf = cv2.flip(frame, 0).tobytes()
            texture = Texture.create(size=(w, h), colorfmt="bgr")
            texture.blit_buffer(buf, colorfmt="bgr", bufferfmt="ubyte")
            self.camera_image.texture = texture

    def show_capture_popup(self, instance):
        """显示采集弹窗"""
        self.popup = CapturePopup(capture_callback=self.save_image)
        self.popup.open()

    def save_image(self, name, id_number):
        """保存图像"""
        ret, frame = self.capture.read()
        if ret:
            # 生成文件名
            filename = f"{name}_{id_number}.png"
            cv2.imwrite(filename, frame)
            self.hint_label.text = f"saved as {filename}"
            print(self.hint_label.text)
            self.popup.dismiss()  # 关闭弹窗


class MainApp(App):
    def build(self):
        # Window.fullscreen = True
        Window.size = (800, 600)
        return CameraLayout()
    def on_stop(self):
        # 释放摄像头资源
        self.root.capture.release()


if __name__ == "__main__":
    MainApp().run()