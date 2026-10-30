from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.wifi.get())                                   # SSID/config wifi guardada
print(robot.wifi.set(ssid="MiRed", password="12345678"))  # nueva red (requiere reboot manual para aplicarse)

robot.close()
