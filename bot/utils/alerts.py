import sys
import os

# Generic sound function
def _play(sound):
    if sys.platform == "darwin":   # macOS
        os.system(f'afplay /System/Library/Sounds/{sound}.aiff')
    elif sys.platform == "win32":  # Windows
        import winsound
        winsound.MessageBeep()
    else:  # Linux
        os.system('paplay /usr/share/sounds/freedesktop/stereo/complete.oga')

# Alerts
def buy_alert():
    _play("Ping")   # Change "Ping" to "Glass", "Submarine", etc.

def sell_alert():
    _play("Funk")   # Different sound for SELL
