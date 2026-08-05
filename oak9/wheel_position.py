import time


class WheelPosition:
    def __init__(self, transport):
        self._transport = transport

    def set(self, left, right, wait=False, timeout=5.0, poll_interval=0.1):
        response = self._transport.send("motor.position.set", left=left,
                                         right=right)
        if not wait:
            return response

        deadline = time.monotonic() + timeout
        status = self.status()
        while status["left_pwm"] != 0 or status["right_pwm"] != 0:
            if time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)
            status = self.status()
        return status

    def stop(self):
        return self._transport.send("motor.position.stop")

    def status(self):
        return self._transport.send("motor.position.status")

    def pid_get(self):
        return self._transport.send("motor.position.pid.get")

    def pid_set(self, kp, ki, kd, ts_ms, deadband):
        return self._transport.send(
            "motor.position.pid.set", kp=kp, ki=ki, kd=kd, ts_ms=ts_ms,
            deadband=deadband
        )
