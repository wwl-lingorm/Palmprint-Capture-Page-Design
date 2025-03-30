"""
手掌识别系统主程序
功能：
- 实时摄像头显示和手掌定位引导
- 用户注册和身份证号验证
- 手掌图像采集和存储
- 手掌图像识别比对
- 视觉和语音反馈
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Rectangle, Color, Ellipse, Line
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
import cv2
import numpy as np
import re
import os
import pyttsx3


class CapturePopup(Popup):
    """
    采集弹窗 - 用于用户注册
    
    属性：
        name_input: 姓名输入框
        id_input: 身份证号输入框(带验证)
        confirm_button: 提交按钮(仅当ID有效时可用)
    """
    def __init__(self, capture_callback, **kwargs):
        super(CapturePopup, self).__init__(**kwargs)
        self.title = "Register"
        self.size_hint = (0.8, 0.4)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)
        
        # 姓名输入框
        self.name_input = TextInput(hint_text="Please Input your Name", multiline=False, size_hint_y=0.3)
        layout.add_widget(self.name_input)
        
        # 身份证输入框(带验证)
        self.id_input = TextInput(hint_text="Please Input your ID", multiline=False, size_hint_y=0.3)
        self.id_input.bind(text=self.validate_id)  # 绑定验证函数
        layout.add_widget(self.id_input)
        
        # 提交按钮(初始不可用)
        self.confirm_button = Button(
            text="Submit",
            size_hint=(1, 0.4),
            disabled=True,
            background_color=[0.5, 0.5, 0.5, 1]  # 灰色表示不可用
        )
        # 绑定回调函数
        self.confirm_button.bind(on_press=lambda instance: capture_callback(self.name_input.text, self.id_input.text))
        layout.add_widget(self.confirm_button)
        
        self.content = layout

    def validate_id(self, instance, value):
        """验证身份证号格式(17位数字+1位数字/X)"""
        id_pattern = r"^\d{17}[\dXx]$"
        if re.match(id_pattern, value):
            self.set_button_color(True)  # 有效ID
        else:
            self.set_button_color(False)  # 无效ID

    def set_button_color(self, is_valid):
        """根据验证结果更新按钮状态"""
        if is_valid:
            self.confirm_button.disabled = False
            self.confirm_button.background_color = [0, 1, 0, 1]  # 绿色表示可用
        else:
            self.confirm_button.disabled = True
            self.confirm_button.background_color = [0.5, 0.5, 0.5, 1]  # 灰色表示不可用


def compare_images(image1, image2):
    """
    图像比对函数(使用OpenCV)
    
    参数：
        image1: 第一张图像
        image2: 第二张图像
        
    返回：
        float: 相似度得分(0-1之间)
    """
    # 这里为演示返回1(100%匹配)
    return 1


class RecognitionPopup(Popup):
    """
    识别结果弹窗
    
    属性：
        result_label: 显示成功/失败信息
        name_label: 显示识别到的姓名(如果成功)
    """
    def __init__(self, result, name=None, **kwargs):
        super(RecognitionPopup, self).__init__(**kwargs)
        self.title = "Recognition result"
        self.size_hint = (0.6, 0.4)
        
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)
        
        # 结果消息
        self.result_label = Label(
            text="Recognition Succeeded!" if result else "Recognition Failed!",
            color=[0, 1, 0, 1] if result else [1, 0, 0, 1],  # 成功绿色/失败红色
            font_size=24
        )
        layout.add_widget(self.result_label)
        
        # 如果识别成功显示姓名
        if result and name:
            self.name_label = Label(
                text=f"Name: {name}",
                color=[1, 1, 1, 1],
                font_size=20
            )
            layout.add_widget(self.name_label)
        
        # 关闭按钮
        self.close_button = Button(
            text="Close",
            size_hint=(1, 0.6)
        )
        self.close_button.bind(on_press=self.dismiss)
        layout.add_widget(self.close_button)
        
        self.content = layout


class CameraLayout(FloatLayout):
    """
    主摄像头界面
    
    属性：
        camera_image: 显示摄像头画面
        button_container: 操作按钮容器
        hint_label: 用户提示信息
        capture: 摄像头捕获对象
        is_capturing: 采集状态标志
        hand: 当前采集的手(左/右)
        capture_count: 已采集图像计数
        engine: 语音引擎
        auto_capture_event: 自动采集定时器
        switch_hand_event: 切换手定时器
    """
    def __init__(self, **kwargs):
        super(CameraLayout, self).__init__(**kwargs)
        
        # 视频显示区域(全屏)
        self.camera_image = Image(size_hint=(1, 1), allow_stretch=True, keep_ratio=True)
        self.camera_image.bind(on_touch_down=self.on_image_touch)
        self.add_widget(self.camera_image)
        
        # 触发区域指示(右上角5%区域)
        with self.canvas:
            Color(1, 0, 0, 0.3)  # 半透明红色
            self.trigger_zone = Rectangle(
                pos=(self.width*0.95, self.height*0.95),
                size=(self.width*0.05, self.height*0.05))
        
        # 按钮容器(初始隐藏)
        self.button_container = FloatLayout(
            size_hint=(None, None),
            size=(150, 100),  # 更紧凑的尺寸
            pos_hint={'right': 0.95, 'top': 0.95},
            opacity=0
        )
        self.add_widget(self.button_container)
        
        # 采集按钮
        self.capture_button = Button(
            text="Capture", 
            size_hint=(1, 0.5),
            pos_hint={'right': 1, 'top': 1.1},
            background_color=[0.2, 0.7, 0.2, 0.9]  # 绿色
        )
        self.capture_button.bind(on_press=self.handle_capture)  # 绑定处理函数
        self.button_container.add_widget(self.capture_button)
        
        # 识别按钮
        self.recognize_button = Button(
            text="Recognize",
            size_hint=(1, 0.5),
            pos_hint={'right': 1, 'top': 0.4},
            background_color=[0.2, 0.2, 0.7, 0.9]  # 蓝色
        )
        self.recognize_button.bind(on_press=self.handle_recognize)  # 绑定处理函数
        self.button_container.add_widget(self.recognize_button)

        # 提示标签
        self.hint_label = Label(
            text="Please place your palm in the circle!",
            size_hint=(0.8, 0.1),
            pos_hint={'center_x': 0.4, 'top': 0.95},
            font_size=24,
            color=[1, 1, 1, 1],
            opacity=0  # 初始透明
        )
        self.add_widget(self.hint_label)
        
        # 初始化摄像头
        self.capture = cv2.VideoCapture(0)
        Clock.schedule_interval(self.update_frame, 1.0 / 30.0)  # 30fps更新
        
        # 采集状态
        self.is_capturing = False
        self.is_recognizing = False  # 新增识别状态标志
        self.hand = "left"  # 初始采集左手
        self.capture_count = 0
        self.name = ""
        self.id_number = ""
        self.progress = 0  # 采集进度
        
        # 自动采集相关定时器
        self.auto_capture_event = None  # 自动采集定时器
        self.switch_hand_event = None  # 切换手定时器
        
        # 进度条
        with self.canvas:
            Color(0, 1, 0, 1)
            self.progress_circle = Line(circle=(0, 0, 0), width=2)

        # 初始化语音引擎
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)  # 语速设置

    def handle_capture(self, instance):
        """处理采集按钮点击"""
        if not self.is_capturing and not self.is_recognizing:
            self.show_capture_popup()  # 显示注册弹窗

    def handle_recognize(self, instance):
        """处理识别按钮点击"""
        if not self.is_capturing and not self.is_recognizing:
            self.is_recognizing = True
            self.hint_label.text = "Recognizing..."
            self.hint_label.opacity = 1
            self.recognize_image()

    def show_capture_popup(self):
        """显示注册弹窗"""
        self.popup = CapturePopup(capture_callback=self.start_capture)
        self.popup.open()

    def start_capture(self, name, id_number):
        """
        开始采集流程
        
        参数：
            name: 用户姓名
            id_number: 已验证的身份证号
        """
        self.name = name
        self.id_number = id_number
        self.is_capturing = True
        self.hand = "left"  # 从左手开始
        self.capture_count = 0
        self.progress = 0
        self.hint_label.text = f"Collecting the {self.hand} hand (0/10)"
        self.hint_label.opacity = 1  # 显示提示
        self.button_container.opacity = 1  # 保持按钮可见
        self.popup.dismiss()  # 关闭弹窗
        
        # 启动自动采集
        self.start_auto_capture()

    def start_auto_capture(self):
        """
        启动自动采集定时器
        每2秒自动采集一张图像
        """
        # 取消之前的定时器(如果有)
        if self.auto_capture_event:
            self.auto_capture_event.cancel()
        if self.switch_hand_event:
            self.switch_hand_event.cancel()
        
        # 每2秒自动采集一次
        self.auto_capture_event = Clock.schedule_interval(self.capture_image, 2)

    def capture_image(self, dt=None):
        """自动采集并保存手掌图像"""
        if not self.is_capturing:
            return
            
        ret, frame = self.capture.read()
        if ret:
            # 创建存储目录(如果不存在)
            if not os.path.exists("local_images"):
                os.makedirs("local_images")
                
            # 保存图像(格式: 姓名_ID_左右手_序号.png)
            filename = f"local_images/{self.name}_{self.id_number}_{self.hand}_{self.capture_count + 1}.png"
            cv2.imwrite(filename, frame)
            self.capture_count += 1
            self.progress += 1
            self.hint_label.text = f"Collecting the {self.hand} hand ({self.capture_count}/10)"
            
            # 检查是否完成当前手的采集
            if self.capture_count >= 10:
                # 取消当前自动采集
                if self.auto_capture_event:
                    self.auto_capture_event.cancel()
                
                self.progress = 0
                if self.hand == "left":
                    # 切换到右手，暂停5秒
                    self.hand = "right"
                    self.capture_count = 0
                    self.hint_label.text = f"Please change to your {self.hand} hand (pause 5 seconds)"
                    
                    # 5秒后重新开始采集
                    self.switch_hand_event = Clock.schedule_once(
                        lambda dt: self.start_auto_capture(), 5)
                else:
                    # 采集完成
                    self.hint_label.text = "Collection complete! Return to the initial screen."
                    self.is_capturing = False
                    Clock.schedule_once(self.reset_capture, 2)

    def recognize_image(self):
        """识别当前手掌图像"""
        ret, frame = self.capture.read()
        if ret:
            # 保存临时图像用于比对
            temp_filename = "temp_capture.png"
            cv2.imwrite(temp_filename, frame)
            current_image = cv2.imread(temp_filename, cv2.IMREAD_GRAYSCALE)
            
            match_found = False
            matched_name = None
            
            # 与存储的所有图像比对
            if os.path.exists("local_images"):
                for filename in os.listdir("local_images"):
                    if filename.endswith(".png"):
                        local_image = cv2.imread(os.path.join("local_images", filename), cv2.IMREAD_GRAYSCALE)
                        similarity = compare_images(current_image, local_image)
                        if similarity > 0.5:  # 相似度阈值
                            match_found = True
                            matched_name = filename.split("_")[0]  # 提取姓名
                            break
            
            # 显示结果
            if match_found:
                self.hint_label.text = "Recognition Succeeded!"
                self.play_audio("Recognition Succeeded!")
                RecognitionPopup(result=True, name=matched_name).open()
            else:
                self.hint_label.text = "Recognition Failed!"
                self.play_audio("Recognition Failed!")
                RecognitionPopup(result=False).open()
            
            # 识别完成后重置状态
            self.is_recognizing = False
            self.button_container.opacity = 0
            Clock.schedule_once(lambda dt: setattr(self.hint_label, 'opacity', 0), 2)

    def play_audio(self, text):
        """播放语音反馈"""
        self.engine.say(text)
        self.engine.runAndWait()

    def reset_capture(self, dt):
        """重置采集状态"""
        self.is_capturing = False
        self.hand = "left"
        self.capture_count = 0
        self.hint_label.text = "Please place your palm in the circle!"
        self.hint_label.opacity = 0
        
        # 取消所有定时器
        if self.auto_capture_event:
            self.auto_capture_event.cancel()
        if self.switch_hand_event:
            self.switch_hand_event.cancel()

    def on_image_touch(self, instance, touch):
        """处理图像区域触摸事件"""
        # 检查是否点击了触发区域(右上角5%)
        if not self.is_capturing and not self.is_recognizing:
            if touch.x > self.width * 0.95 and touch.y > self.height * 0.95:
                self.show_buttons()

    def show_buttons(self):
        """显示操作按钮(3秒后自动隐藏)"""
        self.button_container.opacity = 1
        self.hint_label.opacity = 1
        if not self.is_capturing and not self.is_recognizing:
            Clock.schedule_once(lambda dt: self.hide_buttons(), 3)

    def hide_buttons(self):
        """隐藏操作按钮"""
        if not self.is_capturing and not self.is_recognizing:
            self.button_container.opacity = 0
            self.hint_label.opacity = 0

    def update_frame(self, dt):
        """更新摄像头画面"""
        ret, frame = self.capture.read()
        if ret:
            # 添加引导圆圈
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            radius = min(w, h) // 3  # 半径为图像短边的1/3
            cv2.circle(frame, center, radius, (255, 255, 255), 2)  # 白色圆圈
            
            # 转换为纹理显示
            buf = cv2.flip(frame, 0).tobytes()
            texture = Texture.create(size=(w, h), colorfmt="bgr")
            texture.blit_buffer(buf, colorfmt="bgr", bufferfmt="ubyte")
            self.camera_image.texture = texture
            
            # 更新进度条
            if self.is_capturing:
                center_x = self.camera_image.center_x
                center_y = self.camera_image.center_y
                radius = min(self.camera_image.width, self.camera_image.height) // 3
                
                if self.progress_circle is None:
                    with self.canvas:
                        Color(0, 1, 0, 1)  # 绿色
                        self.progress_circle = Line(circle=(center_x, center_y, radius, 0, self.progress * 36), width=2)
                else:
                    # 更新进度圈角度
                    self.progress_circle.circle = (center_x, center_y, radius, 0, self.progress * 36)
            else:
                # 如果不在采集状态，移除进度圈
                if self.progress_circle is not None:
                    self.canvas.remove(self.progress_circle)
                    self.progress_circle = None

    def on_size(self, *args):
        """处理窗口大小变化"""
        self.trigger_zone.pos = (self.width*0.95, self.height*0.95)
        self.trigger_zone.size = (self.width*0.05, self.height*0.05)


class MainApp(App):
    """
    主应用类
    
    处理窗口配置和清理
    """
    def build(self):
        """初始化主窗口"""
        Window.size = (800, 600)
        return CameraLayout()

    def on_stop(self):
        """应用关闭时释放摄像头和取消定时器"""
        self.root.capture.release()
        # 取消所有定时器
        if hasattr(self.root, 'auto_capture_event') and self.root.auto_capture_event:
            self.root.auto_capture_event.cancel()
        if hasattr(self.root, 'switch_hand_event') and self.root.switch_hand_event:
            self.root.switch_hand_event.cancel()


if __name__ == "__main__":
    MainApp().run()