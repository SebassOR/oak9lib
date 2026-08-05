from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.wheel_velocity.pid_get())
print(robot.wheel_velocity.pid_set(kp=2.6, ki=0.275, kd=0.01, ts_ms=25, alpha=0.12))
print(robot.wheel_velocity.set(left=90, right=90))
print(robot.wheel_velocity.status())

robot.live_plot(
    robot.wheel_velocity.status,
    ["left_target", "right_target", "left_measured", "right_measured"],
    interval=0.01
)

print(robot.wheel_velocity.stop())

robot.close()
