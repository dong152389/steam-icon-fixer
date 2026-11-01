import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional, List
from PIL import Image

class LocalIconExtractor:
    """
    本地超高清游戏图标提取器
    当 Steam 官方 CDN 返回 404 或未提供 .ico 时，
    自动从本地已安装的游戏可执行文件 (.exe) 或 Steam 缓存中无损提取 256x256 高清图标
    """

    @classmethod
    def extract_from_game_dir(cls, game_dir: str, target_ico_path: str) -> bool:
        """从游戏安装目录扫描主 exe 并提取高清图标"""
        if not game_dir or not os.path.isdir(game_dir):
            return False

        candidates = cls._find_candidate_exes(game_dir)
        for exe_path in candidates:
            if cls.extract_icon_from_exe(exe_path, target_ico_path):
                return True

        return False

    @classmethod
    def extract_icon_from_exe(cls, exe_path: str, target_ico_path: str) -> bool:
        """从单个 exe 中提取 256x256 / 最高分辨率图标并保存为 .ico"""
        if not exe_path or not os.path.isfile(exe_path):
            return False

        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            user32.PrivateExtractIconsW.argtypes = [
                wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(ctypes.c_uint),
                ctypes.c_uint, ctypes.c_uint
            ]
            user32.PrivateExtractIconsW.restype = ctypes.c_uint

            hicon = wintypes.HANDLE()
            piconid = ctypes.c_uint()

            # 优先提取 256x256 高清大图标
            extracted = user32.PrivateExtractIconsW(
                exe_path, 0, 256, 256,
                ctypes.byref(hicon), ctypes.byref(piconid),
                1, 0
            )

            if extracted == 0 or not hicon.value:
                # 尝试提取默认分辨率 (0, 0)
                extracted = user32.PrivateExtractIconsW(
                    exe_path, 0, 0, 0,
                    ctypes.byref(hicon), ctypes.byref(piconid),
                    1, 0
                )

            if extracted == 0 or not hicon.value:
                return False

            class ICONINFO(ctypes.Structure):
                _fields_ = [
                    ('fIcon', wintypes.BOOL),
                    ('xHotspot', wintypes.DWORD),
                    ('yHotspot', wintypes.DWORD),
                    ('hbmMask', wintypes.HANDLE),
                    ('hbmColor', wintypes.HANDLE),
                ]

            class BITMAP(ctypes.Structure):
                _fields_ = [
                    ('bmType', wintypes.LONG),
                    ('bmWidth', wintypes.LONG),
                    ('bmHeight', wintypes.LONG),
                    ('bmWidthBytes', wintypes.LONG),
                    ('bmPlanes', wintypes.WORD),
                    ('bmBitsPixel', wintypes.WORD),
                    ('bmBits', ctypes.c_void_p),
                ]

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', wintypes.DWORD),
                    ('biWidth', wintypes.LONG),
                    ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD),
                    ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD),
                ]

            gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
            gdi32.GetObjectW.restype = ctypes.c_int
            gdi32.GetDIBits.argtypes = [
                wintypes.HANDLE, wintypes.HANDLE, ctypes.c_uint,
                ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
            ]
            gdi32.GetDIBits.restype = ctypes.c_int
            user32.GetDC.argtypes = [wintypes.HANDLE]
            user32.GetDC.restype = wintypes.HANDLE
            user32.ReleaseDC.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            user32.DestroyIcon.argtypes = [wintypes.HANDLE]
            gdi32.DeleteObject.argtypes = [wintypes.HANDLE]

            icon_info = ICONINFO()
            user32.GetIconInfo(hicon, ctypes.byref(icon_info))

            bmp = BITMAP()
            gdi32.GetObjectW(icon_info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bmp))
            width, height = bmp.bmWidth, bmp.bmHeight

            if width <= 0 or height <= 0:
                user32.DestroyIcon(hicon)
                return False

            hdc = user32.GetDC(None)

            bih = BITMAPINFOHEADER()
            bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bih.biWidth = width
            bih.biHeight = -height
            bih.biPlanes = 1
            bih.biBitCount = 32
            bih.biCompression = 0

            buf = (ctypes.c_ubyte * (width * height * 4))()
            ret = gdi32.GetDIBits(hdc, icon_info.hbmColor, 0, height, buf, ctypes.byref(bih), 0)

            user32.ReleaseDC(None, hdc)
            gdi32.DeleteObject(icon_info.hbmColor)
            gdi32.DeleteObject(icon_info.hbmMask)
            user32.DestroyIcon(hicon)

            if ret == 0:
                return False

            im = Image.frombuffer('RGBA', (width, height), bytes(buf), 'raw', 'BGRA', 0, 1)

            os.makedirs(os.path.dirname(target_ico_path), exist_ok=True)
            im.save(target_ico_path, format='ICO')
            return True
        except Exception:
            return False

    @classmethod
    def extract_from_librarycache(cls, steam_path: str, appid: int, target_ico_path: str) -> bool:
        """从 Steam appcache/librarycache/<appid>/ 中寻找缓存图片并转换为 ico"""
        cache_dir = os.path.join(steam_path, "appcache", "librarycache", str(appid))
        if not os.path.isdir(cache_dir):
            return False

        try:
            for entry in os.listdir(cache_dir):
                ext = os.path.splitext(entry)[1].lower()
                if ext in (".jpg", ".jpeg", ".png", ".ico"):
                    src_file = os.path.join(cache_dir, entry)
                    try:
                        im = Image.open(src_file)
                        os.makedirs(os.path.dirname(target_ico_path), exist_ok=True)
                        im.save(target_ico_path, format="ICO")
                        return True
                    except Exception:
                        continue
        except Exception:
            pass

        return False

    @staticmethod
    def _find_candidate_exes(game_dir: str) -> List[str]:
        """按优先级搜索游戏主可执行程序"""
        exes = []
        exclude_keywords = [
            "crash", "report", "update", "patch", "unins", "setup",
            "config", "tool", "server", "eac", "easyanticheat", "battleye"
        ]

        # 1. 先检查根目录
        try:
            for f in os.listdir(game_dir):
                if f.lower().endswith(".exe"):
                    name_lower = f.lower()
                    if not any(k in name_lower for k in exclude_keywords):
                        exes.append(os.path.join(game_dir, f))
        except Exception:
            pass

        # 2. 检查常见子目录 (bin, binaries, win64, win32 等)
        subdirs = ["bin", "binaries", "bin/win64", "binaries/win64", "game", "retail"]
        for sub in subdirs:
            p = os.path.join(game_dir, sub)
            if os.path.isdir(p):
                try:
                    for f in os.listdir(p):
                        if f.lower().endswith(".exe"):
                            name_lower = f.lower()
                            if not any(k in name_lower for k in exclude_keywords):
                                exes.append(os.path.join(p, f))
                except Exception:
                    pass

        # 3. 递归搜索整个游戏目录浅层
        if not exes:
            try:
                for root, dirs, files in os.walk(game_dir):
                    rel = os.path.relpath(root, game_dir)
                    if rel.count(os.sep) > 2:
                        continue
                    for f in files:
                        if f.lower().endswith(".exe"):
                            name_lower = f.lower()
                            if not any(k in name_lower for k in exclude_keywords):
                                exes.append(os.path.join(root, f))
            except Exception:
                pass

        return exes
