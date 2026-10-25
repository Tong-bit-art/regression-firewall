import os
from pathlib import Path

token = os.getenv("APP_TOKEN", "x")
out = Path("out")
out.mkdir(exist_ok=True)
(out / "receipt.json").write_text(f"token={token}")
print("done")
