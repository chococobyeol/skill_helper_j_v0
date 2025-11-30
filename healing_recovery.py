# healing_recovery.py
import time
import win32api
import win32con
import pyautogui
import keyboard
import os
from threading import Thread
from mana_recovery import ManaRecoveryController
import numpy as np
import cv2
import easyocr
import torch
import re
from random_delay import add_delay

class HealingController:
    def __init__(self):
        self.is_running = True
        self.is_active = True
        self.is_healing = False
        pyautogui.PAUSE = 0.1
        pyautogui.FAILSAFE = False
        
        self.mana_controller = ManaRecoveryController()
        self.mana_controller.is_running = True
        
        self.img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'img')
        self.lack_health_path = os.path.join(self.img_dir, 'lack_health.png')
        
        self.HEAL_KEY = 0x35
        self.HOME_KEY = win32con.VK_HOME
        self.ESC_KEY = win32con.VK_ESCAPE
        self.ENTER_KEY = win32con.VK_RETURN
        self.TOGGLE_KEY = 'F8'
        self.EXIT_KEY = 'ctrl+q'
        
        self.is_using_skill = False
        self.heal_area = None
        
        self.check_image_files()
        
        try:
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
            torch.cuda.empty_cache()
            if torch.cuda.is_available():
                device = torch.device('cuda:0')
                torch.cuda.set_device(device)
                print(f"GPU 사용: {torch.cuda.get_device_name(0)}")
                print(f"CUDA 버전: {torch.version.cuda}")
                self.reader = easyocr.Reader(['en'], gpu=True, detector=True, recognizer=True, verbose=False,
                                             model_storage_directory='./easyocr_models', download_enabled=True,
                                             cudnn_benchmark=True)
                print("EasyOCR GPU 모드로 초기화됨")
            else:
                raise RuntimeError("CUDA를 찾을 수 없습니다.")
        except Exception as e:
            print(f"GPU 초기화 실패: {str(e)}")
            print("CPU 모드로 대체합니다.")
            self.reader = easyocr.Reader(['en'], gpu=False)
        
        self.health_threshold = 10000

    def check_image_files(self):
        if not os.path.exists(self.lack_health_path):
            print("\n=== 이미지 파일 확인 필요 ===")
            print(f"파일이 없습니다: {self.lack_health_path}")
            print("=========================\n")

    def send_key(self, key, delay=0.02):
        win32api.keybd_event(key, 0, 0, 0)
        time.sleep(add_delay(delay))
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(add_delay(delay))

    def extract_health_value(self, image):
        try:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
            
            lower_green1 = np.array([40, 50, 50])
            upper_green1 = np.array([80, 255, 255])
            lower_green2 = np.array([47, 43, 206])
            upper_green2 = np.array([49, 53, 216])

            mask1 = cv2.inRange(hsv, lower_green1, upper_green1)
            mask2 = cv2.inRange(hsv, lower_green2, upper_green2)
            green_mask = cv2.bitwise_or(mask1, mask2)
            
            kernel = np.ones((2,2), np.uint8)
            processed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
            
            results = self.reader.readtext(processed, allowlist='0123456789')
            for (bbox, text, prob) in results:
                numbers = re.findall(r'\d+', text.replace(" ", ""))
                if numbers:
                    value = int(numbers[0])
                    if 0 <= value <= 9999999:
                        return value
            return None
        except:
            return None

    def find_image(self, image_path):
        try:
            if self.heal_area is None:
                region = (1285, 900, 314, 33)
            else:
                # QRect 또는 튜플 형식 모두 지원
                if isinstance(self.heal_area, tuple):
                    region = self.heal_area
                else:
                    region = (self.heal_area.x(), self.heal_area.y(),
                              self.heal_area.width(), self.heal_area.height())

            # 디버깅: 영역이 실제로 업데이트되었는지 확인
            if hasattr(self, '_last_heal_region') and self._last_heal_region != region:
                print(f"[DEBUG] 힐 영역 변경: {self._last_heal_region} -> {region}")
            self._last_heal_region = region
            
            screen = pyautogui.screenshot(region=region)
            screen_np = np.array(screen)
            
            health = self.extract_health_value(screen_np)
            if health is not None:
                if health <= self.health_threshold:
                    print(f"현재 체력: {health}")
                return health, health <= self.health_threshold
            return None, False
        except Exception as e:
            print(f"체력 확인 중 오류: {str(e)}")
            return None, False

    def use_heal_skill(self, health):
        if self.macro_controller:
            self.macro_controller.is_using_skill = False
            self.macro_controller.current_skill = None

        print("힐링 스킬 시도 (우선)")
        # 글로벌 락 획득
        with self.macro_controller.key_input_lock:
            try:
                # 방향키와 엔터키 블록
                keyboard.block_key('up')
                keyboard.block_key('down')
                keyboard.block_key('left')
                keyboard.block_key('right')
                keyboard.block_key('enter')
                
                self.send_key(self.ESC_KEY, 0.02)
                # 체력 값에 따라 힐링 횟수 조절
                heal_amount = 500
                print("첫번째 힐링")
                self.send_key(self.HEAL_KEY, 0.02)
                self.send_key(self.HOME_KEY, 0.015)
                self.send_key(self.ENTER_KEY, 0.03)
                if self.health_threshold-health > heal_amount:
                    print("두번째 힐링")
                    self.send_key(self.HEAL_KEY, 0.02)
                    self.send_key(self.HOME_KEY, 0.015)
                    self.send_key(self.ENTER_KEY, 0.03)
                if self.health_threshold-health > heal_amount * 2:
                    print("세번째 힐링")
                    self.send_key(self.HEAL_KEY, 0.02)
                    self.send_key(self.HOME_KEY, 0.015)
                    self.send_key(self.ENTER_KEY, 0.03)
                #옛바에서는 초당 3회가 최대
                # if self.health_threshold-health > heal_amount * 3:
                #     print("네번째 힐링")
                #     self.send_key(self.HEAL_KEY, 0.02)
                #     self.send_key(self.HOME_KEY, 0.015)
                #     self.send_key(self.ENTER_KEY, 0.03)
                # if self.health_threshold-health > heal_amount * 4:
                #     print("다섯번째 힐링")
                #     self.send_key(self.HEAL_KEY, 0.02)
                #     self.send_key(self.HOME_KEY, 0.015)
                #     self.send_key(self.ENTER_KEY, 0.03)
            finally:
                # 키 블록 해제
                keyboard.unblock_key('up')
                keyboard.unblock_key('down')
                keyboard.unblock_key('left')
                keyboard.unblock_key('right')
                keyboard.unblock_key('enter')

    def check_and_heal(self):
        mana_thread = Thread(target=self.mana_controller.check_and_recover_mana)
        mana_thread.daemon = True
        mana_thread.start()

        while self.is_active:
            if self.is_running:
                try:
                    if self.mana_controller.is_recovering:
                        time.sleep(0.01)
                        continue

                    health, needs_healing = self.find_image(self.lack_health_path)
                    if needs_healing and health is not None:
                        self.is_healing = True
                        print("체력 부족: 힐링 스킬 시도")
                        self.use_heal_skill(health)
                        time.sleep(0.03)
                    else:
                        self.is_healing = False

                except Exception as e:
                    print(f"매크로 실행 중 오류: {str(e)}")
                    self.is_healing = False
                
                time.sleep(0.01)
            time.sleep(0.01)

    def toggle_macro(self):
        self.is_running = not self.is_running
        status = "실행 중" if self.is_running else "정지"
        print(f"\n힐링 매크로 상태: {status}")

    @property
    def is_running(self):
        return self._is_running

    @is_running.setter
    def is_running(self, value):
        self._is_running = value

    def take_debug_screenshot(self):
        pass