from pathlib import Path
import re


def safe_filename(name: str) -> str:
    base = Path(name).name.strip()
    base = re.sub(r"[^A-Za-z0-9._ -]", "-", base)
    base = re.sub(r"\s+", "-", base)
    return base or "uploaded-file.pdf"
