import os
import sys
import shutil
import subprocess
from pathlib import Path
import re
import argparse
import zipfile
from typing import Optional, List

def print_step(msg: str):
    print(f"\n{'='*20} {msg} {'='*20}")

def ensure_db(project_root: Path) -> Optional[Path]:
    primary = project_root / 'data' / 'accounts.db'
    if primary.exists():
        print(f"✅ 找到数据库文件: {primary}")
        return primary
    
    secondary = project_root / 'src' / 'data' / 'accounts.db'
    if secondary.exists():
        print(f"✅ 找到数据库文件 (备用): {secondary}")
        return secondary
        
    print(f"⚠️ 未找到数据库文件，尝试初始化空数据库")
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        sqlite3.connect(primary).close()
        return primary
    except Exception as e:
        print(f"❌ 无法创建数据库: {e}")
        return None

def add_data_args_mac(project_root: Path) -> List[str]:
    args = []
    db = ensure_db(project_root)
    if db:
        args.append(f"--add-data={db}:data")
    
    resources = [
        ('src/assets', 'src/assets'),
        ('src/utils/public_key.pem', 'src/utils')
    ]
    for src, dest in resources:
        p = project_root / src
        if p.exists():
            args.append(f"--add-data={p}:{dest}")
            print(f"📦 添加资源: {src} -> {dest}")
    return args

def collect_hidden_imports(src_dir: Path) -> List[str]:
    print("🔍 扫描依赖模块与隐藏导入...")
    hidden = [
        "PyQt6", "requests", "cryptography", "jwt", "psutil", "uuid", 
        "DrissionPage", "sqlite3", "lxml", "ui", "core", "utils",
        "logging.handlers", "json", "re", "datetime", "platform",
        "ctypes", "subprocess", "shutil", "glob", "importlib",
        "importlib.util", "importlib.machinery", "tempfile",
        "email.mime.text", "email.mime.multipart", "hmac", "hashlib",
        "base64", "ssl", "pickle", "copy", "threading", "queue", "time",
        "email.utils", "bisect", "ast", "imaplib", "poplib", "smtplib", "email", "email.mime",
        "PyQt6.QtWebSockets", "PyQt6.QtNetwork", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
        "cryptography.hazmat.primitives.padding",
        "cryptography.hazmat.primitives.serialization",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.primitives.asymmetric.padding",
        "cryptography.hazmat.primitives.ciphers",
        "cryptography.hazmat.primitives.ciphers.algorithms",
        "cryptography.hazmat.primitives.ciphers.modes",
        "cryptography.hazmat.backends.default_backend",
        "cryptography.hazmat.backends"
    ]
    
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if f.endswith('.so'):
                try:
                    rel_path = Path(root).relative_to(src_dir)
                    mod_name = f.split('.')[0]
                    full_mod_name = '.'.join(list(rel_path.parts) + [mod_name])
                    hidden.append(full_mod_name)
                except:
                    pass
                
    return list(set(hidden))

def perform_activation(project_root: Path, license_key: str):
    """在构建环境下执行自动化激活"""
    print_step(f"执行自动化激活测试: {license_key}")
    src_dir = project_root / "src"
    if not src_dir.exists():
        print("❌ 激活失败：未找到源码目录")
        return

    # 将 src 添加到路径以加载模块
    sys.path.insert(0, str(src_dir))
    
    try:
        from utils.config import ConfigManager
        from utils.license_validator import LicenseValidator
        
        config_manager = ConfigManager()
        validator = LicenseValidator(config_manager)
        
        print(f"🚀 正在调用 API 激活授权码...")
        success, result = validator.activate_license(license_key)
        
        if success:
            print(f"✅ 激活成功！过期时间: {result.get('expires_at')}")
            print(f"📂 许可证已保存至: {validator.license_file}")
        else:
            print(f"❌ 激活失败: {result.get('message', '未知错误')}")
    except Exception as e:
        print(f"❌ 激活过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

def cleanup_activation(project_root: Path):
    """清除构建环境下的激活信息，确保产物纯净"""
    print_step("执行激活信息清理")
    try:
        from utils.app_paths import get_app_data_dir
        config_dir = get_app_data_dir()
        license_file = config_dir / 'license.dat'
        if license_file.exists():
            license_file.unlink()
            print(f"🗑️ 已删除激活文件: {license_file}")
        
        # 同时检查当前目录下的 data/license.dat (以防万一)
        alt_license = project_root / 'data' / 'license.dat'
        if alt_license.exists():
            alt_license.unlink()
            print(f"🗑️ 已删除备用激活文件: {alt_license}")
            
    except Exception as e:
        print(f"⚠️ 清理激活信息时发生错误: {e}")

def main():
    parser = argparse.ArgumentParser(description="M1 Obfuscated Build Script")
    parser.add_argument("--activate", help="在打包前执行授权码激活测试")
    parser.add_argument("--cleanup", action="store_true", help="清理激活信息")
    args, unknown = parser.parse_known_args()

    # 如果只是清理请求
    if args.cleanup:
        # 智能定位项目根目录
        current_script_dir = Path(__file__).resolve().parent
        if (current_script_dir / "src").exists() or (current_script_dir / "src.zip").exists():
            project_root = current_script_dir
        else:
            project_root = current_script_dir.parent
        sys.path.insert(0, str(project_root / "src"))
        cleanup_activation(project_root)
        return

    print_step("启动 M1 (Apple Silicon) 原生构建流程")
    
    # 智能定位项目根目录
    current_script_dir = Path(__file__).resolve().parent
    if (current_script_dir / "src").exists() or (current_script_dir / "src.zip").exists():
        project_root = current_script_dir
    else:
        project_root = current_script_dir.parent
    
    os.chdir(project_root)
    dist_dir = project_root / "dist"
    obf_dir = project_root / "obfuscated_src_mac"
    src_dir = project_root / "src"
    src_zip = project_root / "src.zip"
    
    print(f"📍 项目根目录: {project_root}")
    print(f"📍 源码目录: {src_dir}")

    # 自动解压 src.zip
    if not src_dir.exists() and src_zip.exists():
        print_step("检测到 src.zip，正在解压源码...")
        try:
            with zipfile.ZipFile(src_zip, 'r') as zip_ref:
                zip_ref.extractall(project_root)
            print("✅ 源码解压完成")
        except Exception as e:
            print(f"❌ 解压失败: {e}")
            sys.exit(1)

    if not src_dir.exists():
        print(f"❌ 严重错误：未找到源码目录 {src_dir}")
        print(f"当前目录内容: {os.listdir(project_root)}")
        sys.exit(1)

    # 激活测试
    if args.activate:
        perform_activation(project_root, args.activate)

    date_str = subprocess.check_output(['date', '+%Y%m%d_%H%M%S']).decode().strip()
    name = f"CursorProManager_M1_{date_str}"

    print_step("1. 准备混淆工作目录")
    if obf_dir.exists():
        shutil.rmtree(obf_dir, ignore_errors=True)
    obf_dir.mkdir(parents=True, exist_ok=True)
    
    obf_src_dir = obf_dir / "src"
    print(f"📂 正在同步源码到: {obf_src_dir}")
    shutil.copytree(src_dir, obf_src_dir)
    
    print_step("2. 优化导入逻辑 (Regex Fix)")
    fixed_count = 0
    for root, dirs, files in os.walk(obf_src_dir):
        for f in files:
            if f.endswith('.py'):
                file_path = Path(root) / f
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    
                    new_content = re.sub(r'from src\.', 'from ', content)
                    new_content = re.sub(r'import src\.', 'import ', new_content)
                    
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as file:
                            file.write(new_content)
                        fixed_count += 1
                except:
                    pass
    print(f"✨ 已处理 {fixed_count} 个文件的导入语句")

    print_step("3. 启动 Cython 二进制编译 (arm64)")
    cython_script = project_root / "build_mac_cython.py"
    if not cython_script.exists():
        print(f"⚠️ 找不到编译脚本: {cython_script}，尝试从源码目录寻找...")
        cython_script = src_dir / "build_mac_cython.py"
        
    if not cython_script.exists():
        print("❌ 错误：缺少 build_mac_cython.py")
        sys.exit(1)
        
    r = subprocess.run([sys.executable, str(cython_script), str(obf_src_dir)], cwd=project_root)
    if r.returncode != 0:
        print("❌ Cython 编译失败")
        sys.exit(1)
    
    print_step("4. 源码移除与加固")
    removed = 0
    for root, dirs, files in os.walk(obf_src_dir):
        for f in files:
            if f.endswith(".py") and f != "main.py" and f != "__init__.py":
                (Path(root) / f).unlink()
                removed += 1
    print(f"🛡️ 已移除 {removed} 个 Python 源码文件")

    print_step("5. 执行 PyInstaller 原生打包")
    entry = obf_src_dir / "main.py"
    cmd = [
        "python3", "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--name={name}",
        f"--paths={str(obf_src_dir)}",
        "--clean"
    ]

    cmd.extend(add_data_args_mac(project_root))
    
    hidden = collect_hidden_imports(obf_src_dir)
    for h in hidden:
        cmd.append(f"--hidden-import={h}")

    cmd.append(str(entry))

    print(f"🚀 执行打包指令...")
    subprocess.run(cmd, cwd=project_root)

    print_step("构建成功!")

if __name__ == "__main__":
    main()
