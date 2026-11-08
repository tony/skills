import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--client", choices=["claude-code", "codex"], required=True)
print(json.dumps({"client": parser.parse_args().client}))
