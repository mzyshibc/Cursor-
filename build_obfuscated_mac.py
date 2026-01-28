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

def get_add_data_paths(project_root: Path):
    """获取需要打包的数据文件路径"""
    add_data_args = []
    
    # 数据库文件 - 只打包一个，但确保存在
    primary_db = project_root / 'data' / 'accounts.db'
    secondary_db = project_root / 'src' / 'data' / 'accounts.db'
    
    # 注意：在 macOS 上，PyInstaller 使用分号 (;) 作为分隔符
    # 但系统路径分隔符是冒号 (:)，所以这里容易混淆
    
    # 优先使用主位置的数据库
    if primary_db.exists():
        # macOS 上正确的语法是分号分隔
        add_data_args.append(f'--add-data={primary_db}:data')
        print(f"✅ 包含数据库文件 (主位置): {primary_db}")
    elif secondary_db.exists():
        add_data_args.append(f'--add-data={secondary_db}:data')
        print(f"✅ 包含数据库文件 (备用位置): {secondary_db}")
    else:
        print("⚠️ 未找到数据库文件，但会继续构建")
    
    # 其他资源文件
    resources = [
        ('src/assets', 'src/assets'),
        ('src/utils/public_key.pem', 'src/utils'),
    ]
    
    for src, dest in resources:
        src_path = project_root / src
        if src_path.exists():
            if src_path.is_dir():
                # 目录：使用分号分隔
                add_data_args.append(f'--add-data={src_path}:{dest}')
            else:
                # 文件：使用分号分隔
                add_data_args.append(f'--add-data={src_path}:{dest}')
            print(f"✅ 包含资源: {src} -> {dest}")
    
    return add_data_args

def main():
    if sys.platform != "darwin":
        print("❌ 仅在 macOS 上运行此脚本")
        sys.exit(1)
    
    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"
    obfuscated_src = project_root / "obfuscated_src"
    src_dir = project_root / "src"
    
    # 检查数据库文件
    primary_db = project_root / 'data' / 'accounts.db'
    secondary_db = project_root / 'src' / 'data' / 'accounts.db'
    
    if not primary_db.exists() and not secondary_db.exists():
        print("⚠️ 未找到数据库文件，创建空的数据库...")
        primary_db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(primary_db)
        conn.close()
        print(f"✅ 已创建空数据库: {primary_db}")
    
    entry = obfuscated_src / "main.py" if (obfuscated_src / "main.py").exists() else src_dir / "main.py"
    entry_dir = entry.parent
    minimal_mode = not ((entry_dir / "ui").exists() or (entry_dir / "core").exists())
    name = "CursorProManager"
    icon_icns = project_root / "src" / "assets" / "icon.icns"
    base_paths = obfuscated_src if entry.parent == obfuscated_src else src_dir
    # 运行时别名 hook（解决 src.utils.logger 与 utils.logger 双前缀导入）
    hook_path = project_root / "rth_alias_logger.py"
    try:
        hook_path.write_text(
            "import sys\n"
            "mod = None\n"
            "try:\n"
            "    import src.utils.logger as mod\n"
            "except Exception:\n"
            "    try:\n"
            "        import utils.logger as mod\n"
            "    except Exception:\n"
            "        mod = None\n"
            "if mod:\n"
            "    sys.modules['src.utils.logger'] = mod\n"
            "    sys.modules['utils.logger'] = mod\n"
        , encoding="utf-8")
    except Exception:
        pass
    
    # 构建 PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--name={name}",
        f"--paths={base_paths}",
        f"--runtime-hook={hook_path}",
        "--osx-bundle-identifier=com.cursorvip.manager"
    ]
    # 额外补充搜索路径（同时包含 src 与 obfuscated_src）
    if src_dir.exists():
        cmd.append(f"--paths={src_dir}")
    if obfuscated_src.exists():
        cmd.append(f"--paths={obfuscated_src}")
    
    # 添加数据文件 - 使用分号分隔
    if primary_db.exists():
        cmd.append(f"--add-data={primary_db}:data")
        print(f"✅ 包含数据库文件: {primary_db}")
    elif secondary_db.exists():
        cmd.append(f"--add-data={secondary_db}:data")
        print(f"✅ 包含数据库文件: {secondary_db}")
    
    # 添加其他资源文件
    if (project_root / "src" / "assets").exists():
        cmd.append(f"--add-data={project_root / 'src' / 'assets'}:src/assets")
        print("✅ 包含资源: src/assets")
    
    if (project_root / "src" / "utils" / "public_key.pem").exists():
        cmd.append(f"--add-data={project_root / 'src' / 'utils' / 'public_key.pem'}:src/utils")
        print("✅ 包含资源: src/utils/public_key.pem")
    
    if minimal_mode:
        pass
    else:
        cmd.extend([
            "--hidden-import=PyQt6",
            "--hidden-import=requests",
            "--hidden-import=logging.handlers",
            "--hidden-import=logging.config",
            "--hidden-import=cryptography",
            "--hidden-import=cryptography.hazmat",
            "--hidden-import=cryptography.hazmat.backends",
            "--hidden-import=cryptography.hazmat.primitives",
            "--hidden-import=cryptography.hazmat.primitives.padding",
            "--hidden-import=cryptography.hazmat.primitives.serialization",
            "--hidden-import=cryptography.hazmat.primitives.hashes",
            "--hidden-import=cryptography.hazmat.primitives.ciphers",
            "--hidden-import=cryptography.hazmat.primitives.ciphers.modes",
            "--hidden-import=cryptography.hazmat.primitives.ciphers.algorithms",
            "--hidden-import=cryptography.hazmat.primitives.asymmetric",
            "--hidden-import=cryptography.hazmat.primitives.asymmetric.padding",
            "--hidden-import=jwt",
            "--hidden-import=psutil",
            "--hidden-import=imaplib",
            "--hidden-import=email",
            "--hidden-import=email.header",
            "--hidden-import=email.utils",
            "--hidden-import=uuid",
            "--hidden-import=DrissionPage",
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
            "--hidden-import=src.ui.about_widget",
            "--hidden-import=src.ui.settings_widget",
            "--hidden-import=src.ui.account_pool_widget",
            "--hidden-import=src.ui.email_config_widget",
            "--hidden-import=src.ui.registration_widget",
            "--hidden-import=src.ui.account_detail_dialog",
            "--hidden-import=src.ui.add_account_dialog",
            "--hidden-import=src.core.registration_engine",
            "--hidden-import=src.core.account_manager",
            "--hidden-import=src.core.auth_injector",
            "--hidden-import=src.core.backend_api",
            "--hidden-import=src.core.cursor_api",
            "--hidden-import=src.core.email_handler",
            "--hidden-import=src.core.legacy_email_handler",
            "--hidden-import=src.core.drission_modules",
            "--hidden-import=src.core.drission_modules.account_storage",
            "--hidden-import=src.core.drission_modules.auto_register",
            "--hidden-import=src.core.drission_modules.browser_manager",
            "--hidden-import=src.core.drission_modules.card_pool_manager",
            "--hidden-import=src.core.drission_modules.country_codes",
            "--hidden-import=src.core.drission_modules.cursor_switcher",
            "--hidden-import=src.core.drission_modules.deep_token_getter",
            "--hidden-import=src.core.drission_modules.email_verification",
            "--hidden-import=src.core.drission_modules.machine_id_generator",
            "--hidden-import=src.core.drission_modules.payment_handler",
            "--hidden-import=src.core.drission_modules.phone_handler",
            "--hidden-import=src.core.drission_modules.registration_steps",
            "--hidden-import=src.core.drission_modules.token_handler",
            "--hidden-import=src.core.drission_modules.turnstile_handler",
            "--hidden-import=src.core.drission_modules.us_address_generator",
            "--hidden-import=src.utils.crypto",
            "--hidden-import=src.utils.app_paths",
            "--hidden-import=src.utils.version_checker",
            "--hidden-import=src.utils.license_monitor",
            "--hidden-import=src.utils.logger",
            "--hidden-import=utils.logger",
        ])
    
    if icon_icns.exists():
        cmd.append(f"--icon={icon_icns}")
    
    cmd.append(str(entry))
    
    print("🔨 正在为 macOS 构建...")
    print("执行命令:", " ".join(cmd))
    
    r = subprocess.run(cmd, cwd=project_root)
    if r.returncode != 0:
        print("❌ 构建失败")
        sys.exit(1)
    
    app_path = dist_dir / f"{name}.app"
    if not app_path.exists():
        print("❌ 未找到 .app 产物")
        sys.exit(1)
    # 解除隔离标记，避免“已损坏”提示
    try:
        subprocess.run(["xattr", "-cr", str(app_path)], check=False)
        print("✅ 已清理 quarantine 属性")
    except Exception:
        print("⚠️ 清理 quarantine 失败，继续后续打包")
    
    # 验证数据库是否被打包 - 更详细的检查
    print("\n🔍 验证打包的文件...")
    
    # 检查多个可能的位置
    possible_locations = [
        app_path / "Contents" / "MacOS" / "data" / "accounts.db",
        app_path / "Contents" / "Resources" / "data" / "accounts.db",
        app_path / "Contents" / "MacOS" / "accounts.db",  # 可能在根目录
    ]
    
    found = False
    for location in possible_locations:
        if location.exists():
            print(f"✅ 数据库已成功打包到应用中: {location}")
            found = True
            break
    
    if not found:
        print("⚠️ 数据库文件未找到，搜索整个应用...")
        # 搜索整个应用包
        for root, dirs, files in os.walk(app_path):
            for file in files:
                if file == "accounts.db":
                    db_path = Path(root) / file
                    print(f"✅ 在非标准位置找到数据库: {db_path}")
                    found = True
                    break
            if found:
                break
        
        if not found:
            print("❌ 数据库中未找到，检查应用内结构:")
            # 列出应用包的结构
            for root, dirs, files in os.walk(app_path / "Contents"):
                level = root.replace(str(app_path / "Contents"), '').count(os.sep)
                indent = ' ' * 2 * level
                print(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # 只显示前10个文件
                    print(f'{subindent}{file}')
                if len(files) > 10:
                    print(f'{subindent}... 还有 {len(files)-10} 个文件')
    
    # 检查 _MEIPASS 中的文件
    print("\n🔍 检查 _MEIPASS 目录内容:")
    # 查找 _MEIPASS 目录（通常是 Contents/MacOS 下的某个目录）
    macos_dir = app_path / "Contents" / "MacOS"
    if macos_dir.exists():
        for item in macos_dir.iterdir():
            if item.is_dir() and item.name.startswith("_MEI"):
                print(f"✅ 找到 _MEIPASS 目录: {item.name}")
                # 列出其中的文件和目录
                for subitem in item.iterdir():
                    if subitem.is_dir():
                        print(f"  📁 {subitem.name}/")
                        if subitem.name == "data":
                            print(f"    ✅ 找到 data 目录")
                            db_files = list(subitem.glob("*.db"))
                            for db in db_files:
                                print(f"    📄 {db.name}")
                    else:
                        print(f"  📄 {subitem.name}")
    
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
