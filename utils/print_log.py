# -*- coding: utf-8 -*-
"""
로깅 및 출력 유틸리티
"""
import os
import time
import logging
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console
from rich.terminal_theme import TerminalTheme
import atexit


# 로그 디렉토리 생성
log_dir = Path('log')
log_dir.mkdir(exist_ok=True)

# 타임스탬프
timestamp = time.strftime('%Y%m%d-%H%M%S')

# 로거 설정
logger = logging.getLogger("rich")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(
    log_dir / f'{timestamp}.logger.log',
    mode="a",
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-8s %(filename)s:%(funcName)s:%(lineno)4s %(message)s"
))
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# 터미널 테마
cmd_theme = TerminalTheme(
    background=(0, 0, 0),
    foreground=(255, 255, 255),
    normal=[
        (0, 0, 0),
        (128, 0, 0),
        (0, 128, 0),
        (128, 128, 0),
        (0, 0, 128),
        (128, 0, 128),
        (0, 128, 128),
        (192, 192, 192),
    ],
    bright=[
        (128, 128, 128),
        (255, 0, 0),
        (0, 255, 0),
        (255, 255, 0),
        (0, 0, 255),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 255),
    ]
)

# 콘솔 설정
console_screen = Console(record=True)
console_screen.print("\033[0m")

console_log_file = open(log_dir / f"{timestamp}.console.log", "a", encoding="utf-8")
console_log = Console(record=True, file=console_log_file)
console_log.print("\033[0m")

atexit.register(console_log_file.close)


class PrintHelper:
    """출력 및 로깅 헬퍼 클래스"""
    
    def __init__(self, console_screen: Console, console_log: Console):
        self.console_screen = console_screen
        self.console_log = console_log
        
        self.Debug = self.Blue
        self.Info = self.Green
        self.Warn = self.Yellow
        self.Err = self.Red
        
        self.Value = self.Cyan
        self.Config = self.Magenta
        
        self._stack_offset_color = 4
    
    def __call__(self, *args, **kwargs):
        kwargs.setdefault('_stack_offset', 2)
        self.console_screen.log(*args, **kwargs)
        self.console_log.log(*args, **kwargs)
    
    def save_html(self):
        """HTML로 저장합니다."""
        self.console_screen.save_html(
            log_dir / f"{timestamp}.console.html",
            theme=cmd_theme
        )
    
    def exception(self, *args, **kwargs):
        """예외를 출력합니다."""
        kwargs.setdefault('show_locals', True)
        self.console_screen.print_exception(*args, **kwargs)
        self.console_log.print_exception(*args, **kwargs)
    
    def _color(self, color: str, msg: str, *args, _stack_offset: int = 3):
        """색상이 있는 메시지를 출력합니다."""
        self(f'[{color}]{msg}[/{color}]', *args, _stack_offset=_stack_offset)
    
    def Blue(self, msg: str, *args):
        """파란색 메시지를 출력합니다."""
        self._color('blue', msg, *args, _stack_offset=self._stack_offset_color)
    
    def Yellow(self, msg: str, *args):
        """노란색 메시지를 출력합니다."""
        self._color('yellow', msg, *args, _stack_offset=self._stack_offset_color)
    
    def Red(self, msg: str, *args):
        """빨간색 메시지를 출력합니다."""
        self._color('red', msg, *args, _stack_offset=self._stack_offset_color)
    
    def Green(self, msg: str, *args):
        """초록색 메시지를 출력합니다."""
        self._color('green', msg, *args, _stack_offset=self._stack_offset_color)
    
    def Cyan(self, msg: str, *args):
        """청록색 메시지를 출력합니다."""
        self._color('cyan', msg, *args, _stack_offset=self._stack_offset_color)
    
    def Magenta(self, msg: str, *args):
        """자홍색 메시지를 출력합니다."""
        self._color('magenta', msg, *args, _stack_offset=self._stack_offset_color)
    
    def White(self, msg: str, *args):
        """흰색 메시지를 출력합니다."""
        self._color('white', msg, *args, _stack_offset=self._stack_offset_color)


print = PrintHelper(console_screen, console_log)

# logger도 export
__all__ = ['print', 'logger']

