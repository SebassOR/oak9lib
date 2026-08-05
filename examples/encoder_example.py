from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.encoder.read())
print(robot.encoder.reset())
print(robot.encoder.cpr_get())
print(robot.encoder.cpr_set(1336))
print(robot.encoder.invert_get())
print(robot.encoder.invert_set(left=True, right=False))
print(robot.encoder.kinematics())

robot.live_plot(robot.encoder.read, ["left_deg", "right_deg"], interval=0.05)

robot.live_plot(
    robot.encoder.kinematics,
    ["left_deg_s", "right_deg_s", "left_deg_s2", "right_deg_s2"],
    interval=0.05
)

robot.close()
