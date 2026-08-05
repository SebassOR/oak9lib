class Imu:
    def __init__(self, transport):
        self._transport = transport

    def read(self):
        return self._transport.send("imu.read")

    def attitude_get(self):
        return self._transport.send("imu.attitude.get")

    def calibrate(self):
        return self._transport.send("imu.calibrate")

    def filter_get(self):
        return self._transport.send("imu.attitude.filter.get")

    def filter_set(self, alpha, ts_ms):
        return self._transport.send("imu.attitude.filter.set", alpha=alpha,
                                     ts_ms=ts_ms)
