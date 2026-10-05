class Client:
    def __init__(self, retries=3):
        self.retries = retries


class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


def connect(host, port=5432):
    return (host, port)
