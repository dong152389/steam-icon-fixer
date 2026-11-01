import os
import time
import requests
from typing import Optional, Callable, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

class IconDownloader:
    """Steam 图标多源下载器与并发管理器"""

    # 官方 CDN 源列表（按优先级尝试，覆盖最新 community_assets 与经典 steamcommunity 路径）
    CDN_TEMPLATES = [
        "https://shared.fastly.steamstatic.com/community_assets/images/apps/{appid}/{hash}.ico",
        "https://shared.akamai.steamstatic.com/community_assets/images/apps/{appid}/{hash}.ico",
        "https://cdn.cloudflare.steamstatic.com/community_assets/images/apps/{appid}/{hash}.ico",
        "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{appid}/{hash}.ico",
        "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/{appid}/{hash}.ico",
        "https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{hash}.ico",
    ]

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, target_dir: str, max_workers: int = 5, proxies: Optional[Dict[str, str]] = None):
        self.target_dir = os.path.normpath(target_dir)
        self.max_workers = max_workers
        self.proxies = proxies
        os.makedirs(self.target_dir, exist_ok=True)

    def download_icon(self, appid: int, icon_hash: str, force: bool = False) -> Dict[str, Any]:
        """
        下载单个游戏的图标
        返回: {'success': bool, 'appid': appid, 'hash': icon_hash, 'path': path, 'error': str, 'skipped': bool}
        """
        if not icon_hash or len(icon_hash) != 40:
            return {
                "success": False,
                "appid": appid,
                "hash": icon_hash,
                "path": None,
                "error": "无效的图标哈希",
                "skipped": False,
            }

        target_file = os.path.join(self.target_dir, f"{icon_hash}.ico")

        # 检查是否已存在且合法
        if not force and os.path.isfile(target_file) and os.path.getsize(target_file) > 100:
            if self._is_valid_ico(target_file):
                return {
                    "success": True,
                    "appid": appid,
                    "hash": icon_hash,
                    "path": target_file,
                    "error": None,
                    "skipped": True,
                }

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "image/x-icon,image/*,*/*;q=0.8",
            "Referer": "https://steamcommunity.com/",
        }

        last_err = None
        for template in self.CDN_TEMPLATES:
            url = template.format(appid=appid, hash=icon_hash)
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=(5, 10),
                    proxies=self.proxies,
                    stream=True
                )
                if resp.status_code == 200:
                    content = resp.content
                    if len(content) > 100 and content[:4] in (b"\x00\x00\x01\x00", b"\x89PNG"):
                        # 写入文件
                        temp_file = target_file + ".tmp"
                        with open(temp_file, "wb") as f:
                            f.write(content)
                        if os.path.isfile(target_file):
                            os.remove(target_file)
                        os.rename(temp_file, target_file)
                        return {
                            "success": True,
                            "appid": appid,
                            "hash": icon_hash,
                            "path": target_file,
                            "error": None,
                            "skipped": False,
                        }
                    else:
                        last_err = f"返回数据非有效图标 (大小: {len(content)})"
                elif resp.status_code == 404:
                    last_err = "404 Not Found"
                else:
                    last_err = f"HTTP {resp.status_code}"
            except Exception as e:
                last_err = str(e)
                time.sleep(0.3)

        return {
            "success": False,
            "appid": appid,
            "hash": icon_hash,
            "path": None,
            "error": last_err or "所有 CDN 源均下载失败",
            "skipped": False,
        }

    def download_batch(
        self,
        tasks: List[Dict[str, Any]],
        on_progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        force: bool = False
    ) -> List[Dict[str, Any]]:
        """
        批量并发下载
        tasks: [{'appid': 2358720, 'hash': '...', 'name': '...'}, ...]
        on_progress: callback(current, total, result)
        """
        total = len(tasks)
        results = []
        if total == 0:
            return results

        completed_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self.download_icon, t["appid"], t["hash"], force): t
                for t in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed_count += 1
                try:
                    res = future.result()
                    res["name"] = task.get("name", f"App {task['appid']}")
                except Exception as e:
                    res = {
                        "success": False,
                        "appid": task["appid"],
                        "hash": task.get("hash"),
                        "name": task.get("name"),
                        "path": None,
                        "error": str(e),
                        "skipped": False,
                    }
                results.append(res)
                if on_progress:
                    on_progress(completed_count, total, res)

        return results

    @staticmethod
    def _is_valid_ico(file_path: str) -> bool:
        """检查文件是否为有效的 .ico 文件（或 png 格式图标）"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                return header in (b"\x00\x00\x01\x00", b"\x89PNG")
        except Exception:
            return False
