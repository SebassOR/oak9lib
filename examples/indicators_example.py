from oak9 import Robot

robot = Robot("192.168.3.1")

print(robot.indicators.tone(hz=440, ms=200))
print(robot.indicators.lcd_print(row=0, col=0, text="Hola OAK9"))

robot.close()
