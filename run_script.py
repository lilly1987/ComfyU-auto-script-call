# -*- coding: utf-8 -*-
"""
실행 스크립트
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import ComfyUIAutomation

if __name__ == '__main__':
    automation = ComfyUIAutomation()
    automation.run()

