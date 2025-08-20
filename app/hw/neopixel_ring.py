import board, neopixel

class NeoPixelRing:
    def __init__(self, n=16, pin=board.D18, brightness=0.3, auto_write=False):
        self.strip = neopixel.NeoPixel(pin, n, brightness=brightness, auto_write=auto_write, pixel_order=neopixel.GRB)
        self.n = n
        self.enabled = True
        self.color_white = (255, 255, 255)
        self.color_warn  = (255, 0, 0)

    def set_enabled(self, en: bool):
        self.enabled = en
        if not en:
            self.off()

    def set_brightness(self, b: float):
        self.strip.brightness = max(0.0, min(1.0, b))
        self.strip.show()

    def set_colors(self, white_hex: str, warn_hex: str):
        def to_rgb(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0,2,4))
        self.color_white = to_rgb(white_hex)
        self.color_warn  = to_rgb(warn_hex)

    def fill(self, rgb):
        if not self.enabled: return
        self.strip.fill(rgb); self.strip.show()

    def off(self):
        self.strip.fill((0,0,0)); self.strip.show()