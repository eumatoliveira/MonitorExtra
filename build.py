from hashlib import file_digest
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlretrieve
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
NAME = "MonitorExtra-Audio"
ASSETS = {
    "Apollo-Setup.exe": (
        "https://github.com/ClassicOldSong/Apollo/releases/download/v0.4.6/Apollo-0.4.6.exe",
        "42b2aefaacb3474511517a56b96ee9f0517f30ac38b5dd2fda9fd5b478f5021a",
    ),
    "Moonlight-Portable.zip": (
        "https://github.com/moonlight-stream/moonlight-qt/releases/download/v6.2.0/MoonlightPortable-x64-6.2.0.zip",
        "6f91d268b41ed5ca8066d9d7578dc403b8db190991ff48f00b1700465f8f7ebf",
    ),
}


def main():
    dist = ROOT / "dist"
    with TemporaryDirectory() as directory:
        staging = Path(directory)
        for name, (url, digest) in ASSETS.items():
            asset = staging / name
            urlretrieve(url, asset)
            with asset.open("rb") as stream:
                if file_digest(stream, "sha256").hexdigest() != digest:
                    raise RuntimeError(f"SHA-256 inválido: {name}")
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
             "--collect-submodules", "zeroconf", "--name", NAME, "--distpath", str(staging),
             "--workpath", str(staging / "build"), "--specpath", str(staging),
             str(ROOT / "MonitorExtra.py")],
            check=True,
        )
        executable = staging / f"{NAME}.exe"
        with ZipFile(executable, "a") as bundle:
            for name in ASSETS:
                bundle.write(staging / name, name)
        subprocess.run([str(executable), "--self-test"], check=True)
        dist.mkdir(exist_ok=True)
        import shutil
        shutil.copy2(executable, dist / executable.name)


if __name__ == "__main__":
    main()
