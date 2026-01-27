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

def ensure_database_exists(project_root: Path):
    """确保数据库文件存在，支持多个位置"""
    db_locations = [
        project_root / 'data' / 'accounts.db',  # 主位置
        project_root / 'src' / 'data' / 'accounts.db',  # 备用位置
    ]
    
    # 检查是否有现有的数据库文件
    existing_db = None
    for db_path in db_locations:
        if db_path.exists():
            print(f"✅ 找到数据库文件: {db_path}")
            existing_db = db_path
            break
    
    # 如果没有数据库文件，创建空的
    if existing_db is None:
        print("⚠️ 未找到数据库文件，将在两个位置都创建...")
        
        for db_path in db_locations:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            import sqlite3
            conn = sqlite3.connect(db_path)
            
            # 创建基础表结构
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            );
            
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            
            INSERT OR IGNORE INTO settings (key, value) VALUES 
                ('version', '1.0.0'),
                ('database_version', '1');
            """)
            conn.commit()
            conn.close()
            print(f"✅ 已创建数据库: {db_path}")
    else:
        # 确保另一个位置也有数据库文件（复制）
        for db_path in db_locations:
            if db_path != existing_db and not db_path.exists():
                db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(existing_db, db_path)
                print(f"✅ 复制数据库到: {db_path}")
    
    return existing_db or db_locations[0]

def get_add_data_paths(project_root: Path):
    """获取需要打包的数据文件路径"""
    add_data_args = []
    
    # 数据库文件 - 只打包一个，但确保存在
    primary_db = project_root / 'data' / 'accounts.db'
    secondary_db = project_root / 'src' / 'data' / 'accounts.db'
    
    # 优先使用主位置的数据库
    if primary_db.exists():
        add_data_args.append(f'--add-data={primary_db}:data')
        print(f"✅ 包含数据库文件 (主位置): {primary_db}")
    elif secondary_db.exists():
        add_data_args.append(f'--add-data={secondary_db}:data')
        print(f"✅ 包含数据库文件 (备用位置): {secondary_db}")
    else:
        # 理论上不会走到这里，因为 ensure_database_exists 已确保
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
                add_data_args.append(f'--add-data={src_path}:{dest}')
            else:
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
    
    # 确保数据库文件存在（在两个位置）
    ensure_database_exists(project_root)
    
    entry = obfuscated_src / "main.py" if (obfuscated_src / "main.py").exists() else src_dir / "main.py"
    entry_dir = entry.parent
    minimal_mode = not ((entry_dir / "ui").exists() or (entry_dir / "core").exists())
    name = "CursorProManager"
    icon_icns = project_root / "src" / "assets" / "icon.icns"
    base_paths = obfuscated_src if entry.parent == obfuscated_src else src_dir
    
    # 构建 PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--name={name}",
        f"--paths={base_paths}",
        "--osx-bundle-identifier=com.cursorvip.manager"
    ]
    
    # 添加数据文件
    add_data_args = get_add_data_paths(project_root)
    cmd.extend(add_data_args)
    
    if minimal_mode:
        pass
    else:
        cmd.extend([
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
    
    # 验证数据库是否被打包
    print("\n🔍 验证打包的文件...")
    if (app_path / "Contents" / "MacOS" / "data" / "accounts.db").exists():
        print("✅ 数据库已成功打包到应用中")
    else:
        print("⚠️ 数据库文件未找到，检查应用内资源")
        macos_dir = app_path / "Contents" / "MacOS"
        if macos_dir.exists():
            print("应用内文件结构:")
            for root, dirs, files in os.walk(macos_dir):
                level = root.replace(str(macos_dir), '').count(os.sep)
                indent = ' ' * 2 * level
                print(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    print(f'{subindent}{file}')
    
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
