# -*- coding: utf-8 -*-

"""
.kivy/config.ini中的字体默认配置修改成中文
default_font = ['Roboto', 'data/fonts/Roboto-Regular.ttf', 'data/fonts/Roboto-Italic.ttf', 'data/fonts/Roboto-Bold.ttf', 'data/fonts/Roboto-BoldItalic.ttf']
default_font = ['宋体', 'C:\\Windows\\Fonts\\simfang.ttf']

主屏幕（空闲状态）MainScreen
分屏幕（点击设置后跳转的屏幕）SettingsScreen
CapturePopup采集弹窗——用户注册
RecognitionPopup识别弹窗——识别结果显示
CameraLayout主摄像头画面
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
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
import glob
import json
from collections import OrderedDict




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
        
        self.user_manager = UserDataManager()
        # 背景颜色
        with self.canvas.before:
            Color(0.2, 0.2, 0.2, 1)  # 深灰色背景
            self.rect = Rectangle(size=self.size, pos=self.pos)
        
        self.bind(size=self._update_rect, pos=self._update_rect)
        
        # 主布局
        main_layout = FloatLayout()  # 改为FloatLayout以便精确控制位置
        
        # 标题
        title_label = Label(
            text="掌纹识别系统",
            font_size=28,
            color=(1, 1, 1, 1),
            size_hint=(0.8, 0.4),
            pos_hint={'center_x': 0.5, 'top': 0.9}
        )
        main_layout.add_widget(title_label)
        
        # 按钮布局
        button_layout = BoxLayout(
            orientation='vertical',
            size_hint=(0.6, 0.25),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            spacing=20
        )
        
        # 采集按钮
        self.capture_button = Button(
            text="采 集", 
            size_hint=(1, 0.3),
            background_color=[0.2, 0.7, 0.2, 0.9],  # 绿色
            font_size=24
        )
        button_layout.add_widget(self.capture_button)
        
        # 修改采集按钮绑定 - 现在直接切换到主屏幕并显示采集弹窗
        self.capture_button.bind(on_press=self.start_capture_process)

        # 识别按钮
        self.recognize_button = Button(
            text="识 别",
            size_hint=(1, 0.3),
            background_color=[0.2, 0.2, 0.7, 0.9],  # 蓝色
            font_size=24
        )
        button_layout.add_widget(self.recognize_button)
        
        # 新增用户管理按钮
        self.manage_button = Button(
            text="用户管理",
            size_hint=(1, 0.3),
            background_color=[0.7, 0.2, 0.7, 0.9],  # 紫色
            font_size=24
        )
        button_layout.add_widget(self.manage_button)
        self.manage_button.bind(on_press=self.show_user_management)

        main_layout.add_widget(button_layout)

        # 返回按钮 - 现在放在左上角
        back_button = Button(
            text="<   返回",
            size_hint=(0.25, 0.1),
            pos_hint={'x': 0.02, 'top': 0.98},  # 左上角位置
            background_color=[0, 0, 0, 0],  # 白色
            font_size=22
        )
        back_button.bind(on_press=self.switch_to_main)
        main_layout.add_widget(back_button)
        
        self.add_widget(main_layout)
    
    def show_user_management(self, instance):
        """显示用户管理弹窗"""
        popup = UserManagementPopup(user_manager=self.user_manager)
        popup.open()

    def _update_rect(self, instance, value):
        """更新背景矩形"""
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def switch_to_main(self, instance):
        """切换回主屏幕"""
        self.manager.current = 'main'

    def start_capture_process(self, instance):
        """启动采集流程"""
        self.manager.current = 'main'
        main_screen = self.manager.get_screen('main')
        # 使用Clock.schedule_once确保界面切换完成后再显示弹窗
        Clock.schedule_once(lambda dt: main_screen.camera_layout.show_capture_popup(), 0.1)


class UserDataManager:
    """用户数据管理器，负责保存和加载用户信息"""
    def __init__(self):
        self.data_file = "user_data.json"
        self.users = OrderedDict()  # 保持插入顺序
        self._load_data()

    def _load_data(self):
        """加载用户数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.users = OrderedDict(json.load(f))
            except Exception as e:
                print(f"加载用户数据失败: {e}")
                self.users = OrderedDict()

    def _save_data(self):
        """保存用户数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户数据失败: {e}")

    def add_user(self, name, id_number, force=False):
        """添加新用户
        force: 如果为True，当用户已存在时会先删除旧记录
        """
        if id_number in self.users:
            if force:
                # 强制模式：先删除旧用户
                self.delete_user(id_number)
            else:
                return False
        # 添加新用户
        self.users[id_number] = {
            'name': name,
            'id': id_number,
            'images': []
        }
        self._save_data()
        return True

    def add_image(self, id_number, image_path):
        """添加用户图片记录"""
        if id_number in self.users:
            self.users[id_number]['images'].append(image_path)
            self._save_data()
            return True
        return False

    def delete_user(self, id_number):
        """删除用户及其所有图片"""
        if id_number in self.users:
            # 删除图片文件
            for img_path in self.users[id_number]['images']:
                if os.path.exists(img_path):
                    os.remove(img_path)
            # 从用户数据中删除
            del self.users[id_number]
            self._save_data()
            return True
        return False

    def get_user_images(self, id_number):
        """获取指定用户的所有图片"""
        return self.users.get(id_number, {}).get('images', [])

    def search_users(self, query):
        """搜索用户"""
        results = []
        query = query.lower()
        for user_id, user_data in self.users.items():
            if (query in user_data['name'].lower() or 
                query in user_id.lower()):
                results.append(user_data.copy())  # 返回副本
        return results

    def get_all_users(self):
        """获取所有用户"""
        return list(self.users.values())


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
        self.title = "注册"
        self.size_hint = (0.8, 0.4)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        # 姓名输入框
        self.name_input = TextInput(hint_text="姓名：", multiline=False, size_hint_y=0.3)
        layout.add_widget(self.name_input)

        # 身份证输入框(带验证)
        self.id_input = TextInput(hint_text="身份证号：", multiline=False, size_hint_y=0.3)
        self.id_input.bind(text=self.validate_id)  # 绑定验证函数
        layout.add_widget(self.id_input)
        
        # 提交按钮(初始不可用)
        self.confirm_button = Button(
            text = "确定",
            size_hint = (1, 0.4),
            disabled = True,
            background_color = [0.5, 0.5, 0.5, 1]  # 灰色表示不可用
        )
        # 绑定回调函数
        self.confirm_button.bind(on_press=lambda x: self._on_confirm(capture_callback))
        layout.add_widget(self.confirm_button)
        
        self.content = layout

    def _on_confirm(self, capture_callback):
        """处理确认按钮点击"""
        # 先关闭弹窗
        self.dismiss()
        # 然后执行回调
        capture_callback(self.name_input.text, self.id_input.text)

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
        result_text = "识别成功!" if result else "识别失败!"
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



class UserManagementPopup(Popup):
    """
    用户管理弹窗 - 用于查询和删除用户
    属性：
        search_input: 搜索输入框(姓名或ID)
        search_button: 搜索按钮
        results_layout: 结果显示区域
        delete_buttons: 删除按钮列表
    """
    def __init__(self, user_manager, **kwargs):
        super(UserManagementPopup, self).__init__(**kwargs)
        self.title = "用户管理"
        self.size_hint = (0.9, 0.8)
        
        # 主布局
        main_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        
        # 搜索区域
        search_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        self.search_input = TextInput(hint_text="输入姓名或身份证号", multiline=False)
        search_layout.add_widget(self.search_input)
        
        search_button = Button(text="搜索", size_hint_x=0.3)
        search_button.bind(on_press=self.search_users)
        search_layout.add_widget(search_button)
        main_layout.add_widget(search_layout)
        
        # 结果区域(带滚动条)
        scroll_view = ScrollView()
        self.results_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.results_layout.bind(minimum_height=self.results_layout.setter('height'))
        scroll_view.add_widget(self.results_layout)
        main_layout.add_widget(scroll_view)
        
        # 关闭按钮
        close_button = Button(text="关闭", size_hint_y=0.1)
        close_button.bind(on_press=lambda x: self.dismiss())
        main_layout.add_widget(close_button)
        
        self.content = main_layout
        self.user_manager = user_manager
    
    def on_open(self):
        """弹窗打开时自动刷新"""
        self.search_users(None)

    def search_users(self, instance):
        """根据输入搜索用户"""
        query = self.search_input.text.strip()
        self.results_layout.clear_widgets()
        
        if query:
            users = self.user_manager.search_users(query)
        else:
            users = self.user_manager.get_all_users()
        
        if not users:
            self._add_result_label("没有找到匹配的用户")
        else:
            for user in users:
                self._add_user_result(user)

    def _add_result_label(self, text):
        """添加结果标签"""
        label = Label(text=text, size_hint_y=None, height=40)
        self.results_layout.add_widget(label)
    
    def _add_user_result(self, user):
        """添加单个用户结果"""
        user_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        
        # 用户信息
        info_label = Label(
            text=f"姓名: {user['name']}  身份证: {user['id']}  照片数: {len(user['images'])}",
            size_hint_x=0.7,
            halign="left",
            valign="middle"
        )
        info_label.bind(size=info_label.setter('text_size'))
        user_layout.add_widget(info_label)
        
        # 删除按钮
        delete_btn = Button(
            text="删除",
            size_hint_x=0.15,
            size_hint_y=0.5,
            pos_hint={'center_y': 0.5},
            background_color=(0.8, 0.2, 0.2, 1)
        )
        delete_btn.bind(
            on_press=lambda x, u=user: self._confirm_delete_user(u))
        user_layout.add_widget(delete_btn)
        
        self.results_layout.add_widget(user_layout)

    def _confirm_delete_user(self, user):
        """显示确认删除弹窗"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(
            text=f"\n确定要删除用户 {user['name']} 吗?\n\n这将删除所有相关照片。"
        ))
        
        btn_layout = BoxLayout(spacing=10)
        confirm_btn = Button(
            text="确认",
            size_hint=(0.5,0.4)
        )
        confirm_btn.bind(
            on_press=lambda x: self._delete_user(user))
        btn_layout.add_widget(confirm_btn)
        
        cancel_btn = Button(
            text="取消",
            size_hint=(0.5,0.4)
        )
        cancel_btn.bind(on_press=lambda x: self.popup.dismiss())
        btn_layout.add_widget(cancel_btn)
        
        content.add_widget(btn_layout)
        
        self.popup = Popup(
            title="确认删除",
            content=content,
            size_hint=(0.6, 0.4))
        self.popup.open()

    def _delete_user(self, user):
        """删除用户及其所有照片"""
        try:
            # 1. 删除图片文件
            for image_path in user['images']:
                if os.path.exists(image_path):
                    os.remove(image_path)
            
            # 2. 从用户数据中删除记录
            self.user_manager.delete_user(user['id'])
            
            self.popup.dismiss()
            self.search_users(None)  # 刷新搜索结果
            
            # 显示成功提示
            success_popup = Popup(
                title="提示",
                content=Label(text=f"用户 {user['name']} 已删除"),
                size_hint=(0.5, 0.3)
            )
            success_popup.open()
            Clock.schedule_once(lambda dt: success_popup.dismiss(), 2)
        except Exception as e:
            error_popup = Popup(
                title="错误",
                content=Label(text=f"删除用户失败: {str(e)}"),
                size_hint=(0.6, 0.4)
            )
            error_popup.open()



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
        
        # 采集按钮(初始隐藏)
        self.capture_btn = Button(
            text="采集",
            size_hint=(0.15, 0.08),
            pos_hint={'right': 0.82, 'top': 0.98},
            background_color=[0.8, 0.2, 0.2, 1],
            opacity=0  # 初始隐藏
        )
        self.capture_btn.bind(on_press=self.capture_image)
        self.add_widget(self.capture_btn)

        # 取消采集按钮(初始隐藏)
        self.cancel_btn = Button(
            text="取消",
            size_hint=(0.15, 0.08),
            pos_hint={'right': 0.99, 'top': 0.98},  # 在采集按钮右边
            background_color=[0.8, 0.2, 0.2, 1],
            opacity=0  # 初始隐藏
        )
        self.cancel_btn.bind(on_press=self.cancel_capture)
        self.add_widget(self.cancel_btn)

        # 设置按钮(右上角红色区域)
        self.settings_button = Button(
            size_hint=(None, None),
            size=(85, 75),
            pos_hint={'right': 0.98, 'top': 0.98},
            background_normal='',
            background_color=[0, 0, 0, 0],  # 白色
            text='设置',
            font_size=24
        )
        self.add_widget(self.settings_button)
        
        # 提示标签
        self.hint_label = Label(
            text="请将手掌放置白色圆圈内！",
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
        self.hand = "左"  # 初始采集左手
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

        # 添加用户数据管理器
        self.user_manager = UserDataManager()

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

    def cancel_capture(self, instance=None):
        """取消采集"""
        if not self.is_capturing:
            return
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text="\n确定取消采集吗?\n\n所有的照片将会被删除。"))
        
        btn_layout = BoxLayout(spacing=10)
        confirm_btn = Button(text="是", size_hint=(0.5, 0.5))
        confirm_btn.bind(on_press=self._confirm_cancel)
        btn_layout.add_widget(confirm_btn)
        
        cancel_btn = Button(text="否", size_hint=(0.5, 0.5))
        cancel_btn.bind(on_press=lambda x: self.popup.dismiss())
        btn_layout.add_widget(cancel_btn)
        
        content.add_widget(btn_layout)
        
        self.popup = Popup(title="确认取消",
                        content=content,
                        size_hint=(0.6, 0.4))
        self.popup.open()

    def _confirm_cancel(self, instance):
        """确认取消采集后重置空闲状态"""
        self.popup.dismiss()
        # 删除临时图片
        if os.path.exists("local_images"):
            # 删除该用户的所有图片
            for image_path in self.user_manager.get_user_images(self.id_number):
                if os.path.exists(image_path):
                    os.remove(image_path)
        
        # 从用户数据中删除该用户
        self.user_manager.delete_user(self.id_number)
        
        self.is_capturing = False
        self.hand = "left"
        self.capture_count = 0
        self.total_captured = 0
        self.progress = 0
        
        self.hint_label.text = "取消采集成功"
        self.hint_label.opacity = 1
        self.settings_button.opacity = 1
        self.settings_button.disabled = False
        self.capture_btn.opacity = 0
        self.cancel_btn.opacity = 0
        
        if self.progress_circle is not None:
            self.canvas.remove(self.progress_circle)
            self.progress_circle = None
        
        Clock.schedule_once(lambda dt: setattr(self.hint_label, 'opacity', 0), 2)
        
    def _perform_recognition(self):
        """实际执行识别逻辑"""
        ret, frame = self.capture.read()
        if ret:
            # 保存临时图像用于比对
            temp_filename = "temp_capture.png"
            cv2.imwrite(temp_filename, frame)
            current_image = cv2.imread(temp_filename, cv2.IMREAD_GRAYSCALE)
            best_match = {"score": 0, "name": None}
            
            # 与存储的所有用户图像比对
            if os.path.exists("local_images"):
                for user_data in self.user_manager.get_all_users():
                    user_score = 0
                    image_count = 0
                    
                    # 比对该用户的所有图片
                    for image_path in user_data['images']:
                        if os.path.exists(image_path):
                            local_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                            similarity = compare_images(current_image, local_image) # compare_images需要完善
                            user_score += similarity
                            image_count += 1
                    
                    # 计算平均相似度
                    if image_count > 0:
                        avg_score = user_score / image_count
                        if avg_score > best_match["score"]:
                            best_match["score"] = avg_score
                            best_match["name"] = user_data['name']
            
            # 显示结果并播放语音
            if best_match["score"] > 0.5:  # 相似度阈值
                popup = RecognitionPopup(result=True, name=best_match["name"])
                self.add_widget(popup)
                Clock.schedule_once(lambda dt: self.play_audio(f"识别成功!"), 0.2)
            else:
                popup = RecognitionPopup(result=False)
                self.add_widget(popup)
                Clock.schedule_once(lambda dt: self.play_audio("识别失败!"), 0.2)
            
            # 重置提示标签
            self.hint_label.text = "请将手掌放置白色圆圈内！"
            Clock.schedule_once(lambda dt: setattr(self.hint_label, 'opacity', 0), 3)

    def show_capture_popup(self):
        """显示注册弹窗"""
        # 先关闭任何已存在的弹窗
        if hasattr(self, 'popup') and self.popup:
            self.popup.dismiss()
        
        # 创建新弹窗
        self.popup = CapturePopup(capture_callback=self.start_capture)
        self.popup.open()

    def start_capture(self, name, id_number):
        """开始采集流程"""
        # 先添加用户到数据库
        if not self.user_manager.add_user(name, id_number):
            self.hint_label.text = "该ID已存在!"
            self.hint_label.opacity = 1
            Clock.schedule_once(lambda dt: setattr(self.hint_label, 'opacity', 0), 2)
            return
        self.name = name
        self.id_number = id_number
        self.is_capturing = True
        self.hand = "left"  # 从左手开始
        self.capture_count = 0
        self.progress = 0
        self.hint_label.text = f"正在采集{self.get_hand_name()}手 (0/10)"
        self.hint_label.opacity = 1  # 显示提示
        # 隐藏settings按钮并且使之失效，显示采集按钮
        self.settings_button.opacity = 0
        self.settings_button.disabled = True
        self.capture_btn.opacity = 1
        self.cancel_btn.opacity = 1  # Show cancel button

    def get_hand_name(self):
        """获取当前采集的手的名称(中文)"""
        return "左" if self.hand == "left" else "右"

    def capture_image(self, instance=None):
        """采集并保存手掌图像"""
        if not self.is_capturing:
            return
        ret, frame = self.capture.read()
        if ret:
            # 创建存储目录(如果不存在)
            if not os.path.exists("local_images"):
                os.makedirs("local_images")
            
            # 使用ID作为文件名，避免中文问题
            filename = f"local_images/{self.id_number}_{self.hand}_{self.capture_count + 1}.png"
            cv2.imwrite(filename, frame)
            
            # 记录图片到用户数据
            self.user_manager.add_image(self.id_number, filename)
            
            self.capture_count += 1
            self.progress += 1
            self.hint_label.text = f"正在采集{self.get_hand_name()}手 ({self.capture_count}/10)"
            
            if self.capture_count >= 10:
                self.progress = 0
                if self.hand == "left":
                    self.hand = "right"
                    self.capture_count = 0
                    self.hint_label.text = f"请将{self.get_hand_name()}手置于圆圈内 (0/10)"
                else:
                    self.hint_label.text = "采集完成!"
                    self.is_capturing = False
                    self.settings_button.opacity = 1
                    self.settings_button.disabled = False
                    self.capture_btn.opacity = 0
                    self.cancel_btn.opacity = 0
                    Clock.schedule_once(self.reset_capture, 2)

    def play_audio(self, text):
        """播放语音反馈"""
        self.engine.say(text)
        self.engine.runAndWait()

    def reset_capture(self, dt):
        """重置采集状态"""
        self.is_capturing = False
        self.hand = "左"
        self.capture_count = 0
        self.hint_label.text = "请将手掌放置白色圆圈内！"
        self.hint_label.opacity = 0
        self.settings_button.opacity = 1
        self.settings_button.disabled = False
        self.cancel_btn.opacity = 0  # Ensure cancel button is hidden

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


    def on_stop(self):
        """应用关闭时释放摄像头"""
        # 获取主屏幕并释放摄像头
        main_screen = self.root.get_screen('main')
        if hasattr(main_screen.camera_layout, 'capture') and main_screen.camera_layout.capture.isOpened():
            main_screen.camera_layout.capture.release()



class MainApp(App):

    # def __init__(self, **kwargs):
    #     super(MainApp, self).__init__(**kwargs)
    #     # 设置系统编码
    #     if sys.version_info[0] < 3:
    #         reload(sys)
    #         sys.setdefaultencoding('utf-8')
    #     locale.setlocale(locale.LC_ALL, '')

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


if __name__ == "__main__":
    MainApp().run()