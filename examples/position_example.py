from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.position.pid_get())
print(robot.position.pid_set(kp=3.0, h_mm=100.0, cruise_mm_s=100.0, a_max_mm_s2=250.0, ts_ms=25))
print(robot.position.set(x=0, y=0))

robot.live_plot(
    robot.position.status,
    ["x_error", "y_error", "left_deg_s", "right_deg_s"],
    interval=0.05
)

print(robot.position.stop())

robot.close()
