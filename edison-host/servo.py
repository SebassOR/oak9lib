from machine import Pin, PWM
from time import sleep

# Configurar servos
servo1 = PWM(Pin(2))
servo2 = PWM(Pin(3))

# Frecuencia estándar para servos
servo1.freq(50)
servo2.freq(50)

def set_angle(servo, angle):
    """
    Convierte un ángulo (0-180°)
    a un ciclo de trabajo PWM para un servo estándar.
    """
    min_us = 500      # pulso para 0°
    max_us = 2500     # pulso para 180°

    pulse_us = min_us + (max_us - min_us) * angle / 180
    duty = int(pulse_us * 65535 / 20000)  # 20 ms = 50 Hz

    servo.duty_u16(duty)

# Posición Home
HOME_ANGLE = 90

# Mover ambos servos a Home
set_angle(servo1, HOME_ANGLE)
set_angle(servo2, HOME_ANGLE)

print("Servos en posición Home")

# Mantener el programa corriendo
while True:
    sleep(1)
