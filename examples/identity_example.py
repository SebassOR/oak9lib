from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.identity.get())
print(robot.identity.set("OAK9-R3"))

robot.close()
