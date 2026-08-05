class Encoder:
    """left/right tick counters, con conversión a grados (CPR
    configurable y persistente, como identity)."""

    def __init__(self, transport):
        self._transport = transport

    def read(self):
        return self._transport.send("encoder.read")

    def kinematics(self):
        return self._transport.send("encoder.kinematics.get")

    def reset(self):
        return self._transport.send("encoder.reset")

    def cpr_get(self):
        return self._transport.send("encoder.cpr.get")

    def cpr_set(self, cpr):
        return self._transport.send("encoder.cpr.set", cpr=cpr)

    def invert_get(self):
        return self._transport.send("encoder.invert.get")

    def invert_set(self, left, right):
        return self._transport.send("encoder.invert.set", left=left,
                                     right=right)
