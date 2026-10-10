"""Download the three pinned public models once; verify every SHA-256."""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

from .core import file_hash
from .live_swap import MODELS, MODEL_DIR, MODEL_REVISION


def download(item):
    name, (remote, digest) = item
    destination = MODEL_DIR / name
    if destination.is_file() and file_hash(destination) == digest:
        print(f"Vérifié : {name}", flush=True)
        return
    temporary = destination.with_suffix(".download")
    url = f"https://huggingface.co/hacksider/deep-live-cam/resolve/{MODEL_REVISION}/{remote}"
    try:
        with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        if file_hash(temporary) != digest:
            raise RuntimeError(f"Empreinte invalide : {name}")
        temporary.replace(destination)
        print(f"Installé et vérifié : {name}", flush=True)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, MODELS.items()))
