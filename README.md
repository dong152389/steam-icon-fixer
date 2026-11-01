# 🎮 Steam 图标自动修复大师 (Steam Icon Fixer)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat&logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6.svg?style=flat&logo=windows&logoColor=white" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/Arch-x64%20|%20x86%20|%20ARM64-orange.svg?style=flat" alt="Arch x64 x86 ARM64">
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-blue.svg?style=flat" alt="CustomTkinter">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat" alt="License MIT">
</p>

> 彻底解决重装系统或重装 Steam 后，游戏桌面快捷方式变成**空白白图标**的顽疾！
> 告别繁琐的手动打开 SteamDB 逐个搜索下载 Client Icon。
> 一键**全自动扫描多盘符 Steam 游戏库**、**毫秒级本地二进制解析 Client Icon Hash**、**官方原生 CDN 极速下载**、**实时图标预览**与**通知 Windows 刷新桌面图标缓存**！

---

## 🌟 核心痛点与解决背景

### 为什么会出现桌面白图标？
1. **重装系统或重装 Steam**：
   桌面上的 Steam 快捷方式本质是 INI 格式的 `.url` 文件（例如 `黑神话：悟空.url`），内部结构如下：
   ```ini
   [{000214A0-0000-0000-C000-000000000046}]
   Prop3=19,0
   [InternetShortcut]
   URL=steam://rungameid/2358720
   IconFile=C:\Program Files (x86)\Steam\steam\games\0121f85746c30090f72e2ba7eb5528fdfffa70b6.ico
   ```
2. 重装系统后，Steam 根目录下的 `\steam\games\` 文件夹会被清空或重置，导致 `IconFile` 指向的 `<hash>.ico` 不复存在。
3. 即使把原有 D盘、E盘的游戏库重新添加回 Steam，Steam 也**不会主动下载**这些游戏的桌面图标。
4. **过去极其痛苦的手动解决方式**：
   玩家必须翻墙打开 SteamDB 网站（经常被 Cloudflare 人机验证拦截），逐个搜索每个游戏的 AppID，手动下载 `clienticon` 并重命名为 40 位哈希保存到 Steam 文件夹，步骤极其繁琐耗时！

### 本工具如何完美解决？
- ⚡ **毫秒级离线二进制解析**：直接解析 Steam 现代 `appinfo.vdf`（支持 v28/v29 64位 String Table 架构），0.1 秒内精准提取库内所有游戏的 AppID 与 Client Icon 40位哈希，无需联网爬虫！
- 🚀 **Steam 官方最新 CDN 直连**：优先从 Fastly / Akamai / Cloudflare 的全新 `community_assets` 官方源拉取 100% 原版 256×256 超清图标，无需登录、无需 API Key。
- 🛡️ **本地三重兜底提取**：若 CDN 出现极罕见 404，自动调用 Windows 原生 GDI API 从本地游戏主 `.exe` 中无损提取 256×256 图标，或从 Steam 缓存转换。
- 🖥️ **全盘符游戏库自动检测**：自动遍历注册表与 `libraryfolders.vdf`，无论你的游戏在 C盘、D盘、E盘还是外置硬盘，统统全自动感知。
- 🎯 **100% 还原 Steam 快捷方式命名规范**：提取官方 `name_localized` 中文名称，还原 Steam 文件名合法化规则（如 `Palworld  幻兽帕鲁.url`），且就地更新桌面快捷方式，绝不生成多余冗余文件。
- 🔄 **Windows Shell 即时无感刷新**：调用 Windows 核心 API（`SHChangeNotify`），修复完成立即通知资源管理器刷新，无需重启电脑或重启 Explorer！

---

## ✨ 功能特性

- 🎨 **现代暗黑/明亮高颜值 GUI**：基于 CustomTkinter 设计，界面纯净无缝隙，视觉舒适度极高。
- 🖼️ **游戏 ICO 图标实时预览**：列表中每一款游戏均展示真实 26×26 高清图标缩略图，缺失状态一目了然。
- 🌐 **中英双语即时切换**：原生内置完整中英文国际化字典（i18n），支持随时一键切换。
- 📊 **实时统计仪表板**：清晰展示游戏总数、已有桌面快捷方式、正常图标数与待修复缺失数。
- 🔍 **智能搜索与多维筛选**：支持按中文名称、英文原名、AppID 实时模糊搜索，支持按“仅缺失图标”、“仅缺快捷方式”过滤。
- 🚀 **一键批量修复 & 单项修复**：多线程并发高速下载，支持同步补全缺失的桌面快捷方式。
- 💻 **无头 CLI / 批处理支持**：支持 `--cli` / `--auto-fix` 等命令行静默执行，极其适合装机 U 盘与自动化脚本。

---

## 📂 项目结构（源码与构建产物完全分离）

```
steam-icon-fixer/
│
├── app/                        # 桌面 GUI 交互层
│   └── gui.py                  # CustomTkinter 现代窗口、双语切换与列表图标渲染
│
├── core/                       # 核心业务与底层引擎
│   ├── detector.py             # Steam 安装路径注册表探测与多盘符游戏库扫描
│   ├── vdf_parser.py           # 二进制 appinfo.vdf 解析器 (支持 String Table 与多语言名称)
│   ├── downloader.py           # 官方最新 CDN 多线程并发下载与 ICO 校验
│   ├── extractor.py            # 本地 exe 64位无损高清图标提取与缓存转换
│   ├── shortcut.py             # 桌面 .url 快捷方式扫描、分析、就地更新与规范命名
│   ├── cache.py                # Windows Shell 图标缓存即时刷新 API
│   └── manager.py              # 全流程综合调度服务
│
├── tests/                      # 单元测试套件
│   └── test_core.py            # 解析器、探测器、下载器、快捷方式单元测试
│
├── main.py                     # 程序总入口（支持 GUI 模式与 CLI 命令行模式）
├── requirements.txt            # Python 运行时依赖列表
├── .gitignore                  # Git 忽略配置（彻底隔离构建产物与可执行文件）
├── LICENSE                     # MIT 开源许可证
└── README.md                   # 详细使用与技术文档
```

---

## 🚀 快速上手

### 方式 1：直接下载免安装 Release 可执行文件（推荐普通用户）

访问本项目的 [GitHub Releases 页面](https://github.com/dong152389/steam-icon-fixer/releases)，下载适合你系统架构的单文件 EXE 即可直接双击运行：
- **`SteamIconFixer-Windows-x64.exe`**：适用于绝大多数 64 位 Windows 10/11 电脑（主流首选）；
- **`SteamIconFixer-Windows-x86.exe`**：适用于 32 位 Windows 系统或老旧设备；
- **`SteamIconFixer-Windows-ARM64.exe`**：适用于 Surface Pro 等搭载高通骁龙处理器的 Windows on ARM 掌机/轻薄本。

### 方式 2：运行 Python 源码（开发者）

1. 克隆本项目：
   ```bash
   git clone https://github.com/dong152389/steam-icon-fixer.git
   cd steam-icon-fixer
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 启动图形化客户端：
   ```bash
   python main.py
   ```

### 方式 3：自行编译打包为单文件 EXE

若需打包为独立免 Python 环境的单文件可执行程序，可使用 PyInstaller：
```bash
pip install pyinstaller
python -m PyInstaller --name="SteamIconFixer" --onefile --noconsole --collect-all customtkinter --add-data "core;core" --add-data "app;app" main.py
```
打包完成后将在 `dist/` 目录下生成 `SteamIconFixer.exe`。

---

## 💻 命令行模式 (CLI)

适合装机脚本、批处理或无人值守场景：

```bash
# 自动扫描并静默修复所有缺失图标
python main.py --cli --auto-fix

# 自动修复缺失图标，同时为所有游戏补齐缺失的桌面快捷方式
python main.py --cli --auto-fix --create-shortcuts

# 仅通知 Windows Shell 刷新桌面图标缓存
python main.py --cli --refresh-cache

# 深度强制重建 Windows 图标缓存（重启 Explorer 进程）
python main.py --cli --refresh-cache --deep-cache

# 手动指定 Steam 安装根目录
python main.py --cli --steam-path "D:\Steam" --auto-fix
```

---

## 🧪 运行测试

本项目包含完整的单元测试，验证所有核心组件的功能正常：

```bash
python -m unittest discover tests
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。欢迎提交 Issue 与 Pull Request！
