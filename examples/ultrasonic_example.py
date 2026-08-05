from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.ultrasonic.read())
print(robot.ultrasonic.filter_get())
print(robot.ultrasonic.filter_set(enabled=True, window=9, alpha=0.3))

robot.live_plot(robot.ultrasonic.read, ["s1"], interval=0.01)

robot.close()
