from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.pose.get())                            # posicion/orientacion estimada (odometria)
print(robot.pose.set(x_mm=0, y_mm=0, theta_deg=0)) # reinicia la odometria a este origen

robot.live_plot(robot.pose.get, ["x_mm", "y_mm", "theta_deg"], interval=0.05)

robot.close()
