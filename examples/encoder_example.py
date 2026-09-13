from oak9 import Robot

robot = Robot("192.168.3.3")

print(robot.encoder.read())        # ticks acumulados de cada rueda
print(robot.encoder.reset())       # pone los contadores en 0
print(robot.encoder.cpr_get())     # cuentas por revolucion (CPR) configuradas
print(robot.encoder.cpr_set(1336)) # cambia el CPR (se guarda en el firmware)
print(robot.encoder.invert_get())  # que ruedas tienen el signo invertido
"""print(robot.encoder.invert_set(left=True, right=False))
print(robot.encoder.kinematics())  # velocidad/aceleracion angular derivadas de los encoders

robot.live_plot(robot.encoder.read, ["left_deg", "right_deg"], interval=0.05)

robot.live_plot(
    robot.encoder.kinematics,
    ["left_deg_s", "right_deg_s", "left_deg_s2", "right_deg_s2"],
    interval=0.05
)

robot.close()"""
