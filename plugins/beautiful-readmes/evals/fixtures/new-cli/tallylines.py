import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Count nonempty lines in a UTF-8 file.")
parser.add_argument("file", type=Path)
args = parser.parse_args()
print(sum(bool(line.strip()) for line in args.file.read_text(encoding="utf-8").splitlines()))
