from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.send("motor.pwm", left=100, right=100))

samples = robot.sample(robot.battery.read, duration=2.0, interval=0.2)
for t, reading in samples:
    print(t, reading)

robot.plot(robot.battery.read, ["voltage"], duration=3.0, interval=0.2)
robot.live_plot(robot.battery.read, ["voltage"], duration=10.0, window=5.0)

robot.close()
