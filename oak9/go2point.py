class Go2Point:
    def __init__(self, transport):
        self._transport = transport

    def set(self, x, y):
        return self._transport.send("robot.go2point.set", x=x, y=y)

    def stop(self):
        return self._transport.send("robot.go2point.stop")

    def status(self):
        return self._transport.send("robot.go2point.status")

    def pid_get(self):
        return self._transport.send("robot.go2point.pid.get")

    def pid_set(self, v_max_giro_deg_s, a_max_giro_deg_s2,
                v_max_avance_mm_s, a_max_avance_mm_s2, ts_ms):
        return self._transport.send(
            "robot.go2point.pid.set", v_max_giro_deg_s=v_max_giro_deg_s,
            a_max_giro_deg_s2=a_max_giro_deg_s2,
            v_max_avance_mm_s=v_max_avance_mm_s,
            a_max_avance_mm_s2=a_max_avance_mm_s2, ts_ms=ts_ms
        )
