"""Manda el robot a un punto (x, y): gira para apuntar y avanza
derecho, las dos fases resueltas en firmware con go2point.set().
"""
import time

from oak9 import Robot

x_ref = 300.0  # mm
y_ref = 0.0  # mm

robot = Robot("192.168.100.9")

try:
    robot.go2point.set(x=x_ref, y=y_ref)  # arranca: gira y luego avanza, solo

    status = robot.go2point.status()
    while status["active"]:                # active=False cuando termina (o si aborta solo)
        print(f"fase={status['phase']}  error=({status['x_error']:.0f}, {status['y_error']:.0f}) mm")
        time.sleep(0.1)
        status = robot.go2point.status()

finally:
    robot.go2point.stop()  # por si Ctrl+C a medio movimiento
    robot.close()
