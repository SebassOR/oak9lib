class Pose:
    def __init__(self, transport):
        self._transport = transport

    def get(self):
        return self._transport.send("pose.get")

    def set(self, x_mm, y_mm, theta_deg):
        return self._transport.send(
            "pose.set", x_mm=x_mm, y_mm=y_mm, theta_deg=theta_deg
        )
