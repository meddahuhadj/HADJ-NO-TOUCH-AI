"""
HADJ — No-Touch (حاج — تحكّم بدون لمس)
Automated Windows Standalone & Portable Distribution Builder
"""

import os
import sys
import shutil
import zipfile
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg: str):
    print(f"[HADJ BUILD] {msg}")


def ensure_icon():
    icon_path = os.path.join(PROJECT_ROOT, "resources", "app_icon.ico")
    png_source = os.path.join(PROJECT_ROOT, "web", "icons", "icon-512.png")
    if not os.path.exists(icon_path) and os.path.exists(png_source):
        try:
            from PIL import Image
            os.makedirs(os.path.dirname(icon_path), exist_ok=True)
            img = Image.open(png_source)
            img.save(
                icon_path,
                format="ICO",
                sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            )
            log("Generated resources/app_icon.ico")
        except Exception as e:
            log(f"Warning: Could not generate .ico: {e}")


def run_pyinstaller():
    spec_path = os.path.join(PROJECT_ROOT, "HADJ_NoTouch.spec")
    if not os.path.exists(spec_path):
        log(f"Error: Spec file not found at {spec_path}")
        return False

    log("Executing PyInstaller build...")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", spec_path]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return res.returncode == 0


def create_portable_zip():
    dist_dir = os.path.join(PROJECT_ROOT, "dist", "HADJ_NoTouch")
    if not os.path.exists(dist_dir):
        log(f"Error: Build folder not found at {dist_dir}")
        return None

    # Write quick start guide
    readme_path = os.path.join(dist_dir, "LISEZ-MOI_README_إقرأني.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            "=================================================================\n"
            "   HADJ — NO-TOUCH AI (حاج — تحكّم بالكمبيوتر بدون لمس)\n"
            "=================================================================\n\n"
            "[FRANÇAIS]\n"
            "Bienvenue dans HADJ No-Touch ! Cette version portable fonctionne à 100 % hors ligne.\n"
            "Pour démarrer l'application, double-cliquez simplement sur HADJ_NoTouch.exe\n"
            "Raccourci arrêt d'urgence permanent : Ctrl + Alt + Échap\n\n"
            "[ARABIC - العربية]\n"
            "مرحباً بك في حاج (تحكّم بدون لمس). هذا الإصدار المحمول يعمل بالكامل 100% بدون إنترنت.\n"
            "لتشغيل البرنامج، انقر نقراً مزدوجاً على HADJ_NoTouch.exe\n"
            "اختصار إيقاف الطوارئ الدائم: Ctrl + Alt + Escape\n\n"
            "[ENGLISH]\n"
            "Welcome to HADJ No-Touch! This portable build operates 100% offline.\n"
            "To launch the application, simply double-click HADJ_NoTouch.exe\n"
            "Permanent Emergency Stop Shortcut: Ctrl + Alt + Escape\n\n"
            "=================================================================\n"
        )

    zip_filename = "HADJ_NoTouch_v3_Windows_Portable.zip"
    zip_path = os.path.join(PROJECT_ROOT, "dist", zip_filename)
    log(f"Creating portable archive: {zip_filename}...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, os.path.dirname(dist_dir))
                zf.write(abs_path, rel_path)

    log(f"Portable archive successfully generated at: {zip_path}")
    return zip_path


def main():
    log("Starting Windows distribution build...")
    ensure_icon()
    success = run_pyinstaller()
    if not success:
        log("PyInstaller compilation failed.")
        return 1

    zip_path = create_portable_zip()
    if zip_path and os.path.exists(zip_path):
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        log(f"SUCCESS! Portable release package: {zip_path} ({size_mb:.1f} MB)")
        return 0
    else:
        log("Failed to create portable ZIP.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
