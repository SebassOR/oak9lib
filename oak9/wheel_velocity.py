class WheelVelocity:
    def __init__(self, transport):
        self._transport = transport

    def set(self, left, right):
        return self._transport.send("motor.velocity.set", left=left,
                                     right=right)

    def stop(self):
        return self._transport.send("motor.velocity.stop")

    def status(self):
        return self._transport.send("motor.velocity.status")

    def pid_get(self):
        return self._transport.send("motor.velocity.pid.get")

    def pid_set(self, kp, ki, kd, ts_ms, alpha):
        return self._transport.send(
            "motor.velocity.pid.set", kp=kp, ki=ki, kd=kd, ts_ms=ts_ms,
            alpha=alpha
        )
