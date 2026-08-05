from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.wheel_position.pid_get())
print(robot.wheel_position.pid_set(kp=4.9990, ki=8.0034, kd=0.1569, ts_ms=25, deadband=1))
print(robot.wheel_position.set(left=3000, right=3000))

robot.live_plot(
    robot.wheel_position.status,
    ["left_target", "right_target", "left_error", "right_error"],
    interval=0.05
)

print(robot.wheel_position.stop())

robot.close()
