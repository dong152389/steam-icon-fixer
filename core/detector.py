import os
import sys
import winreg
from typing import Optional, List, Dict, Any
import vdf

class SteamDetector:
    """Steam 安装路径与游戏库检测器"""

    COMMON_PATHS = [
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        r"D:\Steam",
        r"E:\Steam",
    ]

    @classmethod
    def get_steam_path(cls) -> Optional[str]:
        """自动从注册表或常见路径探测 Steam 安装目录"""
        # 1. 尝试从 HKCU 注册表读取
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                val, _ = winreg.QueryValueEx(key, "SteamPath")
                if val and os.path.isdir(val):
                    return os.path.normpath(val)
        except Exception:
            pass

        # 2. 尝试从 HKLM 64位/32位注册表读取
        for subkey in [r"SOFTWARE\WOW6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as key:
                    val, _ = winreg.QueryValueEx(key, "InstallPath")
                    if val and os.path.isdir(val):
                        return os.path.normpath(val)
            except Exception:
                pass

        # 3. 常见路径回退检查
        for path in cls.COMMON_PATHS:
            if os.path.isdir(path) and os.path.isfile(os.path.join(path, "steam.exe")):
                return os.path.normpath(path)

        return None

    @classmethod
    def get_games_icon_dir(cls, steam_path: Optional[str] = None) -> Optional[str]:
        """获取 steam/games 图标存储目录（自动确保存在）"""
        sp = steam_path or cls.get_steam_path()
        if not sp:
            return None
        icon_dir = os.path.join(sp, "steam", "games")
        try:
            os.makedirs(icon_dir, exist_ok=True)
            return os.path.normpath(icon_dir)
        except Exception:
            return os.path.normpath(icon_dir)

    @classmethod
    def get_libraries(cls, steam_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        解析 steamapps/libraryfolders.vdf，提取所有 Steam 库路径
        返回列表: [{'path': '...', 'apps': {'730': ...}}]
        """
        sp = steam_path or cls.get_steam_path()
        if not sp:
            return []

        vdf_path = os.path.join(sp, "steamapps", "libraryfolders.vdf")
        if not os.path.isfile(vdf_path):
            # 回退：至少当前安装目录算一个
            return [{"path": sp, "apps": {}}]

        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                data = vdf.load(f)

            folders = data.get("libraryfolders", {})
            libraries = []
            for _, folder_info in folders.items():
                if isinstance(folder_info, dict) and "path" in folder_info:
                    lib_path = os.path.normpath(folder_info["path"])
                    apps = folder_info.get("apps", {})
                    libraries.append({
                        "path": lib_path,
                        "apps": apps
                    })
            return libraries
        except Exception:
            return [{"path": sp, "apps": {}}]

    # 忽略非游戏的 Steam 内部运行库组件
    IGNORED_APPIDS = {228980, 228988, 228990, 250820, 1070560}

    @classmethod
    def get_installed_games(cls, steam_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        扫描所有库路径下的 appmanifest_<appid>.acf 文件
        返回所有已安装游戏的详细列表
        """
        libraries = cls.get_libraries(steam_path)
        games = []
        seen_appids = set()

        for lib in libraries:
            lib_path = lib["path"]
            steamapps_dir = os.path.join(lib_path, "steamapps")
            if not os.path.isdir(steamapps_dir):
                continue

            try:
                for entry in os.listdir(steamapps_dir):
                    if entry.startswith("appmanifest_") and entry.endswith(".acf"):
                        acf_path = os.path.join(steamapps_dir, entry)
                        game_info = cls._parse_acf(acf_path, lib_path)
                        if game_info and game_info["appid"] not in seen_appids:
                            if game_info["appid"] in cls.IGNORED_APPIDS:
                                continue
                            seen_appids.add(game_info["appid"])
                            games.append(game_info)
            except Exception:
                continue

        # 按游戏名称排序
        games.sort(key=lambda x: x["name"].lower())
        return games

    @classmethod
    def _parse_acf(cls, acf_path: str, lib_path: str) -> Optional[Dict[str, Any]]:
        """解析单个 appmanifest_<appid>.acf"""
        try:
            with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                data = vdf.load(f)
            app_state = data.get("AppState", {})
            appid_str = str(app_state.get("appid", ""))
            if not appid_str:
                return None

            appid = int(appid_str)
            name = app_state.get("name", f"App {appid}")
            installdir = app_state.get("installdir", "")
            size_on_disk = int(app_state.get("SizeOnDisk", 0))

            return {
                "appid": appid,
                "name": name,
                "installdir": installdir,
                "library_path": lib_path,
                "acf_path": acf_path,
                "size_on_disk": size_on_disk
            }
        except Exception:
            return None
