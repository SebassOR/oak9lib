"""Traza un cuadrado encadenando robot.go2point.set() hacia cada
vertice -- girar y avanzar ya lo resuelve el firmware en cada llamada.
"""
import time

from oak9 import Robot

lado = 300.0  # mm, largo de cada lado del cuadrado

robot = Robot("192.168.3.1")
# rampa mas suave que el default -- menos velocidad/aceleracion en el avance
# reduce el retraso de wheel_velocity respecto al perfil (y con eso el
# tramo que se queda corto en cada vertice, ver conversacion)
robot.go2point.pid_set(v_max_giro_deg_s=90.0, a_max_giro_deg_s2=120.0,
                       v_max_avance_mm_s=150.0, a_max_avance_mm_s2=100.0,
                       ts_ms=25)

esquinas_x = [lado, lado, 0, 0]
esquinas_y = [0, lado, lado, 0]

try:
    robot.pose.set(x_mm=0, y_mm=0, theta_deg=0)  # origen de la ruta

    for i in range(4):
        resultado = robot.go2point.set(x=esquinas_x[i], y=esquinas_y[i])
        print(f"vertice {i}: set() -> {resultado}")  # ok=False aqui = rechazado, no fallo silencioso

        status = robot.go2point.status()
        while status["active"]:              # bloquea hasta que termine este vertice
            time.sleep(0.05)
            status = robot.go2point.status()

        pose = robot.pose.get()  # posicion real, para comparar contra la esquina pedida
        print(f"vertice {i}: pose real=({pose['x_mm']:.0f}, {pose['y_mm']:.0f})  "
              f"valid={status['valid']}  x_error={status['x_error']:.0f}  "
              f"y_error={status['y_error']:.0f}")

finally:
    robot.go2point.stop()
    robot.close()
