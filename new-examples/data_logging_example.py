"""Guarda el voltaje de la bateria en un archivo de texto.

robot.sample() regresa una lista de (tiempo, dict) -- aqui se escribe
linea por linea en vez de graficarse.
"""
from oak9 import Robot

robot = Robot("192.168.100.9")

try:
    muestras = robot.sample(robot.battery.read, duration=5.0, interval=0.1)  # 5s de lecturas, sin graficar
finally:
    robot.close()

with open("battery_log.csv", "w") as archivo:
    archivo.write("t,v\n")                                  # encabezado del CSV
    for t, lectura in muestras:
        archivo.write(f"{t},{lectura['voltage']}\n")        # una fila por muestra

print(f"{len(muestras)} muestras guardadas")
