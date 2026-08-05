class Orientation:
    def __init__(self, transport):
        self._transport = transport

    def set(self, theta):
        return self._transport.send("robot.orientation.set", theta=theta)

    def stop(self):
        return self._transport.send("robot.orientation.stop")

    def status(self):
        return self._transport.send("robot.orientation.status")

    def pid_get(self):
        return self._transport.send("robot.orientation.pid.get")

    def pid_set(self, kp, cruise_deg_s, a_max_deg_s2, ts_ms):
        return self._transport.send(
            "robot.orientation.pid.set", kp=kp,
            cruise_deg_s=cruise_deg_s, a_max_deg_s2=a_max_deg_s2, ts_ms=ts_ms
        )
