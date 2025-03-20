from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Ellipse, Line
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
import cv2
import numpy as np
import re
import os


class CapturePopup(Popup):
    def __init__(self, capture_callback, **kwargs):
        super(CapturePopup, self).__init__(**kwargs)
        self.title = "Register"
        self.size_hint = (0.8, 0.4)  # 弹窗大小

        # 布局
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        # 姓名输入框
        self.name_input = TextInput(hint_text="Input Name", multiline=False, size_hint_y=0.3)
        layout.add_widget(self.name_input)

        # 身份证号输入框
        self.id_input = TextInput(hint_text="Input ID number", multiline=False, size_hint_y=0.3)
        self.id_input.bind(text=self.validate_id)  # 绑定输入事件
        layout.add_widget(self.id_input)

        # 确认按钮
        self.confirm_button = Button(
            text="Submit",
            size_hint=(1, 0.4),
            disabled=True,
            background_color=[0.5, 0.5, 0.5, 1]  # 默认灰色
        )
        self.confirm_button.bind(on_press=lambda instance: capture_callback(self.name_input.text, self.id_input.text))
        layout.add_widget(self.confirm_button)

        self.content = layout

    def validate_id(self, instance, value):
        """验证身份证号格式"""
        # 身份证号正则表达式（简单验证，18位数字）
        id_pattern = r"^\d{17}[\dXx]$"
        if re.match(id_pattern, value):
            self.set_button_color(True)  # 格式正确，启用按钮并设置为绿色
        else:
            self.set_button_color(False)  # 格式错误，禁用按钮并设置为灰色

    def set_button_color(self, is_valid):
        """设置确认按钮的颜色和状态"""
        if is_valid:
            self.confirm_button.disabled = False
            self.confirm_button.background_color = [0, 1, 0, 1]  # 绿色
        else:
            self.confirm_button.disabled = True
            self.confirm_button.background_color = [0.5, 0.5, 0.5, 1]  # 灰色


class CameraLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(CameraLayout, self).__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 0  # 移除内边距
        self.spacing = 0  # 移除控件间距

        # 顶部布局（放置提示标签和采集按钮）
        self.top_layout = BoxLayout(size_hint=(1, 0.1), orientation="horizontal", padding=10, spacing=10)

        # 提示标签
        self.hint_label = Label(text="Please place your palm inside the circle.", size_hint=(0.8, 1), font_size=24)
        self.top_layout.add_widget(self.hint_label)

        # 采集按钮
        self.capture_button = Button(text="Capture", size_hint=(0.2, 1))
        self.capture_button.bind(on_press=self.capture_image)
        self.top_layout.add_widget(self.capture_button)

        self.add_widget(self.top_layout)

        # 视频显示区域（铺满窗口）
        self.camera_image = Image(size_hint=(1, 0.85))
        self.add_widget(self.camera_image)

        # 初始化摄像头
        self.capture = cv2.VideoCapture(0)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # 定时更新视频流
        Clock.schedule_interval(self.update_frame, 1.0 / 30.0)

        # 采集状态
        self.is_capturing = False  # 是否正在采集
        self.hand = "left"  # 当前采集的手（left/right）
        self.capture_count = 0  # 当前采集的照片数量
        self.name = ""  # 用户姓名
        self.id_number = ""  # 用户身份证号

        # 进度条
        self.progress = 0  # 当前进度（0-10）
        with self.canvas:
            Color(0, 1, 0, 1)  # 绿色
            self.progress_circle = Line(circle=(0, 0, 0), width=2)

    def update_frame(self, dt):
        """更新摄像头帧"""
        ret, frame = self.capture.read()
        if ret:
            # 在帧上绘制圆形提示框
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            radius = min(w, h) // 3
            cv2.circle(frame, center, radius, (255, 255, 255), 2)

            # 将 OpenCV 图像转换为 Kivy 纹理
            buf = cv2.flip(frame, 0).tobytes()
            texture = Texture.create(size=(w, h), colorfmt="bgr")
            texture.blit_buffer(buf, colorfmt="bgr", bufferfmt="ubyte")
            self.camera_image.texture = texture

            # 更新进度条
            self.update_progress_circle()

    def update_progress_circle(self):
        """更新进度条"""
        if self.is_capturing:
            # 如果正在采集，绘制或更新进度圈
            center_x = self.camera_image.center_x
            center_y = self.camera_image.center_y
            radius = min(self.camera_image.width, self.camera_image.height) // 3

            # 如果进度圈不存在，则创建
            if self.progress_circle is None:
                with self.canvas:
                    Color(0, 1, 0, 1)  # 绿色
                    self.progress_circle = Line(circle=(center_x, center_y, radius, 0, self.progress * 36), width=2) # 每个照片增加36度
            else:
                # 如果进度圈已存在，则更新
                self.progress_circle.circle = (center_x, center_y, radius, 0, self.progress * 36)
        else:
            # 如果不在采集状态，移除进度圈
            if self.progress_circle is not None:
                self.canvas.remove(self.progress_circle)
                self.progress_circle = None

    def show_capture_popup(self, instance):
        """显示采集弹窗"""
        self.popup = CapturePopup(capture_callback=self.start_capture)
        self.popup.open()

    def start_capture(self, name, id_number):
        """开始采集"""
        self.name = name
        self.id_number = id_number
        self.is_capturing = True
        self.hand = "left"
        self.capture_count = 0
        self.progress = 0
        self.hint_label.text = f"Capturing {self.hand} hand (0/10)"
        self.popup.dismiss()  # 关闭弹窗

    def capture_image(self, instance):
        """采集图像"""
        if not self.is_capturing:
            # 如果未在采集状态，显示弹窗
            self.show_capture_popup(instance)
        else:
            # 如果正在采集状态，执行采集逻辑
            ret, frame = self.capture.read()
            if ret:
                # 生成文件名
                filename = f"{self.name}_{self.id_number}_{self.hand}_{self.capture_count + 1}.png"
                cv2.imwrite(filename, frame)
                self.capture_count += 1
                self.progress += 1

                # 更新提示信息
                self.hint_label.text = f"Capturing {self.hand} hand ({self.capture_count}/10)"

                # 检查是否完成当前手的采集
                if self.capture_count >= 10:
                    self.progress = 0
                    if self.hand == "left":
                        self.hand = "right"
                        self.capture_count = 0
                        self.hint_label.text = f"Switch to {self.hand} hand (0/10)"
                    else:
                        self.hint_label.text = "Capture complete! Returning to initial page."
                        self.is_capturing = False
                        Clock.schedule_once(self.reset_capture, 2)  # 2 秒后重置

    # def capture_image(self, instance):
    #     """采集图像"""
    #     if self.is_capturing:
    #         ret, frame = self.capture.read()
    #         if ret:
    #             # 生成文件名
    #             filename = f"{self.name}_{self.id_number}_{self.hand}_{self.capture_count + 1}.png"
    #             cv2.imwrite(filename, frame)
    #             self.capture_count += 1
    #             self.progress += 1

    #             # 更新提示信息
    #             self.hint_label.text = f"Capturing {self.hand} hand ({self.capture_count}/10)"

    #             # 检查是否完成当前手的采集
    #             if self.capture_count >= 10:
    #                 if self.hand == "left":
    #                     self.hand = "right"
    #                     self.capture_count = 0
    #                     self.hint_label.text = f"Switch to {self.hand} hand (0/10)"
    #                 else:
    #                     self.is_capturing = False
    #                     self.hint_label.text = "Capture complete! Returning to initial page."
    #                     Clock.schedule_once(self.reset_capture, 2)  # 2 秒后重置

    def reset_capture(self, dt):
        """重置采集状态"""
        self.is_capturing = False
        self.hand = "left"
        self.capture_count = 0
        self.progress = 0
        self.hint_label.text = "Please place your palm inside the circle."


class MainApp(App):
    def build(self):
        # 设置窗口大小
        Window.size = (800, 600)
        return CameraLayout()

    def on_stop(self):
        # 释放摄像头资源
        self.root.capture.release()


if __name__ == "__main__":
    MainApp().run()