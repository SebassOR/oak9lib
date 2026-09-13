from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.wheel_position.pid_get())  # ganancias actuales del control de posicion por rueda
print(robot.wheel_position.pid_set(kp=4.9990, ki=8.0034, kd=0.1569, ts_ms=25, deadband=1))  # ajusta el PID
print(robot.wheel_position.set(left=3000, right=3000))  # objetivo en ticks de encoder por rueda

robot.live_plot(
    robot.wheel_position.status,
    ["left_target", "right_target", "left_error", "right_error"],
    interval=0.05
)  # objetivo vs error restante de cada rueda

print(robot.wheel_position.stop())  # cancela el movimiento en curso

robot.close()
