OAK_LCD_COLS = 21


class Indicators:
    def __init__(self, transport):
        self._transport = transport

    def tone(self, hz, ms):
        return self._transport.send("buzzer.tone", hz=hz, ms=ms)

    def lcd_print(self, row, col, text):
        """Escribe `text` en la LCD.

        El router del firmware separa argumentos por espacios, así que
        los espacios en `text` se codifican como `_` (el firmware ya
        los traduce de vuelta al dibujar) — igual que hace
        server/oak_notify.py. No se rellena ni se limpia la fila; si
        el texto nuevo es más corto que el anterior, los caracteres
        viejos que sobren se quedan en pantalla.
        """
        encoded = text.replace(" ", "_")[:OAK_LCD_COLS]
        return self._transport.send(
            "lcd.print", row=row, col=col, text=encoded
        )
