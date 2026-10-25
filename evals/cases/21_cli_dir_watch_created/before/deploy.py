import os
import sys


def main():
    os.makedirs("out", exist_ok=True)
    with open(os.path.join("out", "receipt.txt"), "w") as f:
        f.write("build ok")
    with open(os.path.join("out", "cache.tmp"), "w") as f:
        f.write("scratch data")
    print("Build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
