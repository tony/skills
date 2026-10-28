import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Print sorted unique UTF-8 lines.")
parser.add_argument("file", type=Path)
args = parser.parse_args()
print("\n".join(sorted(set(args.file.read_text(encoding="utf-8").splitlines()))))
