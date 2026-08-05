class Identity:
    def __init__(self, transport):
        self._transport = transport

    def get(self):
        return self._transport.send("identity.get")

    def set(self, robot_id):
        return self._transport.send("identity.set", id=robot_id)
