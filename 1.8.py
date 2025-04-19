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
from kivy.graphics import RoundedRectangle
from kivy.uix.screenmanager import ScreenManager, Screen
import cv2
import numpy as np
import re
import os
import pyttsx3


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.camera_layout = CameraLayout()
        self.camera_layout.settings_button.bind(on_press=self.switch_to_settings)
        self.add_widget(self.camera_layout)
        self.recognition_pending = False  # 添加识别待处理标志
    
    def on_enter(self):
        """当屏幕进入时触发"""
        if self.recognition_pending:
            self.recognition_pending = False
            Clock.schedule_once(lambda dt: self.camera_layout._perform_recognition(), 0.1)

    def switch_to_settings(self, instance):
        self.manager.current = 'settings'


class SettingsScreen(Screen):
    """
    设置屏幕 - 只显示操作按钮
    """
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        
        # 背景颜色
        with self.canvas.before:
            Color(0.2, 0.2, 0.2, 1)  # 深灰色背景
            self.rect = Rectangle(size=self.size, pos=self.pos)
        
        self.bind(size=self._update_rect, pos=self._update_rect)
        
        # 主布局
        main_layout = FloatLayout()  # 改为FloatLayout以便精确控制位置
        
        # 标题
        title_label = Label(
            text="Palm Recognition System",
            font_size=28,
            color=(1, 1, 1, 1),
            size_hint=(0.8, 0.4),
            pos_hint={'center_x': 0.5, 'top': 0.9}
        )
        main_layout.add_widget(title_label)
        
        # 按钮布局
        button_layout = BoxLayout(
            orientation='vertical',
            size_hint=(0.6, 0.2),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            spacing=20
        )
        
        # 采集按钮
        self.capture_button = Button(
            text="Capture", 
            size_hint=(1, 0.2),
            background_color=[0.2, 0.7, 0.2, 0.9],  # 绿色
            font_size=24
        )
        button_layout.add_widget(self.capture_button)
        
        # 识别按钮
        self.recognize_button = Button(
            text="Recognize",
            size_hint=(1, 0.2),
            background_color=[0.2, 0.2, 0.7, 0.9],  # 蓝色
            font_size=24
        )
        button_layout.add_widget(self.recognize_button)
        
        main_layout.add_widget(button_layout)
        
        # 返回按钮 - 现在放在左上角
        back_button = Button(
            text="<   Back to Camera",
            size_hint=(0.25, 0.1),
            pos_hint={'x': 0.02, 'top': 0.98},  # 左上角位置
            background_color=[0, 0, 0, 0],  # 白色
            font_size=22
        )
        back_button.bind(on_press=self.switch_to_main)
        main_layout.add_widget(back_button)
        
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        """更新背景矩形"""
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def switch_to_main(self, instance):
        """切换回主屏幕"""
        self.manager.current = 'main'


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
            text = "Submit",
            size_hint = (1, 0.4),
            disabled = True,
            background_color = [0.5, 0.5, 0.5, 1]  # 灰色表示不可用
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
    图像比对函数
    参数：
        image1: 第一张图像
        image2: 第二张图像
    返回：
        float: 相似度得分(0-1之间)
    """
    # 这里为演示返回1(100%匹配)
    return 1


class RecognitionPopup(FloatLayout):
    """
    不遮挡背景的识别结果弹窗
    """
    def __init__(self, result, name=None, **kwargs):
        super(RecognitionPopup, self).__init__(**kwargs)
        
        # 弹窗基本设置
        self.size_hint = (0.45, 0.25)
        self.pos_hint = {'center_x': 0.5, 'y': 0.00}
        Clock.schedule_once(lambda dt: self.parent.remove_widget(self) if self.parent else None, 10)  # 10秒后自动关闭

        # 绘制圆角背景
        with self.canvas.before:
            Color(0.2, 0.2, 0.2, 0.85)  # 半透明深灰色
            self.background = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[15,]
            )
        
        # 内容布局
        content = BoxLayout(
            orientation='vertical',
            size_hint=(0.9, 0.8),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            spacing=10
        )
        
        # 结果标签
        result_text = "Recognition Succeed!" if result else "Recognition Failed!"
        content.add_widget(Label(
            text=result_text,
            color=(0, 1, 0, 1) if result else (1, 0, 0, 1),
            font_size=22,
            bold=True
        ))
        
        # 姓名标签（如果识别成功）
        if result and name:
            content.add_widget(Label(
                text=f"Name: {name}",
                color=(1, 1, 1, 1),
                font_size=20
            ))
        
        # 关闭按钮
        btn = Button(
            text="Close",
            size_hint=(0.8, 0.7),
            pos_hint={'center_x': 0.5},
            background_normal='',
            background_color=(0.3, 0.3, 0.5, 1)
        )
        btn.bind(on_press=lambda x: self.parent.remove_widget(self))
        content.add_widget(btn)

        self.add_widget(content)
        self.bind(pos=self.update_bg, size=self.update_bg)
    
    def update_bg(self, *args):
        self.background.pos = self.pos
        self.background.size = self.size


class CameraLayout(FloatLayout):
    """
    主摄像头界面
    属性：
        camera_image: 显示摄像头画面
        settings_button: 设置按钮(右上角)
        hint_label: 用户提示信息
        capture: 摄像头捕获对象
        is_capturing: 采集状态标志
        hand: 当前采集的手(左/右)
        capture_count: 已采集图像计数
        engine: 语音引擎
    """
    def __init__(self, **kwargs):
        super(CameraLayout, self).__init__(**kwargs)
        
        # 视频显示区域(全屏)
        self.camera_image = Image(size_hint=(1, 1), allow_stretch=True, keep_ratio=True)
        self.add_widget(self.camera_image)
        
        # 设置按钮(右上角红色区域)
        self.settings_button = Button(
            size_hint=(None, None),
            size=(85, 75),
            pos_hint={'right': 0.98, 'top': 0.98},
            background_normal='',
            background_color=[0, 0, 0, 0],  # 白色
            text='setting',
            font_size=24
        )
        self.add_widget(self.settings_button)
        
        # 提示标签
        self.hint_label = Label(
            text="Please place your palm in the circle!",
            size_hint=(0.8, 0.1),
            pos_hint={'center_x': 0.4, 'top': 0.95},
            font_size=24,
            color=[0, 1, 1, 1],
            opacity=0  # 初始透明
        )
        self.add_widget(self.hint_label)
        
        # 初始化摄像头
        self.capture = cv2.VideoCapture(0)
        Clock.schedule_interval(self.update_frame, 1.0 / 30.0)  # 30fps更新
        
        # 采集状态
        self.is_capturing = False
        self.hand = "left"  # 初始采集左手
        self.capture_count = 0
        self.name = ""
        self.id_number = ""

        # 进度条
        self.progress = 0
        with self.canvas:
            Color(0, 1, 0, 1)
            self.progress_circle = Line(circle=(0, 0, 0), width=2)

        # 初始化语音引擎
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)  # 语速设置

    def handle_capture(self):
        """处理采集按钮点击"""
        if not self.is_capturing:
            self.show_capture_popup()  # 显示注册弹窗
        else:
            self.capture_image()  # 执行采集

    def handle_recognize(self):
        """处理识别按钮点击"""
        # 设置识别待处理标志
        main_screen = self.parent.manager.get_screen('main')
        main_screen.recognition_pending = True
        # 切换回主屏幕
        self.parent.manager.current = 'main'
        # 不再在这里执行识别，而是在主屏幕的on_enter中执行

    def _perform_recognition(self):
        """实际执行识别逻辑"""
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
            
            # 显示结果并播放语音
            if match_found:
                popup = RecognitionPopup(result=True, name=matched_name)
                self.add_widget(popup)
                # self.play_audio("Recognition Succeeded!")
                Clock.schedule_once(lambda dt: self.play_audio("Recognition Succeeded!"), 0.2)
            else:
                popup = RecognitionPopup(result=False)
                self.add_widget(popup)
                # self.play_audio("Recognition Failed!")
                Clock.schedule_once(lambda dt: self.play_audio("Recognition Failed!"), 0.2)
            
            # 重置提示标签
            self.hint_label.text = "Please place your palm in the circle!"
            Clock.schedule_once(lambda dt: setattr(self.hint_label, 'opacity', 0), 3)

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
        self.popup.dismiss()  # 关闭弹窗

    def capture_image(self):
        """采集并保存手掌图像"""
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
                self.progress = 0
                if self.hand == "left":
                    # 切换到右手
                    self.hand = "right"
                    self.capture_count = 0
                    self.hint_label.text = f"Please change to your {self.hand} hand (0/10)"
                else:
                    # 采集完成
                    self.hint_label.text = "Collection complete! Return to the initial screen."
                    self.is_capturing = False
                    Clock.schedule_once(self.reset_capture, 2)

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

    def update_frame(self, dt):
        """更新摄像头画面，只显示圆圈内内容"""
        ret, frame = self.capture.read()
        if ret:
            h, w = frame.shape[:2]
            
            # 创建一个黑色蒙版
            mask = np.zeros((h, w), dtype=np.uint8)
            # 在创建蒙版后添加高斯模糊
            mask = cv2.GaussianBlur(mask, (15, 15), 0)
            center = (w // 2, h // 2)
            radius = min(w, h) // 3  # 半径为图像短边的1/3
            # 在蒙版上绘制白色圆圈
            cv2.circle(mask, center, radius, 255, -1)  # -1表示填充
            # 应用蒙版：只保留圆圈内的图像
            masked_frame = cv2.bitwise_and(frame, frame, mask=mask)
            # 添加白色圆圈边框
            cv2.circle(masked_frame, center, radius, (255, 255, 255), 2)

            # 转换为纹理显示
            buf = cv2.flip(masked_frame, 0).tobytes()
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


class MainApp(App):

    def build(self):
        """初始化主窗口"""
        Window.size = (800, 600)
        # 创建屏幕管理器
        sm = ScreenManager()
        # 添加主屏幕
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        # 添加设置屏幕
        settings_screen = SettingsScreen(name='settings')
        # 将按钮回调绑定到主屏幕的摄像头布局
        settings_screen.capture_button.bind(on_press=lambda x: main_screen.camera_layout.handle_capture())
        settings_screen.recognize_button.bind(on_press=lambda x: main_screen.camera_layout.handle_recognize())
        sm.add_widget(settings_screen)
        return sm

    def on_stop(self):
        """应用关闭时释放摄像头"""
        # 获取主屏幕并释放摄像头
        main_screen = self.root.get_screen('main')
        if hasattr(main_screen.camera_layout, 'capture') and main_screen.camera_layout.capture.isOpened():
            main_screen.camera_layout.capture.release()


if __name__ == "__main__":
    MainApp().run()