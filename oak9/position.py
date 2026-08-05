class Position:
    def __init__(self, transport):
        self._transport = transport

    def set(self, x, y):
        return self._transport.send("robot.position.set", x=x, y=y)

    def stop(self):
        return self._transport.send("robot.position.stop")

    def status(self):
        return self._transport.send("robot.position.status")

    def pid_get(self):
        return self._transport.send("robot.position.pid.get")

    def pid_set(self, kp, h_mm, cruise_mm_s, a_max_mm_s2, ts_ms):
        return self._transport.send(
            "robot.position.pid.set", kp=kp, h_mm=h_mm,
            cruise_mm_s=cruise_mm_s, a_max_mm_s2=a_max_mm_s2, ts_ms=ts_ms
        )
