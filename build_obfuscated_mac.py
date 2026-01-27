import os
import sys
import shutil
import subprocess
from pathlib import Path

def find_plugins_dir(app_path: Path) -> Path | None:
    candidates = [
        app_path / "Contents" / "MacOS" / "PyQt6" / "Qt6" / "plugins",
        app_path / "Contents" / "MacOS" / "Qt6" / "plugins",
        app_path / "Contents" / "Resources" / "PyQt6" / "Qt6" / "plugins",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def prune_qt_plugins(app_path: Path):
    plugins_dir = find_plugins_dir(app_path)
    if not plugins_dir:
        print("⚠️ 未找到 Qt 插件目录，跳过精简")
        return
    img_dir = plugins_dir / "imageformats"
    tls_dir = plugins_dir / "tls"
    icon_dir = plugins_dir / "iconengines"
    plat_dir = plugins_dir / "platforms"
    trans_dir = plugins_dir.parent.parent / "translations"
    if trans_dir.exists():
        shutil.rmtree(trans_dir, ignore_errors=True)
    if plat_dir.exists():
        keep = {"qcocoa.dylib", "libqcocoa.dylib"}
        for p in plat_dir.iterdir():
            if p.is_file() and p.name.lower() not in keep:
                try: p.unlink()
                except: pass
    if img_dir.exists():
        keep = {"qpng.dylib","libqpng.dylib","qjpeg.dylib","libqjpeg.dylib","qsvg.dylib","libqsvg.dylib"}
        for p in img_dir.iterdir():
            if p.is_file() and p.name.lower() not in keep:
                try: p.unlink()
                except: pass
    if tls_dir.exists():
        keep = {"qsecuretransport.dylib","libqsecuretransport.dylib","qopensslbackend.dylib","libqopensslbackend.dylib"}
        for p in tls_dir.iterdir():
            if p.is_file() and p.name.lower() not in keep:
                try: p.unlink()
                except: pass
    if icon_dir.exists():
        keep = {"qsvgicon.dylib","libqsvgicon.dylib"}
        for p in icon_dir.iterdir():
            if p.is_file() and p.name.lower() not in keep:
                try: p.unlink()
                except: pass
    print("✅ 已精简 Qt 插件")

def main():
    if sys.platform != "darwin":
        print("❌ 仅在 macOS 上运行此脚本")
        sys.exit(1)
    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"
    obfuscated_src = project_root / "obfuscated_src"
    src_dir = project_root / "src"
    entry = obfuscated_src / "main.py" if (obfuscated_src / "main.py").exists() else src_dir / "main.py"
    name = "CursorProManager"
    icon_icns = project_root / "src" / "assets" / "icon.icns"
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--name={name}",
        f"--paths={(obfuscated_src if entry.parent == obfuscated_src else src_dir)}",
        "--hidden-import=PyQt6",
        "--hidden-import=requests",
        "--hidden-import=ui.about_widget",
        "--hidden-import=ui.settings_widget",
        "--hidden-import=ui.account_pool_widget",
        "--hidden-import=ui.email_config_widget",
        "--hidden-import=ui.registration_widget",
        "--hidden-import=ui.account_detail_dialog",
        "--hidden-import=ui.add_account_dialog",
        "--hidden-import=core.registration_engine",
        "--hidden-import=core.account_manager",
        "--hidden-import=core.auth_injector",
        "--hidden-import=core.backend_api",
        "--hidden-import=core.cursor_api",
        "--hidden-import=core.email_handler",
        "--hidden-import=core.legacy_email_handler",
        "--hidden-import=core.drission_modules",
        "--hidden-import=core.drission_modules.account_storage",
        "--hidden-import=core.drission_modules.auto_register",
        "--hidden-import=core.drission_modules.browser_manager",
        "--hidden-import=core.drission_modules.card_pool_manager",
        "--hidden-import=core.drission_modules.country_codes",
        "--hidden-import=core.drission_modules.cursor_switcher",
        "--hidden-import=core.drission_modules.deep_token_getter",
        "--hidden-import=core.drission_modules.email_verification",
        "--hidden-import=core.drission_modules.machine_id_generator",
        "--hidden-import=core.drission_modules.payment_handler",
        "--hidden-import=core.drission_modules.phone_handler",
        "--hidden-import=core.drission_modules.registration_steps",
        "--hidden-import=core.drission_modules.token_handler",
        "--hidden-import=core.drission_modules.turnstile_handler",
        "--hidden-import=core.drission_modules.us_address_generator",
        "--hidden-import=utils.crypto",
        "--hidden-import=utils.app_paths",
        "--hidden-import=utils.version_checker",
        "--hidden-import=utils.license_monitor",
        "--hidden-import=PyQt6.QtWebSockets",
        "--osx-bundle-identifier=com.cursorvip.manager",
    ]
    if icon_icns.exists():
        cmd.append(f"--icon={icon_icns}")
    cmd.append(str(entry))
    print("🔨 正在为 macOS 构建...")
    r = subprocess.run(cmd, cwd=project_root)
    if r.returncode != 0:
        print("❌ 构建失败")
        sys.exit(1)
    app_path = dist_dir / f"{name}.app"
    if not app_path.exists():
        print("❌ 未找到 .app 产物")
        sys.exit(1)
    prune_qt_plugins(app_path)
    zip_path = dist_dir / f"{name}-mac.zip"
    if shutil.which("ditto"):
        subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(app_path),str(zip_path)], check=False)
        print(f"📦 已生成 ZIP: {zip_path}")
    else:
        shutil.make_archive(str(zip_path).removesuffix(".zip"), "zip", app_path.parent, app_path.name)
        print(f"📦 已生成 ZIP: {zip_path}")
    print("🎉 macOS 构建完成")

if __name__ == "__main__":
    main()
