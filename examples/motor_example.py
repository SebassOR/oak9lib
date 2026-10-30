from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.motor.pwm(left=100, right=100))  # PWM directo a cada motor (sin control de velocidad)


robot.close()
