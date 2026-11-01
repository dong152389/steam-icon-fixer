import os
import struct
import re
from typing import Dict, Optional, Tuple, Any

class AppInfoParser:
    """
    Steam appcache/appinfo.vdf 二进制解析器
    支持 Modern v28/v29 String Table 格式与 Legacy 二进制 KeyValue 格式
    能够在毫秒级内从几兆的二进制文件中提取所有游戏 appid 与 clienticon hash
    """

    MAGIC_V28 = 0x07564428
    MAGIC_V29 = 0x07564429

    def __init__(self, appinfo_path: str):
        self.appinfo_path = appinfo_path
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._parsed = False

    def parse(self) -> Dict[int, Dict[str, Any]]:
        """
        解析 appinfo.vdf，返回字典:
        {
            appid: {
                'name': 'Game Name',
                'clienticon': '40-char-sha1-hex',
            }
        }
        """
        if self._parsed:
            return self._cache

        if not os.path.isfile(self.appinfo_path):
            return {}

        try:
            with open(self.appinfo_path, "rb") as f:
                data = f.read()
        except Exception:
            return {}

        if len(data) < 16:
            return {}

        magic, universe = struct.unpack_from("<II", data, 0)

        if magic >= self.MAGIC_V28:
            self._parse_v28_v29(data, magic)
        else:
            self._parse_legacy(data)

        self._parsed = True
        return self._cache

    def _parse_v28_v29(self, data: bytes, magic: int):
        """解析带有 String Table 的 Modern Steam appinfo.vdf (v28/v29)"""
        try:
            string_table_offset = struct.unpack_from("<Q", data, 8)[0]
            if string_table_offset >= len(data):
                return

            # 解析字符串池
            num_strings = struct.unpack_from("<I", data, string_table_offset)[0]
            st_pos = string_table_offset + 4
            string_table = []
            for _ in range(num_strings):
                end = data.find(b"\x00", st_pos)
                if end == -1:
                    break
                s = data[st_pos:end].decode("utf-8", errors="replace")
                string_table.append(s)
                st_pos = end + 1

            clienticon_idx = string_table.index("clienticon") if "clienticon" in string_table else None
            name_idx = string_table.index("name") if "name" in string_table else None
            common_idx = string_table.index("common") if "common" in string_table else None
            name_loc_idx = string_table.index("name_localized") if "name_localized" in string_table else None
            schinese_idx = string_table.index("schinese") if "schinese" in string_table else None
            tchinese_idx = string_table.index("tchinese") if "tchinese" in string_table else None

            icon_marker = b"\x01" + struct.pack("<I", clienticon_idx) if clienticon_idx is not None else None
            name_marker = b"\x01" + struct.pack("<I", name_idx) if name_idx is not None else None
            common_marker = b"\x00" + struct.pack("<I", common_idx) if common_idx is not None else None
            loc_sec_marker = b"\x00" + struct.pack("<I", name_loc_idx) if name_loc_idx is not None else None

            pos = 16
            data_len = len(data)

            while pos + 8 <= string_table_offset:
                appid = struct.unpack_from("<I", data, pos)[0]
                if appid == 0:
                    break
                size = struct.unpack_from("<I", data, pos + 4)[0]

                entry_start = pos + 8
                entry_end = entry_start + size
                if entry_end > data_len:
                    break

                entry_data = data[entry_start:entry_end]

                # 优先截取 common 段
                common_data = entry_data
                if common_marker:
                    cp = entry_data.find(common_marker)
                    if cp != -1:
                        common_data = entry_data[cp: cp + 6000]

                clienticon = None
                if icon_marker:
                    i_pos = common_data.find(icon_marker)
                    if i_pos != -1:
                        val_start = i_pos + 5
                        val_end = common_data.find(b"\x00", val_start)
                        if val_end != -1:
                            val_str = common_data[val_start:val_end].decode("utf-8", errors="ignore").strip()
                            if len(val_str) == 40:
                                clienticon = val_str

                # 如果没有在 common 找到，尝试在整个 entry 中查找
                if not clienticon and icon_marker:
                    i_pos = entry_data.find(icon_marker)
                    if i_pos != -1:
                        val_start = i_pos + 5
                        val_end = entry_data.find(b"\x00", val_start)
                        if val_end != -1:
                            val_str = entry_data[val_start:val_end].decode("utf-8", errors="ignore").strip()
                            if len(val_str) == 40:
                                clienticon = val_str

                if not clienticon:
                    match = re.search(rb"([0-9a-fA-F]{40})\x00", entry_data)
                    if match:
                        clienticon = match.group(1).decode("utf-8", errors="ignore").lower()

                name = None
                if name_marker:
                    n_pos = common_data.find(name_marker)
                    if n_pos != -1:
                        val_start = n_pos + 5
                        val_end = common_data.find(b"\x00", val_start)
                        if val_end != -1:
                            name = common_data[val_start:val_end].decode("utf-8", errors="ignore").strip()

                # 提取本地化名称 (schinese / tchinese)
                loc_name = None
                if loc_sec_marker:
                    lp = common_data.find(loc_sec_marker)
                    if lp != -1:
                        sec_data = common_data[lp + 5: lp + 1500]
                        for lidx in (schinese_idx, tchinese_idx):
                            if lidx is None:
                                continue
                            lm = b"\x01" + struct.pack("<I", lidx)
                            lmp = sec_data.find(lm)
                            if lmp != -1:
                                v = sec_data[lmp + 5: sec_data.find(b"\x00", lmp + 5)].decode("utf-8", errors="ignore").strip()
                                if v and not v.endswith((".jpg", ".png", ".ico")):
                                    loc_name = v
                                    break

                # 计算 Steam 官方规范的快捷方式名称
                display_name = loc_name or name or f"App {appid}"
                clean_name = self.steam_clean_shortcut_name(display_name)

                if clienticon or name or loc_name:
                    self._cache[appid] = {
                        "name": name or f"App {appid}",
                        "localized_name": loc_name,
                        "display_name": display_name,
                        "clean_name": clean_name,
                        "clienticon": clienticon,
                    }

                pos += 8 + size

        except Exception:
            pass

    def _parse_legacy(self, data: bytes):
        """解析旧版本 Steam 二进制 KeyValue 格式"""
        try:
            # 旧版查找 "clienticon\x00<40 hex>\x00"
            pattern = re.compile(rb"clienticon\x00([0-9a-fA-F]{40})\x00")
            # 通过全局遍历 app 块提取
            pos = 8
            while pos + 8 < len(data):
                appid = struct.unpack_from("<I", data, pos)[0]
                if appid == 0:
                    break
                size = struct.unpack_from("<I", data, pos + 4)[0]
                entry_data = data[pos + 8: pos + 8 + size]

                match = pattern.search(entry_data)
                clienticon = match.group(1).decode("utf-8").lower() if match else None

                name_match = re.search(rb"name\x00([^\x00]+)\x00", entry_data)
                name = name_match.group(1).decode("utf-8", errors="ignore") if name_match else f"App {appid}"

                if clienticon or name:
                    display_name = name or f"App {appid}"
                    self._cache[appid] = {
                        "name": name,
                        "localized_name": None,
                        "display_name": display_name,
                        "clean_name": self.steam_clean_shortcut_name(display_name),
                        "clienticon": clienticon,
                    }

                pos += 8 + size
        except Exception:
            pass

    @staticmethod
    def steam_clean_shortcut_name(raw_name: str) -> str:
        r"""
        按照 Steam 官方客户端规则生成合法的快捷方式文件名：
        移除非法 Windows 文件名字符：\ / : * ? " < > |
        并去除首尾空格
        """
        if not raw_name:
            return ""
        # 过滤非法字符
        cleaned = "".join(c for c in raw_name if c not in '\\/:*?"<>|')
        return cleaned.strip()

    def get_icon_hash(self, appid: int) -> Optional[str]:
        """获取指定 appid 的 clienticon hash"""
        if not self._parsed:
            self.parse()
        info = self._cache.get(appid)
        return info.get("clienticon") if info else None
