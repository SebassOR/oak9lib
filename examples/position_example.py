# experimental (proyecto KL) -- todavia en ajuste, no se recomienda usar por ahora
from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.position.pid_get())  # ganancias actuales del control de posicion (x, y)
print(robot.position.pid_set(kp=3.0, h_mm=100.0, cruise_mm_s=100.0, a_max_mm_s2=250.0, ts_ms=25))  # ajusta el PID
print(robot.position.set(x=0, y=0))  # manda al robot a ese punto, en mm

robot.live_plot(
    robot.position.status,
    ["x_error", "y_error", "left_deg_s", "right_deg_s"],
    interval=0.05
)  # error hacia el objetivo y velocidad de cada rueda mientras se mueve

print(robot.position.stop())  # cancela el movimiento en curso

robot.close()
