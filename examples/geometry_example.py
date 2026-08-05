from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.geometry.get())
print(robot.geometry.set(wheel_radius_mm=34, track_width_mm=165.9))
print(robot.geometry.get())

robot.close()
