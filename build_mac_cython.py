import os
import sys
from pathlib import Path
from setuptools import setup, Extension
from Cython.Build import cythonize
import shutil

def build_modules(src_dir, project_root):
    target_dirs = ['core', 'utils', 'ui']
    extensions = []
    
    # 扫描指定的子目录
    for target_dir in target_dirs:
        base_path = Path(src_dir) / target_dir
        if not base_path.exists():
            continue
            
        for root, dirs, files in os.walk(base_path):
            for file in files:
                # 编译所有非 __init__.py 的 python 文件
                if file.endswith('.py') and file != '__init__.py':
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(src_dir)
                    module_name = '.'.join(rel_path.with_suffix('').parts)
                    
                    # 排除某些不需要编译的模块（如果有）
                    if 'turnstilePatch' in str(rel_path):
                        continue
                        
                    print(f"[+] 添加编译目标: {module_name}")
                    extensions.append(Extension(
                        name=module_name,
                        sources=[str(file_path)],
                    # macOS/Linux 使用 -O2 优化参数，并忽略弃用警告
                    extra_compile_args=["-O2", "-Wno-deprecated-declarations"],

                    ))

    if not extensions:
        print("[WARN] 未找到需要编译的模块")
        return

    setup_args = {
        'name': 'CursorProManager_Core',
        'ext_modules': cythonize(
            extensions,
            compiler_directives={'language_level': "3", 'always_allow_keywords': True},
            quiet=True
        ),
        'script_args': ['build_ext']
    }

    print("[INFO] 开始 Cython 编译 (macOS)...")
    original_cwd = os.getcwd()
    os.chdir(src_dir)
    try:
        if str(src_dir) not in sys.path:
            sys.path.append(str(src_dir))
        setup(**setup_args)
    except SystemExit as e:
        if str(e) != '0':
            raise
    finally:
        os.chdir(original_cwd)

    # 编译产物处理
    build_lib = src_dir / 'build'
    copied = 0
    if build_lib.exists():
        for root, dirs, files in os.walk(build_lib):
            for f in files:
                # macOS 上的二进制后缀是 .so
                if f.endswith('.so'):
                    src_file = Path(root) / f
                    rel = Path(root).relative_to(build_lib)
                    parts = list(rel.parts)
                    # 跳过 lib.macosx-xxx 等前缀目录
                    if parts and parts[0].startswith('lib.'):
                        parts = parts[1:]
                    
                    dest_dir = src_dir / Path(*parts)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_dir / f)
                    print(f"✓ 复制二进制文件: {f} -> {dest_dir}")
                    copied += 1
                    
    print(f"[OK] 编译完成，共生成 {copied} 个二进制模块")
    
    # 清理中间文件
    try:
        shutil.rmtree(build_lib, ignore_errors=True)
        # 清理生成的 .c 源文件
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith('.c'):
                    (Path(root) / f).unlink()
    except Exception:
        pass
    
if __name__ == "__main__":
    project_root = Path(__file__).parent.absolute()
    target = Path(sys.argv[1]).absolute() if len(sys.argv) > 1 else (project_root / "src")
    build_modules(target, project_root)
