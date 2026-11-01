import os
import re
import configparser
from typing import List, Dict, Any, Optional

class ShortcutManager:
    """Steam 快捷方式 (.url) 管理器：扫描、校验、修复与创建"""

    INVALID_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')

    @staticmethod
    def get_desktop_paths() -> List[str]:
        """获取当前用户桌面和公共桌面路径"""
        paths = []
        user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(user_desktop):
            paths.append(os.path.normpath(user_desktop))

        public_desktop = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
        if os.path.isdir(public_desktop):
            paths.append(os.path.normpath(public_desktop))

        return paths

    @classmethod
    def scan_steam_shortcuts(cls) -> List[Dict[str, Any]]:
        """
        扫描桌面上的所有 Steam 快捷方式 (.url)
        返回列表: [
            {
                'file_path': 'C:/.../Black Myth Wukong.url',
                'name': 'Black Myth Wukong',
                'appid': 2358720,
                'icon_file': 'C:/Program Files (x86)/Steam/steam/games/0121...ico',
                'icon_hash': '0121...',
                'icon_exists': True/False,
            }
        ]
        """
        shortcuts = []
        for desktop_path in cls.get_desktop_paths():
            try:
                for entry in os.listdir(desktop_path):
                    if entry.lower().endswith(".url"):
                        full_path = os.path.join(desktop_path, entry)
                        info = cls.parse_url_file(full_path)
                        if info:
                            shortcuts.append(info)
            except Exception:
                continue

        return shortcuts

    @classmethod
    def parse_url_file(cls, url_file: str) -> Optional[Dict[str, Any]]:
        """解析单个 .url 文件，判断是否为 Steam 游戏快捷方式"""
        if not os.path.isfile(url_file):
            return None

        try:
            # .url 是标准的 INI 格式，但编码可能是 utf-8 或 ansi (gbk)
            content = None
            for encoding in ("utf-8-sig", "gbk", "utf-8", "cp1252"):
                try:
                    with open(url_file, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not content:
                return None

            # 检查是否包含 steam://rungameid/
            url_match = re.search(r"URL=steam://rungameid/(\d+)", content, re.IGNORECASE)
            if not url_match:
                return None

            appid = int(url_match.group(1))

            # 提取 IconFile
            icon_file_match = re.search(r"IconFile=([^\r\n]+)", content, re.IGNORECASE)
            icon_file = icon_file_match.group(1).strip() if icon_file_match else ""

            # 提取 IconHash（40 字符 hex）
            icon_hash = None
            if icon_file:
                hash_match = re.search(r"([0-9a-fA-F]{40})\.ico", icon_file)
                if hash_match:
                    icon_hash = hash_match.group(1).lower()

            icon_exists = os.path.isfile(icon_file) if icon_file else False

            base_name = os.path.splitext(os.path.basename(url_file))[0]

            return {
                "file_path": os.path.normpath(url_file),
                "name": base_name,
                "appid": appid,
                "icon_file": os.path.normpath(icon_file) if icon_file else "",
                "icon_hash": icon_hash,
                "icon_exists": icon_exists,
            }
        except Exception:
            return None

    @classmethod
    def clean_shortcut_name(cls, raw_name: str) -> str:
        r"""
        按照 Steam 官方客户端规则生成合法的快捷方式文件名：
        移除非法 Windows 文件名字符：\ / : * ? " < > |
        并去除首尾空格
        """
        if not raw_name:
            return ""
        cleaned = "".join(c for c in raw_name if c not in '\\/:*?"<>|')
        return cleaned.strip()

    @classmethod
    def update_shortcut_icon(cls, file_path: str, icon_path: str) -> bool:
        """就地更新已有 .url 文件的 IconFile 字段，保持文件名和其它设置不变"""
        if not os.path.isfile(file_path):
            return False
        try:
            content = None
            used_enc = "utf-8"
            for enc in ("utf-8-sig", "gbk", "utf-8", "cp1252"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        content = f.read()
                    used_enc = enc
                    break
                except UnicodeDecodeError:
                    continue

            if not content:
                return False

            norm_icon = os.path.normpath(icon_path)
            if "IconFile=" in content:
                new_content = re.sub(r"IconFile=[^\r\n]*", f"IconFile={norm_icon}", content, flags=re.IGNORECASE)
            else:
                # 在 [InternetShortcut] 下追加
                if "[InternetShortcut]" in content:
                    new_content = content.replace("[InternetShortcut]", f"[InternetShortcut]\nIconFile={norm_icon}")
                else:
                    new_content = content + f"\nIconFile={norm_icon}\n"

            with open(file_path, "w", encoding=used_enc if used_enc != "cp1252" else "utf-8") as f:
                f.write(new_content)
            return True
        except Exception:
            return False

    @classmethod
    def create_or_update_shortcut(
        cls,
        desktop_dir: str,
        game_name: str,
        appid: int,
        icon_path: str,
        existing_path: Optional[str] = None
    ) -> str:
        """
        在桌面创建或更新 Steam 快捷方式 (.url)
        如果提供了 existing_path 且文件存在，直接就地更新，保留原桌面快捷方式名称；
        否则根据 Steam 官方规则使用规范名称新建快捷方式。
        """
        norm_icon = os.path.normpath(icon_path)

        # 优先就地更新现有文件
        if existing_path and os.path.isfile(existing_path):
            if cls.update_shortcut_icon(existing_path, norm_icon):
                return os.path.normpath(existing_path)

        # 清理文件名中的非法字符（遵循 Steam 官方移除非法字符规则）
        safe_name = cls.clean_shortcut_name(game_name)
        safe_name = safe_name or f"Steam_Game_{appid}"
        target_path = os.path.join(desktop_dir, f"{safe_name}.url")

        content = (
            "[{000214A0-0000-0000-C000-000000000046}]\n"
            "Prop3=19,0\n"
            "[InternetShortcut]\n"
            "IDList=\n"
            "IconIndex=0\n"
            f"URL=steam://rungameid/{appid}\n"
            f"IconFile={norm_icon}\n"
        )

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        return os.path.normpath(target_path)
