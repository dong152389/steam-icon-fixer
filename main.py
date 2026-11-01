import os
import sys
import argparse

# 确保 Windows 控制台支持 UTF-8 打印包含特殊字符（如 ™、® 等）的游戏名
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保项目根目录在 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.manager import SteamIconFixerService
from core.cache import IconCacheRefresher

def run_cli_mode(args):
    print("=" * 60)
    print("  Steam 图标自动修复大师 (Steam Icon Fixer) - CLI 模式")
    print("=" * 60)

    service = SteamIconFixerService(steam_path=args.steam_path)
    print(f"[*] 检测 Steam 目录: {service.steam_path or '未找到'}")

    if args.refresh_cache:
        print("[*] 正在刷新 Windows 桌面图标缓存...")
        if args.deep_cache:
            ok, msg = IconCacheRefresher.rebuild_cache_deep()
            print(f"[*] {msg}")
        else:
            IconCacheRefresher.refresh_quick()
            print("[+] 已发送 Shell 刷新通知！")
        return 0

    print("[*] 正在扫描游戏库与桌面快捷方式...")
    data = service.scan_environment()
    if not data.get("valid"):
        print(f"[-] 错误: {data.get('error')}")
        return 1

    stats = data.get("stats", {})
    items = data.get("items", [])
    print(f"[+] 扫描完成: 已安装游戏 {stats.get('installed_count')} 款 | 缺失图标 {stats.get('missing_icons')} 款")

    missing_items = [it for it in items if not it["icon_exists"]]
    if not missing_items and not args.create_shortcuts:
        print("[+] 所有游戏图标均已存在，无需修复！")
        return 0

    print(f"[*] 开始修复 {len(missing_items)} 款游戏的图标...")
    def _prog(curr, tot, msg):
        print(f"  -> {msg}")

    res = service.fix_items(
        items=missing_items if not args.all else items,
        create_shortcuts=args.create_shortcuts,
        progress_callback=_prog
    )

    print("-" * 60)
    print(f"[+] 修复结果: 成功下载 {res.get('downloaded')} 个图标, 失败 {res.get('failed')} 个")
    if args.create_shortcuts:
        print(f"[+] 桌面快捷方式生成/更新: {res.get('shortcuts_created')} 个")
    print("[+] Windows 桌面图标缓存已同步刷新！")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Steam 图标自动修复大师")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式运行")
    parser.add_argument("--auto-fix", action="store_true", help="自动修复所有缺失图标并退出")
    parser.add_argument("--all", action="store_true", help="强制重新下载全部图标")
    parser.add_argument("--create-shortcuts", action="store_true", help="为已安装游戏自动创建缺失的桌面快捷方式")
    parser.add_argument("--refresh-cache", action="store_true", help="仅刷新 Windows 桌面图标缓存")
    parser.add_argument("--deep-cache", action="store_true", help="深度强制重建图标缓存 (会重启 explorer)")
    parser.add_argument("--steam-path", type=str, default=None, help="手动指定 Steam 安装路径")

    args = parser.parse_args()

    # 如果有特定命令行标志，走 CLI 模式
    if args.cli or args.auto_fix or args.refresh_cache:
        sys.exit(run_cli_mode(args))

    # 默认启动 GUI 模式
    try:
        from app.gui import SteamIconFixerApp
        app = SteamIconFixerApp()
        app.mainloop()
    except Exception as e:
        print(f"启动图形界面失败: {e}，回退到命令行模式")
        sys.exit(run_cli_mode(args))

if __name__ == "__main__":
    main()
