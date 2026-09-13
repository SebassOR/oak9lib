from .battery import Battery
from .encoder import Encoder
from .geometry import Geometry
from .go2point import Go2Point
from .identity import Identity
from .imu import Imu
from .indicators import Indicators
from .line import Line
from .motor import Motor
from .network import Wifi
from .orientation import Orientation
from .plotting import live_plot as _live_plot
from .plotting import plot as _plot
from .plotting import sample as _sample
from .pose import Pose
from .position import Position
from .servo import Servo
from .transport import Transport
from .ultrasonic import Ultrasonic
from .wheel_position import WheelPosition
from .wheel_velocity import WheelVelocity


class Robot:
    def __init__(self, host, port=8080, timeout=5.0):
        self._transport = Transport(host, port, timeout)
        self.motor = Motor(self._transport)
        self.battery = Battery(self._transport)
        self.encoder = Encoder(self._transport)
        self.indicators = Indicators(self._transport)
        self.identity = Identity(self._transport)
        self.wifi = Wifi(self._transport)
        self.wheel_position = WheelPosition(self._transport)
        self.ultrasonic = Ultrasonic(self._transport)
        self.line = Line(self._transport)
        self.imu = Imu(self._transport)
        self.wheel_velocity = WheelVelocity(self._transport)
        self.geometry = Geometry(self._transport)
        self.pose = Pose(self._transport)
        self.servo = Servo(self._transport)
        self.orientation = Orientation(self._transport)
        self.position = Position(self._transport)
        self.go2point = Go2Point(self._transport)

    def __repr__(self):
        return repr(self._transport).replace("Transport", "Robot", 1)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        self._transport.close()

    def send(self, command, **kwargs):
        """Escape hatch genérico: manda cualquier comando del router.

        >>> robot.send("motor.pwm", left=100, right=-100)
        """
        return self._transport.send(command, **kwargs)

    def _read_fn(self, command, kwargs):
        if callable(command):
            return command
        return lambda: self._transport.send(command, **kwargs)

    def sample(self, command, duration=2.0, interval=0.05, **kwargs):
        """`command` puede ser un string ("battery.read") o un
        callable (p. ej. lambda: robot.encoder.read())."""
        return _sample(
            self._read_fn(command, kwargs), duration=duration,
            interval=interval
        )

    def plot(self, command, fields, duration=2.0, interval=0.05, **kwargs):
        return _plot(
            self._read_fn(command, kwargs), fields, duration=duration,
            interval=interval
        )

    def live_plot(
        self, command, fields, duration=None, interval=0.1, window=10.0,
        **kwargs
    ):
        return _live_plot(
            self._read_fn(command, kwargs), fields, duration=duration,
            interval=interval, window=window
        )
