"""Avanza y frena cuando un obstaculo esta a una distancia d <= d_min.
"""
import time

from oak9 import Robot

omega = 120.0  # deg/s, velocidad de crucero
d_min = 15.0   # mm

robot = Robot("192.168.3.1")

try:
    robot.wheel_velocity.set(left=omega, right=omega)  # avanza derecho a velocidad constante

    d = d_min + 1               # valor inicial > d_min, solo para entrar al lazo
    while d > d_min:
        d = robot.ultrasonic.read()["s1"]
        print(f"d = {d:.0f} mm")
        time.sleep(0.02)

finally:
    robot.wheel_velocity.stop()  # se ejecuta siempre, incluso si algo truena arriba
    robot.close()
