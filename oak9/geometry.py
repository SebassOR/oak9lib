class Geometry:
    def __init__(self, transport):
        self._transport = transport

    def get(self):
        return self._transport.send("robot.geometry.get")

    def set(self, wheel_radius_mm, track_width_mm):
        return self._transport.send(
            "robot.geometry.set", wheel_radius_mm=wheel_radius_mm,
            track_width_mm=track_width_mm
        )
