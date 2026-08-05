# oak9

Librería Python para hablar directo con el robot OAK9 por TCP (sin pasar
por `server/`). Pensada para experimentar con control, sensores y
perfiles de movimiento desde una terminal, un script o un notebook.

```python
from oak9 import Robot

robot = Robot("192.168.3.1")
robot.motor.pwm(left=100, right=100)
robot.motor.stop()
robot.battery.read()
robot.plot("battery.read", ["voltage"], duration=3)
robot.close()
```

## Instalación

Requiere Python 3.8+.

```bash
pip install -e .
```

Esto instala la librería en modo editable (los cambios en `oak9/` se
reflejan sin reinstalar) y trae su única dependencia externa,
`matplotlib`.

## Uso básico

`Robot(host, port=8080, timeout=5.0)` abre una conexión TCP al robot y
expone un subsistema por sensor/actuador:

| Atributo | Módulo | Atributo | Módulo |
|---|---|---|---|
| `motor` | `motor.py` | `line` | `line.py` |
| `battery` | `battery.py` | `imu` | `imu.py` |
| `encoder` | `encoder.py` | `wheel_velocity` | `wheel_velocity.py` |
| `indicators` | `indicators.py` | `geometry` | `geometry.py` |
| `identity` | `identity.py` | `pose` | `pose.py` |
| `wifi` | `network.py` | `servo` | `servo.py` |
| `wheel_position` | `wheel_position.py` | `orientation` | `orientation.py` |
| `ultrasonic` | `ultrasonic.py` | `position` | `position.py` |

También puede usarse como context manager (`with Robot(...) as robot:`),
que cierra la conexión al salir.

Para cualquier comando del router que no tenga método dedicado, existe
el escape hatch genérico:

```python
robot.send("motor.pwm", left=100, right=-100)
```

### Graficar lecturas

```python
robot.sample("battery.read", duration=2.0, interval=0.05)   # lista de dicts
robot.plot("battery.read", ["voltage"], duration=3)         # gráfica al final
robot.live_plot("encoder.read", ["ticks"], window=10.0)     # gráfica en vivo
```

`command` puede ser un string ("battery.read") o un callable, p. ej.
`lambda: robot.encoder.read()`.

## Ejemplos

La carpeta [`examples/`](examples/) tiene un archivo por subsistema
(`motor_example.py`, `battery_example.py`, etc.), cada uno ejecutable
directo:

```bash
python examples/motor_example.py
```

## Estructura

```
oak9lib/
├── oak9/           # la librería
├── examples/       # un ejemplo por subsistema
├── pyproject.toml
└── requirements.txt
```
