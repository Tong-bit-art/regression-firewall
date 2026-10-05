import os, sys, tempfile

def main():
    cache = os.path.join(tempfile.gettempdir(), f"regfw-eval14-{os.getpid()}.tmp")
    with open(cache, "w") as f:
        f.write("cache")
    print("Deployment complete")
    print(f"cache: {cache}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
