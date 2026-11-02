from .demo import run_demo
from pathlib import Path
import json
if __name__ == '__main__':
    print(json.dumps(run_demo(Path.cwd(), Path('run')), indent=2))
