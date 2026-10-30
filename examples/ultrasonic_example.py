from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.ultrasonic.read())        # distancia medida por el sensor (s1)
print(robot.ultrasonic.filter_get())  # parametros del filtro actual
print(robot.ultrasonic.filter_set(enabled=True, window=9, alpha=0.3))  # activa el filtro (ventana de muestras, peso alpha)

robot.live_plot(robot.ultrasonic.read, ["s1"], interval=0.01)

robot.close()
