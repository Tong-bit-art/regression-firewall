CLI_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: true
    probes:
      - id: deploy
        command: ["python", "deploy.py"]
        files: ["receipt.txt"]
  public_api:
    enabled: false
"""

DEPLOY_PLAIN = """\
import sys

def main():
    print("Deployment complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

DEPLOY_FAIL = """\
import sys

def main():
    print("Deployment failed")
    return 1

if __name__ == "__main__":
    sys.exit(main())
"""

DEPLOY_WITH_RECEIPT = """\
import sys

def main():
    print("Deployment complete")
    with open("receipt.txt", "w") as f:
        f.write("receipt v1")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

DEPLOY_WITH_RECEIPT_V2 = DEPLOY_WITH_RECEIPT.replace("receipt v1", "receipt v2")


def read_report(project):
    import json

    return json.loads(
        (project / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
