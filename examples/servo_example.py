from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.servo.pid_get())  # ganancias actuales del control de velocidad en modo servo
print(robot.servo.pid_set(kp=4.7404, ki=3.8541, kv=0.0043, ts_ms=25, deadband=0.5))  # ajusta el PID
print(robot.servo.set(left=-1000, right=-1000))  # setpoint de velocidad por rueda (negativo = reversa)

robot.live_plot(
    robot.servo.status,
    ["left_error", "right_error", "left_velocity", "right_velocity"],
    interval=0.05
)  # error y velocidad medida de cada rueda

print(robot.servo.stop())  # cancela el movimiento en curso

robot.close()
