from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.orientation.pid_get())
print(robot.orientation.pid_set(kp=6.0, cruise_deg_s=90.0, a_max_deg_s2=120.0, ts_ms=25))
print(robot.orientation.set(theta=90))

robot.live_plot(
    robot.orientation.status,
    ["error", "theta_dot_d", "wheel_deg_s"],
    interval=0.05
)

print(robot.orientation.stop())

robot.close()
