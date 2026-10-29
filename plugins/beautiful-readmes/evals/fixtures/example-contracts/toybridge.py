from contextlib import contextmanager


class Server:
    def __init__(self, name, version=(3, 6)):
        self.name = name
        self.version = version
        self.events = []

    def select_layout(self, layout):
        self.events.append("version-probe")
        if layout.startswith("{") and (3, 4) <= self.version < (3, 8):
            raise ValueError("JSON layout unsupported")
        self.events.append("select-layout")
        return "applied"

    def close(self):
        self.events.append("kill-server:" + self.name)


@contextmanager
def temporary_server():
    server = Server("owned-example")
    try:
        yield server
    finally:
        server.close()
