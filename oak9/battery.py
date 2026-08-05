class Battery:
    def __init__(self, transport):
        self._transport = transport

    def read(self):
        return self._transport.send("battery.read")

    def calibrate(self, raw, mv):
        return self._transport.send("battery.calibrate", raw=raw, mv=mv)
