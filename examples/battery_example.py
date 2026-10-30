from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.battery.read())                      # voltaje actual de la bateria
print(robot.battery.calibrate(raw=3027, mv=8631)) # raw=lectura ADC, mv=voltaje real medido con multimetro

robot.live_plot(robot.battery.read, ["voltage"], interval=0.2)  # grafica en vivo, refresca cada 0.2s

robot.close()
