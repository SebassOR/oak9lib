"""Cambia el sentido de motores/encoders (varia por cableado, no es
igual en todos los robots) y prueba que quedo bien con go2point: si el
signo esta mal, el robot avanza para atras o gira al lado contrario de
lo que se le pide.

motor.invert/encoder.invert quedan guardados en la flash del robot
(persistentes) -- se calibra una vez por robot, no hace falta repetir
esto cada sesion.
"""
import time

from oak9 import Robot

invertir_motor_izq = False
invertir_motor_der = False
invertir_encoder_izq = True
invertir_encoder_der = False

robot = Robot("192.168.100.9")

print("antes:", robot.motor.invert_get(), robot.encoder.invert_get())

robot.motor.invert_set(left=invertir_motor_izq, right=invertir_motor_der)
robot.encoder.invert_set(left=invertir_encoder_izq, right=invertir_encoder_der)

print("despues:", robot.motor.invert_get(), robot.encoder.invert_get())

# prueba: 300mm derecho -- si el signo esta mal, el robot no llega ahi
robot.pose.set(x_mm=0, y_mm=0, theta_deg=0)
robot.go2point.set(x=-300, y=0)

status = robot.go2point.status()
while status["active"]:
    time.sleep(0.05)
    status = robot.go2point.status()

pose = robot.pose.get()
print(f"pose final=({pose['x_mm']:.0f}, {pose['y_mm']:.0f})  esperado=(300, 0)")

robot.go2point.stop()
robot.close()
