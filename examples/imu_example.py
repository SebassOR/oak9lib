from oak9 import Robot

robot = Robot("192.168.3.2")

print(robot.imu.read())
print(robot.imu.attitude_get())
print(robot.imu.filter_get())
print(robot.imu.filter_set(alpha=0.98, ts_ms=10))
print(robot.imu.calibrate())

robot.live_plot(robot.imu.attitude_get, ["roll", "pitch", "yaw"],
                interval=0.01)

robot.close()
