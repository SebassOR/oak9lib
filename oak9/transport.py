"""Low-level TCP transport for the OAK9 firmware's line-based command
protocol (`command key=value ...` -> `OK ...` / `ERROR ...`).
"""

import socket
import threading


def _coerce(value):
    if value in ("true", "false"):
        return value == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_response(line):
    """Parse a raw "OK <cmd> key=value ..." / "ERROR <cmd> CODE msg" line."""
    tokens = line.split(" ")
    result = {"ok": tokens[0] == "OK", "raw_line": line}

    if len(tokens) > 1:
        result["command"] = tokens[1]

    if not result["ok"]:
        if len(tokens) > 2:
            result["error_code"] = tokens[2]
        if len(tokens) > 3:
            result["message"] = " ".join(tokens[3:])
        return result

    for token in tokens[2:]:
        if "=" in token:
            key, _, value = token.partition("=")
            result[key] = _coerce(value)

    return result


class Transport:
    def __init__(self, host, port=8080, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._buffer = b""
        self._lock = threading.Lock()
        self.connect()

    def connect(self):
        self.close()
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        # Sin esto, Nagle (buffer del lado emisor) choca con los ACKs
        # retrasados del ESP32 en este protocolo de paquetes chicos y
        # frecuentes -- produce estancamientos esporadicos de 200-500ms
        # en un round-trip que normalmente tarda unos pocos ms.
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._buffer = b""

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __repr__(self):
        state = "connected" if self._sock is not None else "closed"
        return f"Transport({self.host}:{self.port}, {state})"

    def _read_line(self):
        while b"\n" not in self._buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("El robot cerró la conexión")
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line.decode("utf-8", errors="replace").strip()

    def send(self, command, **kwargs):
        """Send one command line, return the parsed response dict.

        >>> transport.send("motor.pwm", left=100, right=-100)
        """
        parts = [command]
        for key, value in kwargs.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            parts.append(f"{key}={value}")
        line = " ".join(parts)

        with self._lock:
            self._sock.sendall((line + "\n").encode("utf-8"))
            response = self._read_line()

        return parse_response(response)
