"""
HADJ NO-TOUCH OFFLINE AI - Hardware & Sensor Diagnostics Suite
Runs comprehensive local health checks across Camera, Mic, TTS, Screen, and Automation.
"""

import sys
import os
import time

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def run_diagnostics():
    print("=" * 65)
    print("      HADJ NO-TOUCH OFFLINE AI - SYSTEM DIAGNOSTICS SUITE")
    print("=" * 65)
    print()

    checks_passed = 0
    total_checks = 7

    # 1. Python Environment Check
    print("[1/7] Python Runtime:")
    print(f"      Version: {sys.version.split()[0]} ({sys.platform})")
    print(f"      Executable: {sys.executable}")
    if sys.version_info >= (3, 10):
        print("      Status: PASS (Python 3.10+ confirmed)")
        checks_passed += 1
    else:
        print("      Status: WARN (Recommend Python 3.11+)")

    print()

    # 2. Windows Screen & Resolution
    print("[2/7] Windows Display & Automation:")
    try:
        import pyautogui
        w, h = pyautogui.size()
        print(f"      Resolution: {w} x {h}")
        print("      PyAutoGUI Automation: Available")
        print("      Status: PASS")
        checks_passed += 1
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()

    # 3. Camera & OpenCV
    print("[3/7] Camera & Vision Hardware:")
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w, c = frame.shape
                print(f"      Camera 0: Detected ({w}x{h}, {c} channels)")
                print("      Status: PASS")
                checks_passed += 1
            else:
                print("      Status: WARN (Camera opened but no frame captured)")
        else:
            print("      Status: WARN (Webcam not accessible or in use)")
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()

    # 4. MediaPipe Hand Tracking Model
    print("[4/7] MediaPipe Hand Tracking:")
    try:
        import mediapipe as mp
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(max_num_hands=1)
        hands.close()
        print("      Hand Landmark Model: Initialized successfully")
        print("      Status: PASS")
        checks_passed += 1
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()

    # 5. Offline Speech & Microphone
    print("[5/7] Microphone & Speech Recognition:")
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        print(f"      Audio Input Devices Detected: {len(mics)}")
        if mics:
            print(f"      Default Device: {mics[0]}")
            print("      Status: PASS")
            checks_passed += 1
        else:
            print("      Status: WARN (No microphone device detected)")
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()

    # 6. Windows SAPI Text-to-Speech
    print("[6/7] Offline TTS Audio Feedback (Windows SAPI):")
    try:
        import pyttsx3
        tts = pyttsx3.init()
        voices = tts.getProperty("voices")
        print(f"      Installed Offline Voices: {len(voices)}")
        for v in voices[:3]:
            print(f"        • {v.name}")
        print("      Status: PASS")
        checks_passed += 1
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()

    # 7. System Resources
    print("[7/7] System Resource Overhead:")
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        print(f"      CPU Usage: {cpu}%")
        print(f"      RAM Usage: {mem.percent}% ({round(mem.used / (1024**3), 1)}GB / {round(mem.total / (1024**3), 1)}GB)")
        print("      Status: PASS")
        checks_passed += 1
    except Exception as e:
        print(f"      Status: FAIL ({e})")

    print()
    print("=" * 65)
    print(f"  DIAGNOSTICS COMPLETE: {checks_passed}/{total_checks} CHECKS PASSED")
    print("=" * 65)
    print()


if __name__ == "__main__":
    run_diagnostics()
