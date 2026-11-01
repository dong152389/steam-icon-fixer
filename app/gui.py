import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw
from typing import List, Dict, Any, Optional

from core.manager import SteamIconFixerService
from core.detector import SteamDetector
from core.cache import IconCacheRefresher
from core.shortcut import ShortcutManager

# 设置全局外观
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# 多语言国际化字典
I18N = {
    "zh": {
        "app_title": "Steam 图标自动修复大师",
        "header_title": "🎮 Steam 图标修复助手",
        "select_path": "选择路径",
        "rescan": "🔄 重新扫描",
        "toggle_theme": "🌓 主题",
        "toggle_lang": "🌐 EN",
        "card_total": "检测游戏总数",
        "card_shortcuts": "桌面快捷方式",
        "card_normal": "图标正常",
        "card_missing": "待修复缺失",
        "search_placeholder": "🔍 搜索游戏名称或 AppID...",
        "filter_all": "全部",
        "filter_missing_icons": "仅缺失图标",
        "filter_missing_shortcuts": "仅缺快捷方式",
        "sync_shortcuts": "同步补全桌面快捷方式",
        "fix_missing_btn": "🚀 一键修复缺失图标",
        "refresh_cache_btn": "🔄 刷新桌面缓存",
        "th_select_all": "全选",
        "th_icon": "图标",
        "th_name": "游戏名称",
        "th_appid": "AppID",
        "th_library": "游戏库",
        "th_icon_status": "图标状态",
        "th_shortcut": "快捷方式",
        "th_action": "操作",
        "status_normal": "● 正常",
        "status_missing": "● 缺失",
        "sc_created": "✓ 已创建",
        "sc_missing": "✗ 未创建",
        "action_fix": "修复",
        "status_ready": "准备就绪",
        "status_scanning": "正在扫描 Steam 安装路径与游戏库...",
        "status_scan_complete": "扫描完成！找到 {total} 款游戏，{missing} 款缺失图标。",
        "status_fixing": "正在处理任务...",
        "status_fix_done": "修复完成！成功下载/提取 {downloaded} 个图标",
        "shortcuts_updated_suffix": "，同步创建/更新了 {count} 个桌面快捷方式",
        "cache_refreshed": "已向 Windows Shell 发送图标刷新通知！",
        "no_fix_needed": "当前没有需要修复的图标！",
        "tip": "提示",
        "success": "成功",
        "complete": "完成",
        "error": "错误",
        "no_match": "没有找到匹配的游戏项",
    },
    "en": {
        "app_title": "Steam Icon Fixer",
        "header_title": "🎮 Steam Icon Fixer",
        "select_path": "Select Path",
        "rescan": "🔄 Rescan",
        "toggle_theme": "🌓 Theme",
        "toggle_lang": "🌐 中文",
        "card_total": "Total Games",
        "card_shortcuts": "Shortcuts",
        "card_normal": "Icons Normal",
        "card_missing": "Missing Icons",
        "search_placeholder": "🔍 Search game name or AppID...",
        "filter_all": "All",
        "filter_missing_icons": "Missing Icons",
        "filter_missing_shortcuts": "Missing Shortcuts",
        "sync_shortcuts": "Sync Desktop Shortcuts",
        "fix_missing_btn": "🚀 Fix Missing Icons",
        "refresh_cache_btn": "🔄 Refresh Cache",
        "th_select_all": "All",
        "th_icon": "Icon",
        "th_name": "Game Name",
        "th_appid": "AppID",
        "th_library": "Library",
        "th_icon_status": "Icon Status",
        "th_shortcut": "Shortcut",
        "th_action": "Action",
        "status_normal": "● Normal",
        "status_missing": "● Missing",
        "sc_created": "✓ Created",
        "sc_missing": "✗ Missing",
        "action_fix": "Fix",
        "status_ready": "Ready",
        "status_scanning": "Scanning Steam installation and libraries...",
        "status_scan_complete": "Scan complete! Found {total} games, {missing} missing icons.",
        "status_fixing": "Processing tasks...",
        "status_fix_done": "Fix complete! Successfully retrieved {downloaded} icons",
        "shortcuts_updated_suffix": ", updated/created {count} desktop shortcuts",
        "cache_refreshed": "Windows Shell icon refresh notification sent!",
        "no_fix_needed": "No icons need to be fixed!",
        "tip": "Notice",
        "success": "Success",
        "complete": "Complete",
        "error": "Error",
        "no_match": "No matching games found",
    }
}

class SteamIconFixerApp(ctk.CTk):
    """Steam 图标修复工具现代 GUI 客户端"""

    def __init__(self):
        super().__init__()

        self.lang = "zh"  # 默认中文界面，可自由切换中英文

        # 1. 窗口标题：删除 (Steam Icon Fixer) 括号，中英文由语言切换决定
        self.title(self._t("app_title"))
        self.geometry("1020x700")
        self.minsize(880, 580)

        # 初始化核心服务
        self.service = SteamIconFixerService()
        self.scan_data: Dict[str, Any] = {}
        self.display_items: List[Dict[str, Any]] = []
        self.selected_appids = set()

        # 图标缓存池与占位图
        self._icon_cache: Dict[str, ctk.CTkImage] = {}
        self._placeholder_icon: Optional[ctk.CTkImage] = None
        self._init_placeholder_icon()

        self._build_ui()
        self.after(100, self.start_scan_thread)

    def _t(self, key: str, **kwargs) -> str:
        """多语言本地化获取函数"""
        template = I18N.get(self.lang, I18N["zh"]).get(key, key)
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def _init_placeholder_icon(self):
        """生成缺失图标时展示的高清圆角占位图"""
        try:
            im = Image.new("RGBA", (26, 26), (255, 255, 255, 0))
            draw = ImageDraw.Draw(im)
            draw.rounded_rectangle([(1, 1), (24, 24)], radius=5, fill=(120, 130, 145, 50), outline=(239, 68, 68, 160), width=1)
            # 绘制灰色圆点或感叹号
            draw.ellipse([(11, 6), (14, 13)], fill=(239, 68, 68, 200))
            draw.ellipse([(11, 17), (14, 20)], fill=(239, 68, 68, 200))
            self._placeholder_icon = ctk.CTkImage(light_image=im, dark_image=im, size=(26, 26))
        except Exception:
            self._placeholder_icon = None

    def _get_game_icon(self, icon_path: Optional[str]) -> Optional[ctk.CTkImage]:
        """获取或缓存游戏的 CTkImage 缩略图"""
        if not icon_path or not os.path.isfile(icon_path):
            return self._placeholder_icon

        if icon_path in self._icon_cache:
            return self._icon_cache[icon_path]

        try:
            pil_img = Image.open(icon_path)
            pil_img = pil_img.convert("RGBA")
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(26, 26))
            self._icon_cache[icon_path] = ctk_img
            return ctk_img
        except Exception:
            return self._placeholder_icon

    def _build_ui(self):
        # 主网格布局：
        # row 0: Header (自适应)
        # row 1: Stats 卡片 (自适应)
        # row 2: 控制搜索工具栏 (自适应紧凑布局，彻底消除空白)
        # row 3: 游戏列表区域 (weight=1，撑满所有剩余高度)
        # row 4: Footer 状态栏 (自适应)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # 1. 顶部 Header
        self._build_header()

        # 2. 统计卡片与操作栏
        self._build_stats_and_actions()

        # 3. 游戏列表区域
        self._build_list_view()

        # 4. 底部状态栏与进度条
        self._build_footer()

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#161c24"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self._t("header_title"),
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=("#1976D2", "#4dabf7")
        )
        self.title_label.grid(row=0, column=0, padx=(18, 10), pady=10, sticky="w")

        # Steam 路径信息与更换按钮
        self.path_var = tk.StringVar(value=f"Steam: {self.service.steam_path or '未找到'}")
        self.path_label = ctk.CTkLabel(
            self.header_frame,
            textvariable=self.path_var,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.path_label.grid(row=0, column=1, padx=6, pady=10, sticky="w")

        self.change_path_btn = ctk.CTkButton(
            self.header_frame,
            text=self._t("select_path"),
            width=68,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self._on_choose_path
        )
        self.change_path_btn.grid(row=0, column=2, padx=4, pady=10)

        self.rescan_btn = ctk.CTkButton(
            self.header_frame,
            text=self._t("rescan"),
            width=76,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.start_scan_thread
        )
        self.rescan_btn.grid(row=0, column=3, padx=4, pady=10)

        # 切换语言按钮
        self.lang_btn = ctk.CTkButton(
            self.header_frame,
            text=self._t("toggle_lang"),
            width=68,
            height=26,
            fg_color="transparent",
            border_width=1,
            font=ctk.CTkFont(size=11),
            command=self._toggle_language
        )
        self.lang_btn.grid(row=0, column=4, padx=4, pady=10)

        self.theme_btn = ctk.CTkButton(
            self.header_frame,
            text=self._t("toggle_theme"),
            width=68,
            height=26,
            fg_color="transparent",
            border_width=1,
            font=ctk.CTkFont(size=11),
            command=self._toggle_theme
        )
        self.theme_btn.grid(row=0, column=5, padx=(4, 18), pady=10)

    def _build_stats_and_actions(self):
        # 统计卡片容器
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=0, sticky="ew", padx=18, pady=(8, 4))
        container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 统计卡片 1: 扫描游戏总数
        self.card_total_title, self.card_total = self._create_stat_card(container, 0, self._t("card_total"), "0", "#339af0")
        # 统计卡片 2: 快捷方式总数
        self.card_shortcuts_title, self.card_shortcuts = self._create_stat_card(container, 1, self._t("card_shortcuts"), "0", "#51cf66")
        # 统计卡片 3: 图标正常数
        self.card_normal_title, self.card_normal = self._create_stat_card(container, 2, self._t("card_normal"), "0", "#20c997")
        # 统计卡片 4: 待修复/缺失图标数
        self.card_missing_title, self.card_missing = self._create_stat_card(container, 3, self._t("card_missing"), "0", "#ff6b6b")

        # 快捷工具控制栏（紧凑排列，无任何垂直拉伸多余空白）
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 6))

        # 搜索与过滤（左侧）
        left_ctrl = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        left_ctrl.pack(side="left", fill="x", expand=True)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._apply_filter())
        self.search_entry = ctk.CTkEntry(
            left_ctrl,
            placeholder_text=self._t("search_placeholder"),
            textvariable=self.search_var,
            width=240,
            height=32
        )
        self.search_entry.pack(side="left", padx=(0, 10))

        self.filter_var = tk.StringVar(value="all")
        self.filter_seg = ctk.CTkSegmentedButton(
            left_ctrl,
            values=[self._t("filter_all"), self._t("filter_missing_icons"), self._t("filter_missing_shortcuts")],
            command=self._on_filter_changed
        )
        self.filter_seg.set(self._t("filter_all"))
        self.filter_seg.pack(side="left")

        # 右侧操作按钮
        right_ctrl = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        right_ctrl.pack(side="right")

        self.create_shortcuts_cb = ctk.CTkCheckBox(
            right_ctrl,
            text=self._t("sync_shortcuts"),
            font=ctk.CTkFont(size=12)
        )
        self.create_shortcuts_cb.select()
        self.create_shortcuts_cb.pack(side="left", padx=8)

        self.fix_all_btn = ctk.CTkButton(
            right_ctrl,
            text=self._t("fix_missing_btn"),
            font=ctk.CTkFont(weight="bold", size=13),
            fg_color="#1c7ed6",
            hover_color="#1864ab",
            height=32,
            command=self._on_fix_missing_clicked
        )
        self.fix_all_btn.pack(side="left", padx=4)

        self.refresh_cache_btn = ctk.CTkButton(
            right_ctrl,
            text=self._t("refresh_cache_btn"),
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color=("#495057", "#343a40"),
            hover_color=("#343a40", "#212529"),
            command=self._on_refresh_cache_clicked
        )
        self.refresh_cache_btn.pack(side="left", padx=(4, 0))

    def _create_stat_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent, fg_color=("white", "#1e2430"), corner_radius=8)
        card.grid(row=0, column=col, padx=4, pady=2, sticky="ew")

        t_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color="gray")
        t_lbl.pack(anchor="w", padx=12, pady=(6, 0))

        v_lbl = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=color
        )
        v_lbl.pack(anchor="w", padx=12, pady=(0, 6))
        return t_lbl, v_lbl

    def _build_list_view(self):
        # 列表外层卡片（撑满垂直区域）
        list_container = ctk.CTkFrame(self, fg_color=("white", "#1e2430"), corner_radius=8)
        list_container.grid(row=3, column=0, sticky="nsew", padx=18, pady=(2, 8))
        list_container.grid_rowconfigure(1, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        # 表头配置：包含独立的【图标】列与完整的网格宽度对齐
        header = ctk.CTkFrame(list_container, height=36, fg_color=("gray90", "#28303f"), corner_radius=6)
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        header.grid_columnconfigure(2, weight=1)

        self.select_all_btn = ctk.CTkButton(
            header,
            text=self._t("th_select_all"),
            width=46,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            command=self._toggle_select_all
        )
        self.select_all_btn.grid(row=0, column=0, padx=(8, 4), pady=4)

        self.th_icon_lbl = ctk.CTkLabel(header, text=self._t("th_icon"), font=ctk.CTkFont(size=12, weight="bold"), width=34)
        self.th_icon_lbl.grid(row=0, column=1, padx=4)

        self.th_name_lbl = ctk.CTkLabel(header, text=self._t("th_name"), font=ctk.CTkFont(size=12, weight="bold"))
        self.th_name_lbl.grid(row=0, column=2, sticky="w", padx=8)

        self.th_appid_lbl = ctk.CTkLabel(header, text=self._t("th_appid"), font=ctk.CTkFont(size=12, weight="bold"), width=85)
        self.th_appid_lbl.grid(row=0, column=3, padx=4)

        self.th_library_lbl = ctk.CTkLabel(header, text=self._t("th_library"), font=ctk.CTkFont(size=12, weight="bold"), width=110)
        self.th_library_lbl.grid(row=0, column=4, padx=4)

        self.th_status_lbl = ctk.CTkLabel(header, text=self._t("th_icon_status"), font=ctk.CTkFont(size=12, weight="bold"), width=85)
        self.th_status_lbl.grid(row=0, column=5, padx=4)

        self.th_sc_lbl = ctk.CTkLabel(header, text=self._t("th_shortcut"), font=ctk.CTkFont(size=12, weight="bold"), width=85)
        self.th_sc_lbl.grid(row=0, column=6, padx=4)

        self.th_action_lbl = ctk.CTkLabel(header, text=self._t("th_action"), font=ctk.CTkFont(size=12, weight="bold"), width=65)
        self.th_action_lbl.grid(row=0, column=7, padx=(4, 12))

        # 可滚动的项目列表
        self.scrollable_list = ctk.CTkScrollableFrame(list_container, fg_color="transparent")
        self.scrollable_list.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.scrollable_list.grid_columnconfigure(2, weight=1)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=("gray85", "#161c24"))
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value=self._t("status_ready"))
        self.status_label = ctk.CTkLabel(
            footer,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.grid(row=0, column=0, padx=18, pady=6, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(footer, width=220, height=10)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, padx=18, pady=6, sticky="e")

    def _toggle_language(self):
        """切换中英文语言界面"""
        self.lang = "en" if self.lang == "zh" else "zh"
        self.title(self._t("app_title"))
        self.title_label.configure(text=self._t("header_title"))
        self.change_path_btn.configure(text=self._t("select_path"))
        self.rescan_btn.configure(text=self._t("rescan"))
        self.lang_btn.configure(text=self._t("toggle_lang"))
        self.theme_btn.configure(text=self._t("toggle_theme"))

        self.card_total_title.configure(text=self._t("card_total"))
        self.card_shortcuts_title.configure(text=self._t("card_shortcuts"))
        self.card_normal_title.configure(text=self._t("card_normal"))
        self.card_missing_title.configure(text=self._t("card_missing"))

        self.search_entry.configure(placeholder_text=self._t("search_placeholder"))
        self.filter_seg.configure(values=[self._t("filter_all"), self._t("filter_missing_icons"), self._t("filter_missing_shortcuts")])
        self.create_shortcuts_cb.configure(text=self._t("sync_shortcuts"))
        self.fix_all_btn.configure(text=self._t("fix_missing_btn"))
        self.refresh_cache_btn.configure(text=self._t("refresh_cache_btn"))

        self.select_all_btn.configure(text=self._t("th_select_all"))
        self.th_icon_lbl.configure(text=self._t("th_icon"))
        self.th_name_lbl.configure(text=self._t("th_name"))
        self.th_appid_lbl.configure(text=self._t("th_appid"))
        self.th_library_lbl.configure(text=self._t("th_library"))
        self.th_status_lbl.configure(text=self._t("th_icon_status"))
        self.th_sc_lbl.configure(text=self._t("th_shortcut"))
        self.th_action_lbl.configure(text=self._t("th_action"))

        self._apply_filter()

    def start_scan_thread(self):
        """后台异步执行扫描"""
        self.status_var.set(self._t("status_scanning"))
        self.progress_bar.set(0.2)
        self.fix_all_btn.configure(state="disabled")

        def _worker():
            data = self.service.scan_environment()
            self.after(0, lambda: self._on_scan_completed(data))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_completed(self, data: Dict[str, Any]):
        self.scan_data = data
        self.progress_bar.set(1.0)
        self.fix_all_btn.configure(state="normal")

        if not data.get("valid"):
            err_msg = data.get("error", "Error")
            self.status_var.set(f"扫描异常: {err_msg}")
            messagebox.showerror(self._t("error"), err_msg)
            return

        stats = data.get("stats", {})
        self.card_total.configure(text=str(stats.get("total_games", 0)))
        self.card_shortcuts.configure(text=str(stats.get("shortcuts_count", 0)))
        normal_count = stats.get("total_games", 0) - stats.get("missing_icons", 0)
        self.card_normal.configure(text=str(max(0, normal_count)))
        self.card_missing.configure(text=str(stats.get("missing_icons", 0)))

        self.path_var.set(f"Steam: {self.service.steam_path}")
        self.status_var.set(self._t(
            "status_scan_complete",
            total=len(data["items"]),
            missing=stats.get("missing_icons", 0)
        ))

        self._apply_filter()

    def _apply_filter(self):
        items = self.scan_data.get("items", [])
        keyword = self.search_var.get().strip().lower()
        filter_type = self.filter_seg.get()

        filtered = []
        for it in items:
            # 搜索词过滤（支持中文名称、英文原名、AppID）
            if keyword:
                name_match = keyword in it["name"].lower()
                orig_match = keyword in it.get("original_name", "").lower()
                appid_match = keyword in str(it["appid"])
                if not (name_match or orig_match or appid_match):
                    continue

            # 状态过滤
            if filter_type in (I18N["zh"]["filter_missing_icons"], I18N["en"]["filter_missing_icons"]) and it["icon_exists"]:
                continue
            if filter_type in (I18N["zh"]["filter_missing_shortcuts"], I18N["en"]["filter_missing_shortcuts"]) and it["has_shortcut"]:
                continue

            filtered.append(it)

        self.display_items = filtered
        self._render_items()

    def _on_filter_changed(self, value):
        self._apply_filter()

    def _render_items(self):
        # 清除现有控件
        for widget in self.scrollable_list.winfo_children():
            widget.destroy()

        if not self.display_items:
            empty_lbl = ctk.CTkLabel(
                self.scrollable_list,
                text=self._t("no_match"),
                font=ctk.CTkFont(size=13),
                text_color="gray"
            )
            empty_lbl.pack(pady=30)
            return

        for idx, item in enumerate(self.display_items):
            row = ctk.CTkFrame(
                self.scrollable_list,
                fg_color=("white", "#232a36") if idx % 2 == 0 else ("gray95", "#1a202c"),
                corner_radius=4,
                height=38
            )
            row.pack(fill="x", expand=True, pady=1)
            row.grid_columnconfigure(2, weight=1)

            # 0. 复选框
            chk_var = tk.BooleanVar(value=item["appid"] in self.selected_appids)
            def _on_chk(aid=item["appid"], var=chk_var):
                if var.get():
                    self.selected_appids.add(aid)
                else:
                    self.selected_appids.discard(aid)

            chk = ctk.CTkCheckBox(row, text="", width=24, variable=chk_var, command=_on_chk)
            chk.grid(row=0, column=0, padx=(8, 4), pady=4)

            # 1. 游戏 ICO 图标缩略图预览（26x26）
            icon_img = self._get_game_icon(item.get("icon_file") if item.get("icon_exists") else None)
            icon_lbl = ctk.CTkLabel(row, text="", image=icon_img, width=34)
            icon_lbl.grid(row=0, column=1, padx=4, pady=4)

            # 2. 游戏名称（显示 Steam 官方标准本地化名称）
            display_name = item["name"]
            orig_name = item.get("original_name")
            if orig_name and orig_name != display_name and orig_name.lower() not in display_name.lower():
                display_title = f"{display_name}  ({orig_name})"
            else:
                display_title = display_name

            name_lbl = ctk.CTkLabel(
                row,
                text=display_title,
                font=ctk.CTkFont(size=12),
                anchor="w"
            )
            name_lbl.grid(row=0, column=2, sticky="ew", padx=8, pady=4)

            # 3. AppID
            ctk.CTkLabel(
                row,
                text=str(item["appid"]),
                font=ctk.CTkFont(size=11),
                text_color="gray",
                width=85
            ).grid(row=0, column=3, padx=4)

            # 4. 库路径简写 (盘符)
            lib_str = item["library_path"]
            if len(lib_str) > 16:
                drive = os.path.splitdrive(lib_str)[0] or lib_str[:3]
                lib_str = f"{drive} 盘库" if self.lang == "zh" else f"Drive {drive}"

            ctk.CTkLabel(
                row,
                text=lib_str,
                font=ctk.CTkFont(size=11),
                text_color="gray",
                width=110
            ).grid(row=0, column=4, padx=4)

            # 5. 图标状态徽章
            if item["icon_exists"]:
                icon_badge = ctk.CTkLabel(
                    row,
                    text=self._t("status_normal"),
                    font=ctk.CTkFont(size=11),
                    text_color="#51cf66",
                    width=85
                )
            else:
                icon_badge = ctk.CTkLabel(
                    row,
                    text=self._t("status_missing"),
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#ff6b6b",
                    width=85
                )
            icon_badge.grid(row=0, column=5, padx=4)

            # 6. 快捷方式状态
            sc_text = self._t("sc_created") if item["has_shortcut"] else self._t("sc_missing")
            sc_color = "#20c997" if item["has_shortcut"] else "gray"
            ctk.CTkLabel(
                row,
                text=sc_text,
                font=ctk.CTkFont(size=11),
                text_color=sc_color,
                width=85
            ).grid(row=0, column=6, padx=4)

            # 7. 单项修复按钮
            fix_btn = ctk.CTkButton(
                row,
                text=self._t("action_fix"),
                width=48,
                height=22,
                font=ctk.CTkFont(size=11),
                command=lambda it=item: self._on_fix_single(it)
            )
            fix_btn.grid(row=0, column=7, padx=(4, 10), pady=4)

    def _toggle_select_all(self):
        if len(self.selected_appids) == len(self.display_items):
            self.selected_appids.clear()
        else:
            self.selected_appids = {it["appid"] for it in self.display_items}
        self._render_items()

    def _on_fix_missing_clicked(self):
        """修复所有缺失图标或选中项"""
        items = self.scan_data.get("items", [])
        if self.selected_appids:
            target_items = [it for it in items if it["appid"] in self.selected_appids]
        else:
            target_items = [it for it in items if not it["icon_exists"]]

        if not target_items:
            messagebox.showinfo(self._t("tip"), self._t("no_fix_needed"))
            return

        create_sc = self.create_shortcuts_cb.get() == 1
        self._start_fix_thread(target_items, create_sc)

    def _on_fix_single(self, item: Dict[str, Any]):
        create_sc = self.create_shortcuts_cb.get() == 1
        self._start_fix_thread([item], create_sc)

    def _start_fix_thread(self, items: List[Dict[str, Any]], create_shortcuts: bool):
        self.fix_all_btn.configure(state="disabled")
        self.progress_bar.set(0)

        def _prog(curr, tot, msg):
            ratio = curr / max(1, tot)
            self.after(0, lambda: self._update_progress(ratio, msg))

        def _worker():
            res = self.service.fix_items(items, create_shortcuts=create_shortcuts, progress_callback=_prog)
            self.after(0, lambda: self._on_fix_completed(res))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, ratio: float, msg: str):
        self.progress_bar.set(ratio)
        self.status_var.set(msg)

    def _on_fix_completed(self, res: Dict[str, Any]):
        self.fix_all_btn.configure(state="normal")
        self.progress_bar.set(1.0)
        downloaded = res.get("downloaded", 0)
        sc_count = res.get("shortcuts_created", 0)

        msg = self._t("status_fix_done", downloaded=downloaded)
        if sc_count > 0:
            msg += self._t("shortcuts_updated_suffix", count=sc_count)
        msg += "。"

        self.status_var.set(msg)
        messagebox.showinfo(self._t("complete"), msg)
        self.start_scan_thread()

    def _on_refresh_cache_clicked(self):
        """手动刷新 Windows 桌面图标缓存"""
        IconCacheRefresher.refresh_quick()
        messagebox.showinfo(self._t("success"), self._t("cache_refreshed"))

    def _on_choose_path(self):
        folder = filedialog.askdirectory(title="选择 Steam 安装根目录")
        if folder:
            self.service = SteamIconFixerService(folder)
            self.start_scan_thread()

    def _toggle_theme(self):
        mode = ctk.get_appearance_mode()
        new_mode = "Light" if mode == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
