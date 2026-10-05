"""samplelib — a tiny library whose public API Regression Firewall watches."""

__all__ = ["Client", "RetryPolicy", "connect"]


class Client:
    def __init__(self, host, retries=3):
        self.host = host
        self.retries = retries

    def request(self, path):
        return {"path": path}


class RetryPolicy:
    """Deprecated: pass retries to Client instead."""

    def __init__(self, attempts=5):
        self.attempts = attempts


def connect(host, port=5432):
    return (host, port)
