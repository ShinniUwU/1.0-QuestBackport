# Build the mod and pack it as a drag-and-drop zip (SPT_Runtime/user/mods/<mod>).
# Same as package.ps1, but runs on Linux and macOS too.
# usage: python tools/package.py [--spt /path/to/SPT_Runtime] [--version 0.3.2]
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_NAME = "ShinnisQuestsBackport"
DEFAULT_SPT = r"C:\SPT\SPT_Runtime" if os.name == "nt" else os.environ.get("SPT_DIR", "")


def run(cmd):
    if subprocess.call(cmd):
        sys.exit(f"failed: {' '.join(cmd)}")


def zip_dir(dist, zip_path):
    # zipfile always writes "/" separators, so the zip works on Linux servers too
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(os.path.join(dist, "SPT_Runtime")):
            for f in files:
                path = os.path.join(base, f)
                z.write(path, os.path.relpath(path, dist))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spt", default=DEFAULT_SPT, help="SPT_Runtime folder (or set SPT_DIR)")
    ap.add_argument("--version", default="0.3.2")
    a = ap.parse_args()
    if not a.spt:
        sys.exit("pass --spt /path/to/SPT_Runtime or set SPT_DIR")
    checks.spt_runtime(a.spt)
    checks.data_files(os.path.join(ROOT, "data"), "wtt_ids.json", "tasks_pve.json", "tasks_pve_en.json")

    dist = os.path.join(ROOT, "dist")
    mod_dir = os.path.join(dist, "SPT_Runtime", "user", "mods", MOD_NAME)

    run(["dotnet", "build", os.path.join(ROOT, "src"), "-c", "Release", "-nologo", "-v", "q"])

    shutil.rmtree(mod_dir, ignore_errors=True)
    os.makedirs(mod_dir)
    run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "build.py"),
         os.path.join(ROOT, "data"), os.path.join(a.spt, "SPT_Data", "database"), mod_dir])
    shutil.copy(os.path.join(ROOT, "src", "bin", "Release", f"{MOD_NAME}.dll"), mod_dir)
    shutil.copy(os.path.join(ROOT, "src", "config.json"), mod_dir)
    shutil.move(os.path.join(mod_dir, "build_report.json"), os.path.join(dist, "build_report.json"))

    zip_path = os.path.join(dist, f"{MOD_NAME}-{a.version}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    zip_dir(dist, zip_path)
    print(f"packed {zip_path}")


if __name__ == "__main__":
    main()
