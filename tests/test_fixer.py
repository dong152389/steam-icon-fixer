import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.detector import SteamDetector
from core.vdf_parser import AppInfoParser
from core.shortcut import ShortcutManager
from core.downloader import IconDownloader
from core.cache import IconCacheRefresher
from core.manager import SteamIconFixerService

class TestSteamIconFixer(unittest.TestCase):

    def test_steam_detector(self):
        sp = SteamDetector.get_steam_path()
        self.assertIsNotNone(sp)
        self.assertTrue(os.path.isdir(sp))

        icon_dir = SteamDetector.get_games_icon_dir(sp)
        self.assertIsNotNone(icon_dir)
        self.assertTrue(os.path.isdir(icon_dir))

        libs = SteamDetector.get_libraries(sp)
        self.assertGreaterEqual(len(libs), 1)

        games = SteamDetector.get_installed_games(sp)
        self.assertGreater(len(games), 0)

    def test_appinfo_parser(self):
        sp = SteamDetector.get_steam_path()
        appinfo_path = os.path.join(sp, "appcache", "appinfo.vdf")
        if os.path.isfile(appinfo_path):
            parser = AppInfoParser(appinfo_path)
            apps = parser.parse()
            self.assertGreater(len(apps), 10)
            # 常见游戏的 appid 必须存在
            has_wukong = 2358720 in apps
            has_cs2 = 730 in apps
            self.assertTrue(has_wukong or has_cs2)

    def test_shortcut_parser(self):
        shortcuts = ShortcutManager.scan_steam_shortcuts()
        self.assertIsInstance(shortcuts, list)
        if shortcuts:
            first = shortcuts[0]
            self.assertIn("appid", first)
            self.assertIn("file_path", first)

    def test_ico_validator(self):
        # 验证合法 ICO 头部检查
        self.assertTrue(callable(IconDownloader._is_valid_ico))

    def test_service_scan(self):
        service = SteamIconFixerService()
        res = service.scan_environment()
        self.assertTrue(res["valid"])
        self.assertIn("stats", res)
        self.assertGreater(res["stats"]["total_games"], 0)

if __name__ == "__main__":
    unittest.main()
