class Line:
    def __init__(self, transport):
        self._transport = transport

    def read(self):
        return self._transport.send("line.read")
