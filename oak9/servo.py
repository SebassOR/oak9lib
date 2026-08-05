class Servo:
    def __init__(self, transport):
        self._transport = transport

    def set(self, left, right):
        return self._transport.send("motor.servo.set", left=left, right=right)

    def stop(self):
        return self._transport.send("motor.servo.stop")

    def status(self):
        return self._transport.send("motor.servo.status")

    def pid_get(self):
        return self._transport.send("motor.servo.pid.get")

    def pid_set(self, kp, ki, kv, ts_ms, deadband):
        return self._transport.send(
            "motor.servo.pid.set", kp=kp, ki=ki, kv=kv, ts_ms=ts_ms,
            deadband=deadband
        )
