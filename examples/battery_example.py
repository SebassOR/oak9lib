from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.battery.read())
print(robot.battery.calibrate(raw=3027, mv=8631))

robot.live_plot(robot.battery.read, ["voltage"], interval=0.2)

robot.close()
