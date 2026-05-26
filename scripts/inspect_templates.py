"""读取 archived 工作区里的导入模板，输出每张表的列名清单。

用于对比模板列名 vs normalize/fields.py 别名字典，识别需要补的列名。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def find_templates_dir() -> Path | None:
    """在 d:\\CursorWorkSpace 下查找包含 import_templates 的目录。"""
    root = Path(r"D:\CursorWorkSpace")
    if not root.exists():
        return None
    for sub in root.iterdir():
        if not sub.is_dir():
            continue
        cand = sub / "schemas" / "import_templates"
        if cand.exists():
            return cand
        # 也试着递归找
        for c in sub.rglob("import_templates"):
            if c.is_dir():
                return c
    return None


def main() -> int:
    TEMPLATES_DIR = find_templates_dir()
    if TEMPLATES_DIR is None or not TEMPLATES_DIR.exists():
        print("[error] 没找到 import_templates 目录")
        return 1
    print(f"[info] templates dir: {TEMPLATES_DIR}")

    for xlsx in sorted(TEMPLATES_DIR.glob("*.xlsx")):
        print("=" * 80)
        print(f"文件: {xlsx.name}")
        try:
            xl = pd.ExcelFile(xlsx)
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {e}")
            continue
        for sheet in xl.sheet_names:
            try:
                df = pd.read_excel(xlsx, sheet_name=sheet, nrows=3, dtype=object)
            except Exception as e:  # noqa: BLE001
                print(f"  sheet '{sheet}': [error] {e}")
                continue
            print(f"  sheet '{sheet}' ({len(df)} 行样本)：")
            for i, c in enumerate(df.columns, 1):
                print(f"    {i:>2}. {c}")
            if not df.empty:
                print(f"    样本行 1: {df.iloc[0].to_dict()}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
