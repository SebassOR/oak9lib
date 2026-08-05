from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.wifi.get())
print(robot.wifi.set(ssid="MiRed", password="12345678"))

robot.close()
