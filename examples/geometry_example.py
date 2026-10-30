from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.geometry.get())                                        # radio de rueda y ancho de eje guardados
print(robot.geometry.set(wheel_radius_mm=34, track_width_mm=165.9)) # actualiza la geometria del chasis
print(robot.geometry.get())                                        # confirma que se guardo

robot.close()
