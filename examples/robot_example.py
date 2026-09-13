from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.send("motor.pwm", left=100, right=100))  # escape hatch: manda cualquier comando del router por su nombre

samples = robot.sample(robot.battery.read, duration=2.0, interval=0.2)  # toma lecturas por 2s cada 0.2s, sin graficar
for t, reading in samples:
    print(t, reading)

robot.plot(robot.battery.read, ["voltage"], duration=3.0, interval=0.2)      # grafica de una sola vez, tras 3s
robot.live_plot(robot.battery.read, ["voltage"], duration=10.0, window=5.0)  # grafica en vivo, ventana de 5s, durante 10s

robot.close()
