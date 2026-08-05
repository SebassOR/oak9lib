class Wifi:
    """SSID/password persistentes; wifi.set requiere reboot manual
    para aplicarse (no reconecta en caliente)."""

    def __init__(self, transport):
        self._transport = transport

    def get(self):
        return self._transport.send("wifi.get")

    def set(self, ssid, password):
        return self._transport.send("wifi.set", ssid=ssid, password=password)
