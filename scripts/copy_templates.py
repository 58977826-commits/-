"""把 archived 工作区里的 6 张导入模板复制到 data/samples/。

仅作一次性操作；模板列名是 normalize/fields.py 别名字典的事实标准。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def find_templates_dir() -> Path | None:
    root = Path(r"D:\CursorWorkSpace")
    if not root.exists():
        return None
    for sub in root.iterdir():
        if not sub.is_dir():
            continue
        for c in sub.rglob("import_templates"):
            if c.is_dir():
                return c
    return None


def main() -> int:
    src = find_templates_dir()
    if src is None:
        print("[error] 没找到 import_templates 目录")
        return 1
    dst = Path(__file__).resolve().parents[1] / "data" / "samples"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src.glob("*.xlsx")):
        target = dst / f.name
        shutil.copy2(f, target)
        print(f"copied {f.name} -> {target.relative_to(dst.parents[1])}")
        n += 1
    print(f"\n done. {n} files copied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
