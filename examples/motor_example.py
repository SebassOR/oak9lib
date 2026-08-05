from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.motor.pwm(left=100, right=100))
print(robot.motor.stop())
print(robot.motor.invert_get())
print(robot.motor.invert_set(left=True, right=False))

robot.close()
