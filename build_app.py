"""
HADJ NO-TOUCH AI — Windows Desktop Build Script (optimisé pour espace disque).
Utilise PyInstaller avec des imports ciblés et redirige les répertoires temporaires et de build
vers le lecteur D: s'il dispose de suffisamment d'espace libre (pour éviter 'Disk Full' sur C:).
"""

import os
import sys
import subprocess
import shutil

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    print("=================================================================", flush=True)
    print(" HADJ NO-TOUCH AI -- Build Windows EXE (optimise)", flush=True)
    print("=================================================================\n", flush=True)

    # Clean old build artifacts on root (C:) to save space
    for d in ["dist", "build"]:
        p = os.path.join(root, d)
        if os.path.exists(p):
            print(f"Nettoyage ancien dossier sur C: {p}...", flush=True)
            shutil.rmtree(p, ignore_errors=True)
    spec = os.path.join(root, "HADJ-NO-TOUCH-AI.spec")
    if os.path.exists(spec):
        try:
            os.remove(spec)
        except OSError:
            pass

    # Choose build destination: use D: if available with > 5 GB free to avoid C: disk full errors
    d_drive = "D:\\"
    build_base = root
    temp_dir = None
    if os.path.exists(d_drive):
        try:
            _, _, d_free = shutil.disk_usage(d_drive)
            if d_free > 5 * (1024**3):
                build_base = r"D:\hadj_build"
                temp_dir = r"D:\hadj_temp"
                print(f"[INFO] Utilisation du disque D: ({d_free / (1024**3):.1f} GB libres disponibles).", flush=True)
        except Exception as e:
            print(f"[WARN] Impossible de verifier D: ({e}), utilisation de {root}.", flush=True)

    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir
        os.environ["TMPDIR"] = temp_dir
        print(f"[INFO] Repertoire temporaire redirige : {temp_dir}", flush=True)

    dist_dir = os.path.join(build_base, "dist")
    work_dir = os.path.join(build_base, "build")
    spec_dir = build_base

    # Clean old build artifacts in build_base
    if build_base != root:
        for d in [dist_dir, work_dir]:
            if os.path.exists(d):
                print(f"Nettoyage {d}...", flush=True)
                shutil.rmtree(d, ignore_errors=True)

    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    print("[1/3] Compilation avec PyInstaller...", flush=True)

    web_data = os.path.join(root, "web")
    main_script = os.path.join(root, "main.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=HADJ-NO-TOUCH-AI",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        f"--specpath={spec_dir}",
        # PySide6 core only — no Qt3D / QtBluetooth / QtQml
        "--collect-submodules=PySide6.QtCore",
        "--collect-submodules=PySide6.QtGui",
        "--collect-submodules=PySide6.QtWidgets",
        "--collect-submodules=PySide6.QtMultimedia",
        "--collect-submodules=PySide6.QtNetwork",
        # MediaPipe & OpenCV
        "--collect-all=mediapipe",
        "--collect-all=cv2",
        # App modules
        "--collect-all=hadj_no_touch",
        # Web assets
        f"--add-data={web_data};web",
        # Exclude heavy unused packages to speed up build
        "--exclude-module=torch",
        "--exclude-module=torchvision",
        "--exclude-module=jax",
        "--exclude-module=jaxlib",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        "--exclude-module=matplotlib",
        "--exclude-module=pyarrow",
        "--exclude-module=sqlalchemy",
        "--exclude-module=h5py",
        "--exclude-module=pytest",
        "--exclude-module=PySide6.Qt3DAnimation",
        "--exclude-module=PySide6.Qt3DCore",
        "--exclude-module=PySide6.Qt3DExtras",
        "--exclude-module=PySide6.Qt3DInput",
        "--exclude-module=PySide6.Qt3DLogic",
        "--exclude-module=PySide6.Qt3DRender",
        "--exclude-module=PySide6.QtBluetooth",
        "--exclude-module=PySide6.QtQml",
        "--exclude-module=PySide6.QtQuick",
        "--exclude-module=PySide6.QtWebEngine",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        main_script
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[ERROR] Erreur PyInstaller (code: {result.returncode}).", flush=True)
        sys.exit(result.returncode)

    # Package into ZIP
    output_app_dir = os.path.join(dist_dir, "HADJ-NO-TOUCH-AI")
    zip_base = os.path.join(dist_dir, "HADJ-NO-TOUCH-AI-Windows")

    if os.path.exists(output_app_dir):
        print(f"[2/3] Creation du ZIP : {zip_base}.zip...", flush=True)
        shutil.make_archive(zip_base, "zip", output_app_dir)

        exe_path = os.path.join(output_app_dir, "HADJ-NO-TOUCH-AI.exe")

        # Create quick launcher batch file in root
        launcher_bat = os.path.join(root, "Lancer_HADJ_AI.bat")
        with open(launcher_bat, "w", encoding="utf-8") as f:
            f.write(f'@echo off\nstart "" "{exe_path}"\n')

        print("\n==========================================================", flush=True)
        print(" [OK] SUCCESS -- Application Windows prete !", flush=True)
        print(f" EXE : {exe_path}", flush=True)
        print(f" ZIP : {zip_base}.zip", flush=True)
        print(f" Raccourci lanceur : {launcher_bat}", flush=True)
        print("==========================================================", flush=True)
    else:
        print(f"[ERROR] Dossier {output_app_dir} introuvable.", flush=True)

if __name__ == "__main__":
    main()
