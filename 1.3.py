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
import pyttsx3


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
        # 简单验证身份证格式（18位数字）
        id_pattern = r"^\d{17}[\dXx]$"
        if re.match(id_pattern, value):
            self.set_button_color(True)  # 格式正确，启用按钮并设置为绿色
        else:
            self.set_button_color(False)  # 格式错误，禁用按钮并设置为灰色

    # 设置确认按钮的状态和颜色
    def set_button_color(self, is_valid):
        if is_valid:
            self.confirm_button.disabled = False
            self.confirm_button.background_color = [0, 1, 0, 1]  # 绿色
        else:
            self.confirm_button.disabled = True
            self.confirm_button.background_color = [0.5, 0.5, 0.5, 1]  # 灰色


# 简答的图像比对（假设）
def compare_images(image1, image2):
    # 使用 SIFT 特征检测器
    sift = cv2.SIFT_create()
    # 检测关键点和描述符
    keypoints1, descriptors1 = sift.detectAndCompute(image1, None)
    keypoints2, descriptors2 = sift.detectAndCompute(image2, None)
    # 使用 BFMatcher 进行匹配
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(descriptors1, descriptors2, k=2)
    # 过滤匹配点
    good_matches = [m for m, n in matches if m.distance < 0.75 * n.distance]
    # 计算匹配度
    similarity = len(good_matches) / max(len(keypoints1), len(keypoints2))
    return similarity


# 识别弹窗
class RecognitionPopup(Popup):
    def __init__(self, result, name=None, **kwargs):
        super(RecognitionPopup, self).__init__(**kwargs)
        self.title = "Recognition Result"
        self.size_hint = (0.6, 0.4)  # 弹窗大小

        # 布局
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        # 结果显示标签
        self.result_label = Label(
            text="Recognition successful!" if result else "Recognition failed!",
            color=[0, 1, 0, 1] if result else [1, 0, 0, 1],  # 绿色或红色
            font_size=24
        )
        layout.add_widget(self.result_label)

        # 照片姓名标签（仅识别成功时显示）
        if result and name:
            self.name_label = Label(
                text=f"Name: {name}",
                color=[1, 1, 1, 1],  # 白色
                font_size=20
            )
            layout.add_widget(self.name_label)

        # 关闭按钮
        self.close_button = Button(
            text="Close",
            size_hint=(1, 0.4)
        )
        self.close_button.bind(on_press=self.dismiss)  # 绑定关闭事件
        layout.add_widget(self.close_button)

        self.content = layout


class CameraLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(CameraLayout, self).__init__(**kwargs)
        self.orientation = "vertical"

        # 顶部布局（放置提示标签和按钮）
        self.top_layout = BoxLayout(size_hint=(1, 0.1), orientation="horizontal", padding=10, spacing=10)
        
        # 提示标签
        self.hint_label = Label(text="Please place your palm inside the circle.", size_hint=(0.6, 1), font_size=24)

        self.top_layout.add_widget(self.hint_label)
        # 采集按钮
        self.capture_button = Button(text="Capture", size_hint=(0.2, 1))
        self.capture_button.bind(on_press=self.capture_image)
        self.top_layout.add_widget(self.capture_button)

        # 识别按钮
        self.recognize_button = Button(text="Recognize", size_hint=(0.2, 1))
        self.recognize_button.bind(on_press=self.recognize_image)
        self.top_layout.add_widget(self.recognize_button)
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
        self.progress = 0  # 当前进度[0-10]
        with self.canvas:
            Color(0, 1, 0, 1)
            self.progress_circle = Line(circle=(0, 0, 0), width=2)

        # 初始化语音引擎
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)  # 设置语速

    def update_frame(self, dt):
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
        if self.is_capturing:
            # 如果正在采集，绘制或更新进度圈
            center_x = self.camera_image.center_x
            center_y = self.camera_image.center_y
            radius = min(self.camera_image.width, self.camera_image.height) // 3
            # 如果进度圈不存在，则创建
            if self.progress_circle is None:
                with self.canvas:
                    Color(0, 1, 0, 1)  # 绿色
                    self.progress_circle = Line(circle=(center_x, center_y, radius, 0, self.progress * 36), width=2)
            else:
                # 如果进度圈已存在，则更新
                self.progress_circle.circle = (center_x, center_y, radius, 0, self.progress * 36)
        else:
            # 如果不在采集状态，移除进度圈
            if self.progress_circle is not None:
                self.canvas.remove(self.progress_circle)
                self.progress_circle = None

    def show_capture_popup(self, instance):
        self.popup = CapturePopup(capture_callback=self.start_capture)
        self.popup.open()

    def start_capture(self, name, id_number):
        self.name = name
        self.id_number = id_number
        self.is_capturing = True
        self.hand = "left"
        self.capture_count = 0
        self.progress = 0
        self.hint_label.text = f"Capturing {self.hand} hand (0/10)"
        self.popup.dismiss()  # 关闭弹窗

    def capture_image(self, instance):
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
                        Clock.schedule_once(self.reset_capture, 2)  # 2秒后重置

    # 图像识别
    def recognize_image(self, instance):
        # 将按钮背景颜色设置为绿色
        instance.background_color = [0, 1, 0, 1]  # RGBA，绿色
        # 执行识别逻辑
        ret, frame = self.capture.read()
        if ret:
            # 保存当前帧为临时文件
            temp_filename = "temp_capture.png"
            cv2.imwrite(temp_filename, frame)
            # 读取临时文件
            current_image = cv2.imread(temp_filename, cv2.IMREAD_GRAYSCALE)
            # 遍历本地图像进行比对
            match_found = False
            matched_name = None
            for filename in os.listdir("local_images"):  # 假设本地图像存储在 local_images 文件夹中
                if filename.endswith(".png"):
                    local_image = cv2.imread(os.path.join("local_images", filename), cv2.IMREAD_GRAYSCALE)
                    similarity = compare_images(current_image, local_image)
                    if similarity > 0.5:  # 相似度阈值
                        match_found = True
                        matched_name = filename.split("_")[0]  # 假设文件名格式为 "name_id_hand_count.png"
                        break
            # 显示识别结果
            if match_found:
                self.hint_label.text = "Recognition successful!"
                self.play_audio("Recognition successful!")  # 播放语音提示
                # 弹出识别成功的弹窗
                RecognitionPopup(result=True, name=matched_name).open()
            else:
                self.hint_label.text = "Recognition failed!"
                self.play_audio("Recognition failed!")  # 播放语音提示
                # 弹出识别失败的弹窗
                RecognitionPopup(result=False).open()
        # 恢复按钮的默认颜色
        instance.background_color = [1, 1, 1, 1]  # RGBA，白色

    # 播放语音提示
    def play_audio(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def reset_capture(self, dt):
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