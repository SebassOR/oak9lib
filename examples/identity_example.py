from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.identity.get())          # nombre/ID guardado en el robot
print(robot.identity.set("OAK9-R3")) # renombra el robot (persiste en el firmware)

robot.close()
