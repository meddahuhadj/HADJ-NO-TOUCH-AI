import os
import shutil

def get_dir_size(path):
    total = 0
    if not os.path.exists(path):
        return 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def main():
    root = r"c:\Users\User\Downloads\HADJ NO-TOUCH AI"
    b_size = get_dir_size(os.path.join(root, "build"))
    d_size = get_dir_size(os.path.join(root, "dist"))
    temp_size = get_dir_size(os.environ.get("TEMP", ""))
    
    total, used, free = shutil.disk_usage("C:\\")
    print(f"C: Total: {total / (1024**3):.2f} GB")
    print(f"C: Used: {used / (1024**3):.2f} GB")
    print(f"C: Free: {free / (1024**3):.2f} GB ({free / (1024**2):.1f} MB)")
    print(f"build/ size: {b_size / (1024**2):.1f} MB")
    print(f"dist/ size: {d_size / (1024**2):.1f} MB")
    print(f"TEMP size: {temp_size / (1024**2):.1f} MB")

if __name__ == "__main__":
    main()
