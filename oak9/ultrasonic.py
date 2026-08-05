class Ultrasonic:
    def __init__(self, transport):
        self._transport = transport

    def read(self):
        return self._transport.send("ultrasonic.read")

    def filter_get(self):
        return self._transport.send("ultrasonic.filter.get")

    def filter_set(self, enabled, window, alpha):
        return self._transport.send("ultrasonic.filter.set",
                                     enabled=enabled, window=window,
                                     alpha=alpha)
