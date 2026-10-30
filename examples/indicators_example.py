from oak9 import Robot

robot = Robot("192.168.100.9")

print(robot.indicators.tone(hz=440, ms=200))                       # suena el buzzer 200ms a 440Hz
print(robot.indicators.lcd_print(row=0, col=0, text="Hola OAK9"))  # escribe texto en la LCD (fila, columna)

robot.close()
