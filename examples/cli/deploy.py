"""A small CLI tool with observable behavior.

`deploy.py --env prod` prints a plan, writes a receipt file, and exits 0 on
success. Regression Firewall watches the stdout text, the exit code, and the
generated receipt — so an agent that changes any of them gets caught.
"""

import argparse
import json
import sys

RECEIPT_PATH = "out/deploy_receipt.json"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="deploy")
    parser.add_argument("--env", default="staging", choices=["staging", "prod"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    print(f"Deploying to {args.env}")
    if args.dry_run:
        print("Dry run: no changes applied")
        return 0

    print("Deployment complete")
    with open(RECEIPT_PATH, "w") as handle:
        json.dump({"env": args.env, "result": "ok"}, handle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
