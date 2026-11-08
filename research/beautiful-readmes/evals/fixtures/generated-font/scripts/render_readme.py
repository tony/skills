from pathlib import Path

root = Path(__file__).resolve().parents[1]
(root / "README.md").write_text((root / "docs/README.template.md").read_text())
