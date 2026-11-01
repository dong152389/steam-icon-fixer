import os
import sys
import time
import subprocess
import ctypes
from typing import Tuple

class IconCacheRefresher:
    """Windows 图标缓存刷新与重建工具"""

    SHCNE_ASSOCCHANGED = 0x08000000
    SHCNF_IDLIST = 0x0000

    @classmethod
    def refresh_quick(cls) -> bool:
        """
        轻量级无感刷新（推荐，不重启 Explorer）
        利用 SHChangeNotify 通知 Shell 关联和图标发生变更
        """
        try:
            # 1. Shell API 通知
            ctypes.windll.shell32.SHChangeNotify(
                cls.SHCNE_ASSOCCHANGED,
                cls.SHCNF_IDLIST,
                None,
                None
            )

            # 2. ie4uinit 辅助刷新
            try:
                # Windows 10/11: ie4uinit.exe -show
                subprocess.run(["ie4uinit.exe", "-show"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            return True
        except Exception:
            return False

    @classmethod
    def rebuild_cache_deep(cls) -> Tuple[bool, str]:
        """
        深度强制重建图标缓存（重启 Explorer）
        清理 %LOCALAPPDATA% 下的 IconCache.db 与 Explorer 缓存数据库
        """
        try:
            local_appdata = os.environ.get("LOCALAPPDATA")
            if not local_appdata:
                return False, "无法获取 LOCALAPPDATA 环境变量"

            # 1. 结束 explorer 进程
            subprocess.run(["taskkill", "/F", "/IM", "explorer.exe"], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)

            # 2. 删除缓存文件
            deleted_files = 0
            icon_cache_old = os.path.join(local_appdata, "IconCache.db")
            if os.path.isfile(icon_cache_old):
                try:
                    os.remove(icon_cache_old)
                    deleted_files += 1
                except Exception:
                    pass

            explorer_cache_dir = os.path.join(local_appdata, "Microsoft", "Windows", "Explorer")
            if os.path.isdir(explorer_cache_dir):
                for entry in os.listdir(explorer_cache_dir):
                    if entry.lower().startswith("iconcache") and entry.lower().endswith(".db"):
                        cache_file = os.path.join(explorer_cache_dir, entry)
                        try:
                            os.remove(cache_file)
                            deleted_files += 1
                        except Exception:
                            pass

            # 3. 重新启动 explorer
            subprocess.Popen(["explorer.exe"])
            time.sleep(1)

            # 4. 发送 Shell 通知
            cls.refresh_quick()

            return True, f"成功重建图标缓存 (清理了 {deleted_files} 个缓存文件)"
        except Exception as e:
            # 无论如何确保 explorer 恢复运行
            try:
                subprocess.Popen(["explorer.exe"])
            except Exception:
                pass
            return False, f"重建失败: {str(e)}"
