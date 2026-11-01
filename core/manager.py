import os
from typing import List, Dict, Any, Optional, Callable
from .detector import SteamDetector
from .vdf_parser import AppInfoParser
from .downloader import IconDownloader
from .shortcut import ShortcutManager
from .cache import IconCacheRefresher
from .extractor import LocalIconExtractor

class SteamIconFixerService:
    """Steam 图标修复调度核心服务"""

    def __init__(self, steam_path: Optional[str] = None):
        self.steam_path = steam_path or SteamDetector.get_steam_path()
        self.icon_dir = SteamDetector.get_games_icon_dir(self.steam_path) if self.steam_path else None
        self.appinfo_parser = None
        if self.steam_path:
            appinfo_file = os.path.join(self.steam_path, "appcache", "appinfo.vdf")
            self.appinfo_parser = AppInfoParser(appinfo_file)

        self.downloader = IconDownloader(self.icon_dir) if self.icon_dir else None

    def scan_environment(self) -> Dict[str, Any]:
        """
        全面扫描环境：
        返回: {
            'steam_path': str,
            'icon_dir': str,
            'libraries': list,
            'installed_games': list,
            'desktop_shortcuts': list,
            'items': list[GameItemModel],
            'stats': dict
        }
        """
        if not self.steam_path or not os.path.isdir(self.steam_path):
            return {
                "valid": False,
                "error": "未找到 Steam 安装路径，请手动指定",
                "items": [],
                "stats": {},
            }

        # 1. 解析 appinfo.vdf
        app_meta = {}
        if self.appinfo_parser:
            app_meta = self.appinfo_parser.parse()

        # 2. 扫描已安装游戏
        installed = SteamDetector.get_installed_games(self.steam_path)

        # 3. 扫描桌面快捷方式
        shortcuts = ShortcutManager.scan_steam_shortcuts()
        shortcuts_by_appid = {s["appid"]: s for s in shortcuts}

        # 4. 汇总为统一视图模型
        items = []
        missing_icons_count = 0
        missing_shortcuts_count = 0

        # 以已安装游戏为主
        seen_appids = set()
        for g in installed:
            appid = g["appid"]
            seen_appids.add(appid)

            meta = app_meta.get(appid, {})
            meta_hash = meta.get("clienticon")
            shortcut = shortcuts_by_appid.get(appid)
            shortcut_hash = shortcut.get("icon_hash") if shortcut else None

            # 游戏名称：优先使用 Steam 官方本地化中文名称与规范清理名称
            game_display_name = meta.get("clean_name") or meta.get("display_name") or g["name"]

            # 优先使用快捷方式中绑定的 hash（与现有桌面快捷方式精准匹配），否则使用 appinfo.vdf
            icon_hash = shortcut_hash or meta_hash
            fallback_hash = meta_hash if icon_hash != meta_hash else None

            # 检查 ico 文件是否存在
            icon_file = os.path.join(self.icon_dir, f"{icon_hash}.ico") if (self.icon_dir and icon_hash) else None
            icon_exists = os.path.isfile(icon_file) if icon_file else False

            if not icon_exists:
                # 检查备用 hash 是否在本地存在
                if fallback_hash:
                    fb_file = os.path.join(self.icon_dir, f"{fallback_hash}.ico")
                    if os.path.isfile(fb_file):
                        icon_hash = fallback_hash
                        icon_file = fb_file
                        icon_exists = True

            game_dir = os.path.join(g["library_path"], "steamapps", "common", g["installdir"]) if g.get("installdir") else None

            if not icon_exists:
                missing_icons_count += 1
            if not shortcut:
                missing_shortcuts_count += 1

            items.append({
                "appid": appid,
                "name": game_display_name,
                "original_name": g["name"],
                "library_path": g["library_path"],
                "game_dir": game_dir,
                "icon_hash": icon_hash,
                "fallback_hash": fallback_hash,
                "icon_file": icon_file,
                "icon_exists": icon_exists,
                "has_shortcut": shortcut is not None,
                "shortcut_file": shortcut["file_path"] if shortcut else None,
                "is_installed": True,
            })

        # 检查是否有桌面上存在快捷方式，但没有在 installed_games 中的情况（例如外置移动硬盘暂时拔掉）
        for s in shortcuts:
            appid = s["appid"]
            if appid not in seen_appids:
                seen_appids.add(appid)
                meta = app_meta.get(appid, {})
                icon_hash = s.get("icon_hash") or meta.get("clienticon")
                icon_file = os.path.join(self.icon_dir, f"{icon_hash}.ico") if (self.icon_dir and icon_hash) else None
                icon_exists = os.path.isfile(icon_file) if icon_file else False

                if not icon_exists:
                    missing_icons_count += 1

                items.append({
                    "appid": appid,
                    "name": s["name"],
                    "library_path": "未知/未挂载",
                    "icon_hash": icon_hash,
                    "icon_file": icon_file,
                    "icon_exists": icon_exists,
                    "has_shortcut": True,
                    "shortcut_file": s["file_path"],
                    "is_installed": False,
                })

        return {
            "valid": True,
            "steam_path": self.steam_path,
            "icon_dir": self.icon_dir,
            "libraries": SteamDetector.get_libraries(self.steam_path),
            "items": items,
            "stats": {
                "total_games": len(items),
                "installed_count": len(installed),
                "shortcuts_count": len(shortcuts),
                "missing_icons": missing_icons_count,
                "missing_shortcuts": missing_shortcuts_count,
            }
        }

    def fix_items(
        self,
        items: List[Dict[str, Any]],
        create_shortcuts: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        批量修复指定项的图标
        create_shortcuts: 是否同时生成/更新桌面快捷方式
        """
        if not self.downloader:
            return {"success": False, "error": "下载器未初始化"}

        # 筛选需要下载的任务
        tasks = []
        for item in items:
            if item.get("icon_hash"):
                tasks.append({
                    "appid": item["appid"],
                    "hash": item["icon_hash"],
                    "fallback_hash": item.get("fallback_hash"),
                    "name": item["name"],
                })

        user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")

        download_results = []
        def _on_dl_prog(curr, tot, res):
            if progress_callback:
                status = "成功" if res["success"] else f"失败({res.get('error')})"
                progress_callback(curr, tot, f"[{curr}/{tot}] 下载图标: {res.get('name')} - {status}")

        if tasks:
            download_results = self.downloader.download_batch(tasks, on_progress=_on_dl_prog)

            # 对首选 hash 失败且有 fallback_hash 的任务进行二次补试
            retry_tasks = []
            for res, task in zip(download_results, tasks):
                if not res["success"] and task.get("fallback_hash"):
                    retry_tasks.append({
                        "appid": task["appid"],
                        "hash": task["fallback_hash"],
                        "name": task["name"],
                    })

            if retry_tasks:
                def _on_retry_prog(curr, tot, res):
                    if progress_callback:
                        status = "成功" if res["success"] else f"失败({res.get('error')})"
                        progress_callback(curr, tot, f"[重试 {curr}/{tot}] 备用源下载: {res.get('name')} - {status}")

                retry_results = self.downloader.download_batch(retry_tasks, on_progress=_on_retry_prog)
                # 合并结果
                for rr in retry_results:
                    if rr["success"]:
                        for orig in download_results:
                            if orig["appid"] == rr["appid"]:
                                orig["success"] = True
                                orig["hash"] = rr["hash"]
                                orig["path"] = rr["path"]
                                orig["error"] = None
                                break

        # 对未成功下载或缺少哈希的游戏，启动本地多重保底提取（游戏目录 exe 提取 / librarycache 图片转换）
        item_by_appid = {it["appid"]: it for it in items}
        for res in download_results:
            if not res["success"]:
                appid = res["appid"]
                item = item_by_appid.get(appid, {})
                hash_to_use = res.get("hash") or f"app_{appid}"
                target_ico = os.path.join(self.icon_dir, f"{hash_to_use}.ico")

                extracted = False
                # 1. 尝试从已安装游戏根目录提取主 exe 图标
                game_dir = item.get("game_dir")
                if game_dir and os.path.isdir(game_dir):
                    if LocalIconExtractor.extract_from_game_dir(game_dir, target_ico):
                        extracted = True
                        if progress_callback:
                            progress_callback(0, 0, f"从游戏目录提取高清图标成功: {item.get('name')}")

                # 2. 尝试从 Steam librarycache 转换
                if not extracted and self.steam_path:
                    if LocalIconExtractor.extract_from_librarycache(self.steam_path, appid, target_ico):
                        extracted = True
                        if progress_callback:
                            progress_callback(0, 0, f"从 Steam 本地缓存转换图标成功: {item.get('name')}")

                if extracted:
                    res["success"] = True
                    res["path"] = target_ico
                    res["error"] = None
                    item["icon_file"] = target_ico
                    item["icon_exists"] = True

        # 创建/更新快捷方式
        shortcut_created_count = 0
        if create_shortcuts and os.path.isdir(user_desktop):
            for idx, item in enumerate(items, 1):
                icon_file = item.get("icon_file")
                icon_hash = item.get("icon_hash")
                target_ico = icon_file or (os.path.join(self.icon_dir, f"{icon_hash}.ico") if icon_hash else None)
                if target_ico and os.path.isfile(target_ico):
                    try:
                        ShortcutManager.create_or_update_shortcut(
                            desktop_dir=user_desktop,
                            game_name=item["name"],
                            appid=item["appid"],
                            icon_path=target_ico,
                            existing_path=item.get("shortcut_file")
                        )
                        shortcut_created_count += 1
                        if progress_callback:
                            progress_callback(idx, len(items), f"创建/更新桌面快捷方式: {item['name']}")
                    except Exception:
                        pass

        # 刷新 Windows 缓存
        IconCacheRefresher.refresh_quick()

        success_count = sum(1 for r in download_results if r["success"])
        fail_count = len(download_results) - success_count

        return {
            "success": True,
            "total_tasks": len(tasks),
            "downloaded": success_count,
            "failed": fail_count,
            "shortcuts_created": shortcut_created_count,
        }
