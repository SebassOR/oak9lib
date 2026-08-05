class Motor:
    def __init__(self, transport):
        self._transport = transport

    def pwm(self, left, right):
        return self._transport.send("motor.pwm", left=left, right=right)

    def stop(self):
        return self._transport.send("motor.stop")

    def invert_get(self):
        return self._transport.send("motor.invert.get")

    def invert_set(self, left, right):
        return self._transport.send("motor.invert.set", left=left,
                                     right=right)
