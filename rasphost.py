import network
import socket as usocket
import time
import math
from machine import Pin

SSID = "Robocoffee-Labdst5"
PASSWORD = "6j5hF4akXA"

led = Pin("LED", Pin.OUT)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Conectando a WiFi...")
while not wlan.isconnected():
    time.sleep(1)
print("Conectado:", wlan.ifconfig())

# IP del robot ESP32 en la misma red
ROBOT_IP = "192.168.0.102"
ROBOT_PORT = 8080
DELIVERY_DISTANCES_MM = {1: 1000, 2: 1000, 3: 2000, 4: 2000}
TABLE_TURN_DIRECTIONS = {1: 1, 2: -1, 3: 1, 4: -1}
ROBOT_MOTION_TIMEOUT_S = 60
ROBOT_BUSY_STATES = ("saliendo", "esperando_cliente", "regresando", "error")
GO2POINT_V_MAX_GIRO_DEG_S = 90
GO2POINT_A_MAX_GIRO_DEG_S2 = 120
GO2POINT_V_MAX_AVANCE_MM_S = 300
GO2POINT_A_MAX_AVANCE_MM_S2 = 100
GO2POINT_TS_MS = 25
ORIENTATION_KP = 2.0
ORIENTATION_CRUISE_DEG_S = 120
ORIENTATION_A_MAX_DEG_S2 = 180
ORIENTATION_TS_MS = 25
ORIENTATION_TOLERANCE_DEG = 5
ORIENTATION_TIMEOUT_S = 30
ORIENTATION_STABLE_READINGS = 3
ORIENTATION_MAX_CORRECTIONS = 3
ORIGIN_POSITION_TOLERANCE_MM = 40
ORIGIN_HEADING_TOLERANCE_DEG = 5
POSITION_MAX_CORRECTIONS = 3

pedidos = []
contador_pedidos = 0
referencia_origen = None


def parsear_campos_robot(line):
    fields = {}
    for token in line.split()[2:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if value == "true":
            fields[key] = True
        elif value == "false":
            fields[key] = False
        else:
            try:
                fields[key] = float(value)
            except ValueError:
                fields[key] = value
    return fields


def enviar_comando_robot(sock, command):
    data = (command + "\n").encode()
    while data:
        sent = sock.send(data)
        if sent <= 0:
            raise OSError("No se pudo enviar el comando al robot")
        data = data[sent:]

    response = b""
    while b"\n" not in response:
        chunk = sock.recv(128)
        if not chunk:
            raise OSError("El robot cerró la conexión sin responder")
        response += chunk

    line = response.split(b"\n", 1)[0].decode().strip()
    if not line.startswith("OK "):
        raise OSError("El robot rechazó el comando: " + line)
    return parsear_campos_robot(line)


def normalizar_angulo(angulo):
    return angulo % 360


def leer_yaw_robot(sock):
    attitude = enviar_comando_robot(sock, "imu.attitude.get")
    if "yaw" not in attitude:
        raise OSError("La respuesta de imu.attitude.get no contiene yaw")
    return normalizar_angulo(float(attitude["yaw"]))


def leer_pose_robot(sock):
    pose = enviar_comando_robot(sock, "pose.get")
    if "x_mm" not in pose or "y_mm" not in pose or "theta_deg" not in pose:
        raise OSError("La respuesta de pose.get no contiene x_mm/y_mm/theta_deg")
    return pose


def diferencia_angular(angulo_objetivo, angulo_actual):
    return (angulo_objetivo - angulo_actual + 180) % 360 - 180


def girar_y_validar(sock, rumbo_pose_objetivo, yaw_referencia, cambio_yaw):
    yaw_objetivo = normalizar_angulo(yaw_referencia + cambio_yaw)

    for intento in range(ORIENTATION_MAX_CORRECTIONS + 1):
        enviar_comando_robot(
            sock,
            "robot.orientation.pid.set kp={} cruise_deg_s={} "
            "a_max_deg_s2={} ts_ms={}".format(
                ORIENTATION_KP,
                ORIENTATION_CRUISE_DEG_S,
                ORIENTATION_A_MAX_DEG_S2,
                ORIENTATION_TS_MS,
            ),
        )
        resultado = enviar_comando_robot(
            sock, "robot.orientation.set theta={}".format(rumbo_pose_objetivo)
        )
        print("orientation.set intento {} -> {}".format(intento + 1, resultado))

        start = time.ticks_ms()
        lecturas_estables = 0
        ultimo_yaw = None
        while time.ticks_diff(time.ticks_ms(), start) < ORIENTATION_TIMEOUT_S * 1000:
            yaw = leer_yaw_robot(sock)
            error = diferencia_angular(yaw_objetivo, yaw)
            print("MPU6050 yaw={:.1f}, objetivo={:.1f}, error={:.1f}".format(
                yaw, yaw_objetivo, error
            ))

            if abs(error) <= ORIENTATION_TOLERANCE_DEG:
                if ultimo_yaw is not None and abs(
                    diferencia_angular(yaw, ultimo_yaw)
                ) <= ORIENTATION_TOLERANCE_DEG:
                    lecturas_estables += 1
                else:
                    lecturas_estables = 1
                if lecturas_estables >= ORIENTATION_STABLE_READINGS:
                    return yaw
            else:
                lecturas_estables = 0

            ultimo_yaw = yaw
            time.sleep_ms(100)

        enviar_comando_robot(sock, "robot.orientation.stop")
        if intento == ORIENTATION_MAX_CORRECTIONS:
            break

        pose_actual = leer_pose_robot(sock)
        yaw_actual = leer_yaw_robot(sock)
        error = diferencia_angular(yaw_objetivo, yaw_actual)
        if abs(error) <= ORIENTATION_TOLERANCE_DEG:
            continue

        rumbo_pose_objetivo = pose_actual["theta_deg"] + error
        print(
            "Corrigiendo giro: error MPU={:.1f} grados, "
            "nuevo objetivo de pose={:.1f} grados".format(
                error, rumbo_pose_objetivo
            )
        )

    raise OSError(
        "El MPU6050 no confirmó el rumbo relativo {:.1f} grados "
        "tras {} correcciones (lectura final {:.1f}, error {:.1f})".format(
            cambio_yaw, ORIENTATION_MAX_CORRECTIONS, yaw, error
        )
    )


def mover_robot_a(sock, x_mm, y_mm):
    for intento in range(POSITION_MAX_CORRECTIONS + 1):
        enviar_comando_robot(sock, "motor.velocity.stop")
        resultado = enviar_comando_robot(
            sock, "robot.go2point.set x={} y={}".format(x_mm, y_mm)
        )
        print("go2point.set intento {} -> {}".format(intento + 1, resultado))

        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < ROBOT_MOTION_TIMEOUT_S * 1000:
            status = enviar_comando_robot(sock, "robot.go2point.status")
            if "active" not in status:
                raise OSError("La respuesta del robot no contiene el estado active")
            if status["active"]:
                time.sleep_ms(50)
                continue

            if status.get("valid") is False:
                raise OSError(
                    "go2point terminó con valid=false: {}".format(status)
                )

            pose = leer_pose_robot(sock)
            dx = x_mm - pose["x_mm"]
            dy = y_mm - pose["y_mm"]
            error_mm = math.sqrt(dx * dx + dy * dy)
            print(
                "Pose al terminar -> x={:.1f}, y={:.1f}; error={:.1f} mm".format(
                    pose["x_mm"], pose["y_mm"], error_mm
                )
            )
            if error_mm <= ORIGIN_POSITION_TOLERANCE_MM:
                return status
            if intento == POSITION_MAX_CORRECTIONS:
                raise OSError(
                    "No llegó al punto ({:.1f}, {:.1f}); error final {:.1f} mm "
                    "tras {} correcciones".format(
                        x_mm, y_mm, error_mm, POSITION_MAX_CORRECTIONS
                    )
                )
            print(
                "Corrigiendo posición hacia ({:.1f}, {:.1f}), "
                "error {:.1f} mm".format(x_mm, y_mm, error_mm)
            )
            break
        else:
            try:
                enviar_comando_robot(sock, "robot.go2point.stop")
            except Exception as stop_error:
                print("No se pudo detener la navegación:", stop_error)
            raise OSError("Se agotó el tiempo de navegación del robot")


def enviar_orden_robot(mesa):
    global referencia_origen
    if mesa not in DELIVERY_DISTANCES_MM:
        raise ValueError("Mesa no válida: {}".format(mesa))

    s = None
    try:
        print(f"Conectando al robot en {ROBOT_IP}...")
        addr = usocket.getaddrinfo(ROBOT_IP, ROBOT_PORT)[0][-1]
        s = usocket.socket()
        s.settimeout(5.0)
        s.connect(addr)

        enviar_comando_robot(
            s,
            "robot.go2point.pid.set "
            "v_max_giro_deg_s={} a_max_giro_deg_s2={} "
            "v_max_avance_mm_s={} a_max_avance_mm_s2={} ts_ms={}".format(
                GO2POINT_V_MAX_GIRO_DEG_S,
                GO2POINT_A_MAX_GIRO_DEG_S2,
                GO2POINT_V_MAX_AVANCE_MM_S,
                GO2POINT_A_MAX_AVANCE_MM_S2,
                GO2POINT_TS_MS,
            ),
        )

        if referencia_origen is None:
            enviar_comando_robot(s, "motor.velocity.stop")
            enviar_comando_robot(
                s, "pose.set x_mm=0 y_mm=0 theta_deg=0"
            )
            pose_origen = leer_pose_robot(s)
            referencia_origen = {
                "x_mm": pose_origen["x_mm"],
                "y_mm": pose_origen["y_mm"],
                "theta_deg": pose_origen["theta_deg"],
                "yaw": leer_yaw_robot(s),
            }

        origen_x = referencia_origen["x_mm"]
        origen_y = referencia_origen["y_mm"]
        theta_origen = referencia_origen["theta_deg"]
        yaw_origen = referencia_origen["yaw"]
        pose_inicio = leer_pose_robot(s)
        distancia_al_origen = math.sqrt(
            (pose_inicio["x_mm"] - origen_x) ** 2
            + (pose_inicio["y_mm"] - origen_y) ** 2
        )
        if distancia_al_origen > ORIGIN_POSITION_TOLERANCE_MM:
            raise OSError(
                "El robot no está en su origen: error de posición {:.1f} mm".format(
                    distancia_al_origen
                )
            )

        yaw_actual = leer_yaw_robot(s)
        error_yaw_inicio = diferencia_angular(yaw_origen, yaw_actual)
        error_theta_inicio = diferencia_angular(
            theta_origen, pose_inicio["theta_deg"]
        )
        if (
            abs(error_yaw_inicio) > ORIGIN_HEADING_TOLERANCE_DEG
            or abs(error_theta_inicio) > ORIGIN_HEADING_TOLERANCE_DEG
        ):
            print(
                "Alineando salida al rumbo original: MPU error={:.1f}, "
                "pose error={:.1f}".format(error_yaw_inicio, error_theta_inicio)
            )
            girar_y_validar(
                s,
                theta_origen,
                yaw_origen,
                0,
            )

        direccion_giro = TABLE_TURN_DIRECTIONS[mesa]
        distancia = DELIVERY_DISTANCES_MM[mesa]
        angulo_ruta = math.radians(theta_origen)
        destino_x = origen_x + distancia * math.cos(angulo_ruta)
        destino_y = origen_y + distancia * math.sin(angulo_ruta)
        mover_robot_a(s, destino_x, destino_y)
        girar_y_validar(
            s,
            theta_origen + direccion_giro * 90,
            yaw_origen,
            direccion_giro * 90,
        )
        print("El robot llegó al punto de entrega.")
        return {
            "yaw_inicio": yaw_origen,
            "theta_inicio": theta_origen,
            "origen_x_mm": origen_x,
            "origen_y_mm": origen_y,
            "direccion_giro": direccion_giro,
            "distancia_mm": distancia,
        }
    except Exception as e:
        if s:
            for command in (
                "robot.go2point.stop",
                "robot.orientation.stop",
            ):
                try:
                    enviar_comando_robot(s, command)
                except Exception as stop_error:
                    print("No se pudo ejecutar {}: {}".format(
                        command, stop_error
                    ))
        print("No se pudo completar el viaje de ida:", e)
        raise
    finally:
        if s:
            s.close()


def regresar_robot_al_origen(pedido):
    s = None
    try:
        addr = usocket.getaddrinfo(ROBOT_IP, ROBOT_PORT)[0][-1]
        s = usocket.socket()
        s.settimeout(5.0)
        s.connect(addr)

        yaw_inicio = pedido["yaw_inicio"]
        theta_inicio = pedido["theta_inicio"]
        origen_x = pedido["origen_x_mm"]
        origen_y = pedido["origen_y_mm"]
        direccion_giro = pedido["direccion_giro"]
        girar_y_validar(
            s,
            theta_inicio + direccion_giro * 180,
            yaw_inicio,
            direccion_giro * 180,
        )
        mover_robot_a(s, origen_x, origen_y)
        girar_y_validar(
            s,
            theta_inicio,
            yaw_inicio,
            0,
        )
        pose_final = leer_pose_robot(s)
        error_final_mm = math.sqrt(
            (pose_final["x_mm"] - origen_x) ** 2
            + (pose_final["y_mm"] - origen_y) ** 2
        )
        if error_final_mm > ORIGIN_POSITION_TOLERANCE_MM:
            raise OSError(
                "Regreso fuera del origen: error final {:.1f} mm".format(
                    error_final_mm
                )
            )
        print("El robot regresó al punto de partida.")
    except Exception as e:
        if s:
            for command in (
                "robot.go2point.stop",
                "robot.orientation.stop",
            ):
                try:
                    enviar_comando_robot(s, command)
                except Exception as stop_error:
                    print("No se pudo ejecutar {}: {}".format(
                        command, stop_error
                    ))
        print("No se pudo completar el regreso del robot:", e)
        raise
    finally:
        if s:
            s.close()


def buscar_pedido(order_id):
    for pedido in pedidos:
        if pedido["id"] == order_id:
            return pedido
    return None

# 1. Página de bienvenida interactiva
def welcome_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>RoboCoffee</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body { margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background:#6b3e26; font-family: Arial, sans-serif; overflow:hidden; cursor:pointer; }
        .container { text-align:center; padding: 0 15px; }
        h1 { font-size: clamp(2.5rem, 10vw, 4.5rem); color:white; animation: fadeIn 3s ease-in-out infinite alternate; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); margin:0; }
        p { color: #f0d5bc; font-size: 1.1rem; margin-top: 20px; opacity: 0.9; }
        @keyframes fadeIn {
          from { opacity:0.3; transform: scale(0.95); }
          to { opacity:1; transform: scale(1.05); }
        }
      </style>
    </head>
    <body onclick="window.location.href='/login';">
      <div class="container">
        <h1>RoboCoffee ☕</h1>
        <p>Toca la pantalla para entrar</p>
      </div>
      <script>
        setTimeout(function(){ window.location.href='/login'; }, 3000);
      </script>
    </body>
    </html>
    """

# 2. Página principal con selección de rol
def login_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>RoboCoffee - Login</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #f5f5f5; padding:20px; }
        h1 { color: #6b3e26; }
        .card { background: white; max-width: 350px; margin: 40px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        button { width:100%; padding:15px; margin:10px 0; font-size:18px; background: #6b3e26; color: white; border:none; border-radius:8px; cursor: pointer; }
        button:hover { background: #8c5a3c; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>RoboCoffee</h1>
        <p>Selecciona tu rol:</p>
        <a href="/cliente"><button>Cliente</button></a>
        <a href="/trabajador"><button>Trabajador</button></a>
      </div>
    </body>
    </html>
    """

# 3. Selección de mesa para clientes
def cliente_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>RoboCoffee - Mesa</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #fffbe6; padding:20px; }
        h1 { color: #6b3e26; }
        .card { background: white; max-width: 350px; margin: 40px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        button { width:100%; padding:15px; margin:10px 0; font-size:18px; background: #6b3e26; color:white; border:none; border-radius:8px; cursor: pointer; }
        button:hover { background:#8c5a3c; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Selecciona tu Mesa</h1>
        <a href="/menu?mesa=1"><button>Mesa 1</button></a>
        <a href="/menu?mesa=2"><button>Mesa 2</button></a>
        <a href="/menu?mesa=3"><button>Mesa 3</button></a>
        <a href="/menu?mesa=4"><button>Mesa 4</button></a>
      </div>
    </body>
    </html>
    """

# 4. Menú de cafés
def menu_page(mesa):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>RoboCoffee - Menú</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #fffbe6; padding: 20px; }}
        h1 {{ color: #6b3e26; font-size: 24px; }}
        .card {{ background: white; max-width: 400px; margin: 20px auto; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); text-align: left; }}
        label {{ font-weight: bold; color: #6b3e26; display: block; margin-top: 15px; }}
        input[type="text"] {{ width: 100%; box-sizing: border-box; padding: 12px; margin-top: 5px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; }}
        .options {{ margin-top: 15px; }}
        .options label {{ font-weight: normal; display: block; margin: 10px 0; font-size: 18px; cursor: pointer; }}
        button {{ width: 100%; padding: 15px; margin-top: 25px; font-size: 18px; background: #6b3e26; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }}
        button:hover {{ background: #8c5a3c; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1 style="text-align:center;">Menú - Mesa {mesa}</h1>
        <form action="/pedido" method="get">
          <input type="hidden" name="mesa" value="{mesa}">
          
          <label for="nombre">Tu Nombre:</label>
          <input type="text" id="nombre" name="nombre" placeholder="Ej. Carlos" required>
          
          <label>Selecciona tu café:</label>
          <div class="options">
            <label><input type="radio" name="cafe" value="Espresso" required> ☕ Espresso</label>
            <label><input type="radio" name="cafe" value="Latte"> 🥛 Latte</label>
            <label><input type="radio" name="cafe" value="Capuccino"> ☕ Cappuccino</label>
            <label><input type="radio" name="cafe" value="Americano"> 🍵 Americano</label>
          </div>
          
          <button type="submit">Confirmar Pedido</button>
        </form>
      </div>
    </body>
    </html>
    """

# 5. Panel del trabajador con botón "Entregar"
def trabajador_page(mensaje=""):
    info_robot = "Robot entregador: Modelo RC-01, batería 85%, listo para servicio."
    robot_ocupado = any(p["estado"] in ROBOT_BUSY_STATES for p in pedidos)
    pedidos_html = "<ul style='list-style-type: none; padding: 0;'>"
    if not pedidos:
        pedidos_html += "<p>No hay pedidos pendientes.</p>"
    else:
        for p in pedidos:
            if p["estado"] == "pendiente":
                if robot_ocupado:
                    accion_html = ""
                    estado_texto = "Pendiente; el robot está ocupado o requiere revisión"
                else:
                    accion_html = """
                    <a href="/entregar?id={}" style="text-decoration: none;">
                      <button style="background: #2e7d32; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; margin-top: 5px;">Entregar</button>
                    </a>
                    """.format(p["id"])
                    estado_texto = "Pendiente"
            elif p["estado"] == "saliendo":
                accion_html = ""
                estado_texto = "El robot va hacia la entrega"
            elif p["estado"] == "esperando_cliente":
                accion_html = ""
                estado_texto = "Esperando confirmación del cliente"
            elif p["estado"] == "regresando":
                accion_html = ""
                estado_texto = "El robot está regresando"
            elif p["estado"] == "completado":
                accion_html = ""
                estado_texto = "Entrega completada"
            else:
                accion_html = ""
                estado_texto = "Requiere revisión del trabajador"
            pedidos_html += f"""
            <li style="background: #fafafa; margin-bottom: 12px; padding: 12px; border-radius: 8px; border: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
              <div>
                <b>Mesa {p['mesa']}</b> - {p['nombre']}: <b>{p['cafe']}</b> <small>(ID #{p['id']})</small>
                <div>{estado_texto}</div>
              </div>
              {accion_html}
            </li>
            """
    pedidos_html += "</ul>"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>RoboCoffee - Trabajador</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta http-equiv="refresh" content="5">
      <style>
        body {{ font-family: Arial, sans-serif; background:#f0f0f0; padding:20px; text-align: center; }}
        h1, h2 {{ color:#6b3e26; }}
        .panel {{ background:#fff; max-width: 650px; margin: 0 auto; padding:20px; border-radius:10px; box-shadow:0 0 10px #aaa; text-align: left; }}
        button.back-btn {{ width:100%; padding:12px; margin-top:20px; font-size:16px; background:#6b3e26; color:white; border:none; border-radius:8px; cursor:pointer; }}
        button.back-btn:hover {{ background:#8c5a3c; }}
      </style>
    </head>
    <body>
      <div class="panel">
        <h1>Panel de Trabajador</h1>
        <p>{mensaje}</p>
        <h2>Pedidos Recibidos:</h2>
        {pedidos_html}
        <h2>Información del robot:</h2>
        <p>{info_robot}</p>
        <a href="/login"><button class="back-btn">Volver al Login</button></a>
      </div>
    </body>
    </html>
    """

# 6. Página de confirmación de pedido
def pedido_page(cafe, mesa, nombre):
    global pedidos, contador_pedidos
    mesa_numero = int(mesa)
    if mesa_numero not in DELIVERY_DISTANCES_MM:
        raise ValueError("Mesa no válida: {}".format(mesa))
    contador_pedidos += 1
    pedidos.append({
        "id": contador_pedidos,
        "mesa": mesa_numero,
        "nombre": nombre,
        "cafe": cafe,
        "estado": "pendiente",
    })
    led.value(1)
    return pedido_estado_page(contador_pedidos)


def pedido_estado_page(order_id, mensaje=""):
    pedido = buscar_pedido(order_id)
    if pedido is None:
        return """
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>Pedido no encontrado</title></head>
        <body><h1>No se encontró este pedido.</h1></body></html>
        """

    estado = pedido["estado"]
    if estado == "pendiente":
        estado_texto = "Tu pedido está confirmado; espera a que el trabajador lo envíe."
    elif estado == "saliendo":
        estado_texto = "El robot va en camino con tu café."
    elif estado == "esperando_cliente":
        estado_texto = "El robot llegó. Cuando tengas tu café, confirma abajo."
    elif estado == "regresando":
        estado_texto = "Gracias. El robot está regresando a su punto de partida."
    elif estado == "completado":
        estado_texto = "¡Gracias! El robot regresó y la entrega quedó completada."
    else:
        estado_texto = "Hubo un problema con el movimiento. Avisa al trabajador."

    if estado == "esperando_cliente":
        boton_confirmacion = """
        <a href="/recibi?id={}">
          <button>Recibí mi café</button>
        </a>
        """.format(order_id)
    else:
        boton_confirmacion = '<button disabled>Recibí mi café</button>'

    refresh = ""
    if estado not in ("completado", "error"):
        refresh = '<meta http-equiv="refresh" content="3;url=/pedido_estado?id={}">'.format(
            order_id
        )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Estado de tu pedido</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      {refresh}
      <style>
        body {{ font-family: Arial, sans-serif; text-align:center; background:#e6ffe6; padding:20px; }}
        h1 {{ color:#2e7d32; }}
        .card {{ background: white; max-width: 400px; margin: 50px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
        button {{ width:100%; padding:15px; margin-top:20px; font-size:18px; background:#2e7d32; color:white; border:none; border-radius:8px; cursor:pointer; }}
        button:hover {{ background:#388e3c; }}
        button:disabled {{ background:#888; cursor:default; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Estado del pedido #{order_id}</h1>
        <p><b>{pedido['nombre']}</b> (Mesa {pedido['mesa']}), tu café <b>{pedido['cafe']}</b>.</p>
        <p>{estado_texto}</p>
        <p>{mensaje}</p>
        {boton_confirmacion}
        <a href="/cliente"><button>Hacer otro pedido</button></a>
      </div>
    </body>
    </html>
    """

# --- Servidor del Servidor Principal ---
try:
    server_socket.close()
except:
    pass

addr = usocket.getaddrinfo("0.0.0.0", 80)[0][-1]
server_socket = usocket.socket()
server_socket.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
server_socket.bind(addr)
server_socket.listen(5)

print("Servidor RoboCoffee activo en http://", wlan.ifconfig()[0])

while True:
    cl = None
    try:
        cl, addr = server_socket.accept()
        cl.settimeout(2.0)
        
        request = cl.recv(1024).decode('utf-8', 'ignore')
        if not request:
            cl.close()
            continue
            
        request_line = request.split("\r\n")[0] if request else ""
        print("Solicitud:", request_line)

        response = login_page()
        redirect_to = None

        if request_line == "GET /" or request_line.startswith("GET / ") or "GET /index" in request_line:
            response = welcome_page()
        elif "GET /login" in request_line:
            response = login_page()
        elif "GET /cliente" in request_line:
            response = cliente_page()
        elif "GET /trabajador" in request_line:
            response = trabajador_page()
        elif "GET /pedido_estado?" in request_line:
            try:
                params = request_line.split(" ")[1]
                query = params.split("?", 1)[1]
                order_id = int(query.split("id=", 1)[1].split("&")[0])
                response = pedido_estado_page(order_id)
            except Exception as e:
                print("Error al consultar el pedido:", e)
                response = "<h1>No se pudo consultar el pedido</h1>"
        elif "GET /entregar?" in request_line:
            try:
                params = request_line.split(" ")[1]
                query = params.split("?", 1)[1]
                order_id = int(query.split("id=", 1)[1].split("&")[0])
                redirect_to = "/trabajador"
                pedido = buscar_pedido(order_id)
                if pedido is None:
                    raise ValueError("No existe el pedido #{}".format(order_id))
                robot_ocupado = any(
                    p is not pedido and p["estado"] in ROBOT_BUSY_STATES
                    for p in pedidos
                )
                if pedido["estado"] == "pendiente" and not robot_ocupado:
                    pedido["estado"] = "saliendo"
                    try:
                        viaje = enviar_orden_robot(int(pedido["mesa"]))
                        pedido.update(viaje)
                        pedido["estado"] = "esperando_cliente"
                    except Exception as e:
                        pedido["estado"] = "error"
                        print("Error al enviar el robot:", e)
                response = trabajador_page()
            except Exception as e:
                print("Error al entregar pedido:", e)
                response = trabajador_page()
        elif "GET /recibi?" in request_line:
            try:
                params = request_line.split(" ")[1]
                query = params.split("?", 1)[1]
                order_id = int(query.split("id=", 1)[1].split("&")[0])
                redirect_to = "/pedido_estado?id={}".format(order_id)
                pedido = buscar_pedido(order_id)
                if pedido is None:
                    raise ValueError("No existe el pedido #{}".format(order_id))
                if pedido["estado"] != "esperando_cliente":
                    response = pedido_estado_page(
                        order_id, "Todavía no se puede confirmar la entrega."
                    )
                else:
                    pedido["estado"] = "regresando"
                    try:
                        regresar_robot_al_origen(pedido)
                        pedido["estado"] = "completado"
                    except Exception as e:
                        pedido["estado"] = "error"
                        print("Error al regresar el robot:", e)
                    response = pedido_estado_page(order_id)
            except Exception as e:
                print("Error al confirmar recepción:", e)
                response = "<h1>No se pudo confirmar la recepción</h1>"
        elif "GET /menu?mesa=" in request_line:
            try:
                params = request_line.split(" ")[1]
                mesa = params.split("mesa=")[1].split("&")[0]
                response = menu_page(mesa)
            except:
                response = menu_page("1")
        elif "GET /pedido?" in request_line:
            try:
                params = request_line.split(" ")[1]
                query = params.split("?")[1]
                pairs = query.split("&")
                data = {}
                for pair in pairs:
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        data[k] = v.replace("+", " ").replace("%20", " ").replace("%C3%A9", "é").replace("%C3%AD", "í").replace("%C3%B3", "ó").replace("%C3%A1", "á").replace("%C3%BA", "ú").replace("%C3%B1", "ñ")
                mesa = data.get("mesa", "1")
                nombre = data.get("nombre", "Invitado")
                cafe = data.get("cafe", "Espresso")
                response = pedido_page(cafe, mesa, nombre)
            except Exception as e:
                print("Error en pedido:", e)
                response = "<h1>Error en el pedido</h1>"

        if redirect_to:
            cl.send(
                "HTTP/1.1 303 See Other\r\n"
                "Location: {}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n"
                "Content-Length: 0\r\n\r\n".format(redirect_to)
            )
        else:
            cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n")
            cl.send(response)
        cl.close()
        
    except Exception as e:
        if cl:
            try:
                cl.close()
            except:
                pass
