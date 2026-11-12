import json
import math
import network
import socket
import time
from machine import I2C, PWM, Pin
from wifi_config import WIFI_SSID, WIFI_PASSWORD

# Edison
EDISON_HOST = "192.168.100.10"
EDISON_PORT = 3000
TELEMETRY_PATH = "/api/pico/telemetry"

# I2C
I2C_ID = 0
I2C_SDA_PIN = 0
I2C_SCL_PIN = 1
I2C_FREQUENCY_HZ = 400000

# MPU
MPU_ADDRESS = 0x68
MAG_ADDRESS = 0x0C
MAG_OFFSET_UT = (0.0, 0.0, 0.0)
MAG_SCALE = (1.0, 1.0, 1.0)
MAG_DECLINATION_DEG = 0.0

# Timing
SAMPLE_INTERVAL_MS = 100
TEMPERATURE_SAMPLE_INTERVAL_MS = 5000
TEMPERATURE_AVERAGE_SAMPLES = 3
GYRO_CALIBRATION_SAMPLES = 30

# Servos from servo.py: GP2 and GP3, with the original 50 Hz PWM range.
SERVO1_PIN = 2
SERVO2_PIN = 3
SERVO_FREQUENCY_HZ = 50
SERVO_CLOSED_ANGLE = 90
SERVO_OPEN_ANGLE = 0


def signed_16(high, low):
    value = (high << 8) | low

    if value > 32767:
        value -= 65536

    return value


class MPU9250:

    def __init__(self, i2c):

        self.i2c = i2c
        self.last_magnetometer = None
        self.has_magnetometer = False

        # Despertar MPU
        self.i2c.writeto_mem(
            MPU_ADDRESS,
            0x6B,
            b'\x00'
        )

        time.sleep_ms(100)
        self.i2c.writeto_mem(MPU_ADDRESS, 0x37, b'\x02')
        time.sleep_ms(10)

        try:
            identity = self.i2c.readfrom_mem(MAG_ADDRESS, 0x00, 1)[0]
            if identity != 0x48:
                raise OSError("Identificador AK8963 no reconocido")
            self.i2c.writeto_mem(MAG_ADDRESS, 0x0A, b'\x00')
            time.sleep_ms(10)
            self.i2c.writeto_mem(MAG_ADDRESS, 0x0A, b'\x16')
            time.sleep_ms(10)
            self.has_magnetometer = True
        except OSError as error:
            print("Magnetómetro no disponible; usaré yaw integrado del giroscopio:", error)

    def read_magnetometer(self):

        if not self.has_magnetometer:
            return None

        deadline = time.ticks_add(time.ticks_ms(), 100)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if self.i2c.readfrom_mem(MAG_ADDRESS, 0x02, 1)[0] & 0x01:
                data = self.i2c.readfrom_mem(MAG_ADDRESS, 0x03, 7)
                if data[6] & 0x08:
                    raise OSError("Desbordamiento en la lectura del magnetómetro")

                raw_x = signed_16(data[1], data[0])
                raw_y = signed_16(data[3], data[2])
                raw_z = signed_16(data[5], data[4])
                raw_values = (raw_x, raw_y, raw_z)
                values = []
                for index in range(3):
                    value = raw_values[index] * (4912.0 / 32760.0)
                    value = (value - MAG_OFFSET_UT[index]) * MAG_SCALE[index]
                    values.append(value)

                self.last_magnetometer = {
                    "x": values[0],
                    "y": values[1],
                    "z": values[2]
                }
                return self.last_magnetometer
            time.sleep_ms(2)

        if self.last_magnetometer is not None:
            return self.last_magnetometer
        raise OSError("El magnetómetro no produjo una lectura")

    def read_temperature(self):

        data = self.i2c.readfrom_mem(
            MPU_ADDRESS,
            0x41,
            2
        )

        raw = signed_16(data[0], data[1])

        return (raw / 333.87) + 21.0

    def read_gyroscope(self):

        data = self.i2c.readfrom_mem(
            MPU_ADDRESS,
            0x43,
            6
        )

        return {
            "x": signed_16(data[0], data[1]) / 131.0,
            "y": signed_16(data[2], data[3]) / 131.0,
            "z": signed_16(data[4], data[5]) / 131.0
        }

    def read_sample(self):

        accel_data = self.i2c.readfrom_mem(
            MPU_ADDRESS,
            0x3B,
            6
        )
        acceleration = {
            "x": signed_16(accel_data[0], accel_data[1]) / 16384.0,
            "y": signed_16(accel_data[2], accel_data[3]) / 16384.0,
            "z": signed_16(accel_data[4], accel_data[5]) / 16384.0
        }
        return acceleration, self.read_gyroscope(), self.read_magnetometer()


def calibrate_gyroscope_z(sensor):

    total = 0.0
    for sample_index in range(GYRO_CALIBRATION_SAMPLES):
        total += sensor.read_gyroscope()["z"]
        if sample_index < GYRO_CALIBRATION_SAMPLES - 1:
            time.sleep_ms(SAMPLE_INTERVAL_MS)
    bias = total / GYRO_CALIBRATION_SAMPLES
    print("Giroscopio calibrado; bias Z: {:.3f} grados/s".format(bias))
    return bias


def set_angle(servo, angle):
    pulse_us = 500 + (2500 - 500) * angle / 180
    duty = int(pulse_us * 65535 / 20000)
    servo.duty_u16(duty)


def apply_servo_command(command, servo1, servo2, current_state,
                        current_command_id):
    if not isinstance(command, dict):
        raise ValueError("El host no devolvió un comando de servos válido")

    state = command.get("state")
    command_id = command.get("command_id")
    if state not in ("open", "closed") or not isinstance(command_id, int):
        raise ValueError("El comando de servos recibido no es válido")
    if command_id < 0:
        raise ValueError("El identificador del comando de servos no es válido")

    if state != current_state or command_id != current_command_id:
        angle = SERVO_OPEN_ANGLE if state == "open" else SERVO_CLOSED_ANGLE
        set_angle(servo1, angle)
        set_angle(servo2, 180 - angle)
        print("Servos {} a {} grados".format(state, angle))
        return state, command_id

    return current_state, current_command_id


def calculate_orientation(acceleration, gyroscope, magnetometer,
                          previous_yaw, elapsed_seconds, gyro_z_bias):

    roll_rad = math.atan2(acceleration["y"], acceleration["z"])
    pitch_rad = math.atan2(
        -acceleration["x"],
        math.sqrt(acceleration["y"] ** 2 + acceleration["z"] ** 2)
    )
    yaw = previous_yaw if previous_yaw is not None else 0.0
    if previous_yaw is not None and elapsed_seconds > 0:
        yaw = (
            previous_yaw +
            (gyroscope["z"] - gyro_z_bias) * elapsed_seconds
        ) % 360.0

    if magnetometer is not None:
        mx = magnetometer["x"]
        my = magnetometer["y"]
        mz = magnetometer["z"]
        horizontal_x = mx * math.cos(pitch_rad) + mz * math.sin(pitch_rad)
        horizontal_y = (
            mx * math.sin(roll_rad) * math.sin(pitch_rad) +
            my * math.cos(roll_rad) -
            mz * math.sin(roll_rad) * math.cos(pitch_rad)
        )
        magnetic_yaw = (
            math.degrees(math.atan2(horizontal_y, horizontal_x)) +
            MAG_DECLINATION_DEG
        ) % 360.0
        if previous_yaw is None:
            yaw = magnetic_yaw
        else:
            yaw = (
                yaw + 0.02 *
                ((magnetic_yaw - yaw + 180.0) % 360.0 - 180.0)
            ) % 360.0

    return {
        "roll": math.degrees(roll_rad),
        "pitch": math.degrees(pitch_rad),
        "yaw": yaw,
        "heading_source": (
            "magnetometer" if magnetometer is not None else "gyro_integrated"
        )
    }


def connect_wifi():

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():

        wlan.connect(
            WIFI_SSID,
            WIFI_PASSWORD
        )

        timeout = time.ticks_add(
            time.ticks_ms(),
            20000
        )

        while (
            not wlan.isconnected() and
            time.ticks_diff(
                timeout,
                time.ticks_ms()
            ) > 0
        ):
            time.sleep_ms(500)

    if not wlan.isconnected():
        raise OSError("No se pudo conectar al WiFi")

    print("WiFi OK:", wlan.ifconfig())

    return wlan


def post_telemetry(payload):

    body = json.dumps(payload).encode()

    address = socket.getaddrinfo(
        EDISON_HOST,
        EDISON_PORT
    )[0][-1]

    sock = socket.socket()

    try:

        sock.settimeout(5)

        sock.connect(address)

        headers = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n\r\n"
        ).format(
            TELEMETRY_PATH,
            EDISON_HOST,
            len(body)
        )

        request = headers.encode() + body
        while request:
            sent = sock.send(request)
            if sent <= 0:
                raise OSError("El host Edison cerró la conexión")
            request = request[sent:]

        response = b""
        while True:
            chunk = sock.recv(256)
            if not chunk:
                break
            response += chunk

        status_line, response_body = response.split(b"\r\n\r\n", 1)
        status_line = status_line.split(b"\r\n", 1)[0]
        if b" 202 " not in status_line:
            raise OSError(
                "Edison respondió {}: {}".format(
                    status_line.decode(),
                    response_body.decode().strip()
                )
            )
        print("Telemetría aceptada por Edison")
        return json.loads(response_body.decode())

    finally:

        sock.close()


def main():

    servo1 = PWM(Pin(SERVO1_PIN))
    servo2 = PWM(Pin(SERVO2_PIN))
    servo1.freq(SERVO_FREQUENCY_HZ)
    servo2.freq(SERVO_FREQUENCY_HZ)
    set_angle(servo1, SERVO_CLOSED_ANGLE)
    set_angle(servo2, SERVO_CLOSED_ANGLE)
    servo_state = "closed"
    servo_command_id = 0

    i2c = I2C(
        I2C_ID,
        sda=Pin(I2C_SDA_PIN),
        scl=Pin(I2C_SCL_PIN),
        freq=I2C_FREQUENCY_HZ
    )

    devices = i2c.scan()

    print(
        "I2C:",
        [hex(d) for d in devices]
    )

    if 0x68 not in devices:
        raise Exception(
            "MPU no encontrado"
        )

    sensor = MPU9250(i2c)
    print("Mantén el robot quieto mientras calibro el giroscopio.")
    gyro_z_bias = calibrate_gyroscope_z(sensor)

    wlan = connect_wifi()

    temps = []

    for _ in range(TEMPERATURE_AVERAGE_SAMPLES):

        temps.append(
            sensor.read_temperature()
        )

        time.sleep_ms(100)

    last_temp_ms = time.ticks_ms()
    previous_yaw = None
    previous_sample_ms = None

    while True:

        try:

            acceleration, gyroscope, magnetometer = (
                sensor.read_sample()
            )

            now = time.ticks_ms()
            elapsed_seconds = 0.0
            if previous_sample_ms is not None:
                elapsed_seconds = time.ticks_diff(
                    now,
                    previous_sample_ms
                ) / 1000.0
            previous_sample_ms = now

            if time.ticks_diff(
                now,
                last_temp_ms
            ) >= TEMPERATURE_SAMPLE_INTERVAL_MS:

                temps.append(
                    sensor.read_temperature()
                )

                if len(temps) > TEMPERATURE_AVERAGE_SAMPLES:
                    temps.pop(0)

                last_temp_ms = now

            orientation = calculate_orientation(
                acceleration,
                gyroscope,
                magnetometer,
                previous_yaw,
                elapsed_seconds,
                gyro_z_bias
            )
            previous_yaw = orientation["yaw"]

            payload = {

                "acceleration_g":
                acceleration,

                "gyroscope_dps":
                gyroscope,

                "magnetometer_ut":
                magnetometer,

                "magnetometer_available":
                sensor.has_magnetometer,

                "temperature_c":
                temps[-1],

                "temperature_avg_c":
                sum(temps) / len(temps),

                "temperature_samples":
                len(temps),

                "attitude":
                orientation,

                "servos": {
                    "state": servo_state,
                    "command_id": servo_command_id
                },

                "status":
                "online"
            }

            print(
                "Roll:",
                round(
                    orientation["roll"],
                    2
                ),
                "Pitch:",
                round(
                    orientation["pitch"],
                    2
                ),
                "Yaw:",
                round(
                    orientation["yaw"],
                    2
                )
            )

            host_response = post_telemetry(payload)
            servo_state, servo_command_id = apply_servo_command(
                host_response.get("servo_command"),
                servo1,
                servo2,
                servo_state,
                servo_command_id
            )

            time.sleep_ms(
                SAMPLE_INTERVAL_MS
            )

        except Exception as e:

            print(
                "Error:",
                e
            )

            time.sleep(2)


main()
