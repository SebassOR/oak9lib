# experimental (proyecto KL) -- todavia en ajuste, no se recomienda usar por ahora
from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.orientation.pid_get())  # ganancias actuales del control de orientacion
print(robot.orientation.pid_set(kp=2.0, cruise_deg_s=90.0, a_max_deg_s2=120.0, ts_ms=25))  # ajusta el PID
print(robot.orientation.set(theta=0))  # gira el robot hasta apuntar a theta grados

robot.live_plot(
    robot.orientation.status,
    ["error", "theta_dot_d", "wheel_deg_s"],
    interval=0.05
)  # error restante y velocidad deseada mientras gira

print(robot.orientation.stop())  # cancela el movimiento en curso

robot.close()
