from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.servo.pid_get())
print(robot.servo.pid_set(kp=4.7404, ki=3.8541, kv=0.0043, ts_ms=25, deadband=0.5))
print(robot.servo.set(left=-1000, right=-1000))

robot.live_plot(
    robot.servo.status,
    ["left_error", "right_error", "left_velocity", "right_velocity"],
    interval=0.05
)

print(robot.servo.stop())

robot.close()
