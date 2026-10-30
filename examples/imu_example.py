from oak9 import Robot

robot = Robot("192.168.0.102")

print(robot.imu.read())         # datos crudos del acelerometro/giroscopio
print(robot.imu.attitude_get()) # roll/pitch/yaw ya fusionados
print(robot.imu.filter_get())   # parametros del filtro complementario
print(robot.imu.filter_set(alpha=0.98, ts_ms=10)) # peso giro vs acelerometro y periodo de muestreo
print(robot.imu.calibrate())    # calibra el offset del IMU (robot debe estar quieto)

robot.live_plot(robot.imu.attitude_get, ["roll", "pitch", "yaw"],
                interval=0.01)

robot.close()
