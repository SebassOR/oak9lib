from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.line.read())  # lectura de los sensores de linea (izquierdo/derecho)

robot.live_plot(robot.line.read, ["left", "right"], interval=0.05)

robot.close()
