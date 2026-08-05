"""Librería Python del proyecto OAK9 — sandbox para hablar con el
robot directo por TCP (sin pasar por server/) y experimentar con
control, sensores y perfiles de movimiento.

    from oak9 import Robot

    robot = Robot("192.168.3.1")
    robot.motor.pwm(left=100, right=100)
    robot.motor.stop()
    robot.battery.read()
    robot.plot("battery.read", ["voltage"], duration=3)
"""

from .robot import Robot
from .transport import parse_response

__all__ = ["Robot", "parse_response"]
