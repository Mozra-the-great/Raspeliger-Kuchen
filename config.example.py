"""
Zentrale Konfiguration - Vorlage ohne echte Credentials.
Kopieren als config.py und Werte anpassen.
"""

# ============================================
# DATENBANK (MariaDB auf Pi 206)
# ============================================
DB_CONFIG = {
    "host": "192.168.1.206",
    "port": 3306,
    "user": "raspi-db",
    "password": "DEIN_PASSWORT",
    "database": "raumverwaltung",
    "charset": "utf8mb4"
}

# ============================================
# FLASK SERVER (läuft auf Pi 4)
# ============================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
DEBUG = False

# ============================================
# MQTT (Mosquitto auf Pi 206)
# ============================================
MQTT_CONFIG = {
    "host": "192.168.1.206",
    "port": 1883,
    "username": "raspi",
    "password": "DEIN_MQTT_PASSWORT",
    "keepalive": 60
}

# Welche Topics sollen abonniert werden?
MQTT_TOPICS = [
    "sensor/+/temperatur",
    "sensor/+/luftfeuchte",
    "sensor/+/co2",
    "room/+/occupied",
    "state/+/licht",
    "state/+/rollo",
    "state/+/klima_modus",
    "state/+/klima_soll",
]

# Haupt-Raum für Dashboard-Hauptanzeige
HAUPT_RAUM = "raum_a"

# ============================================
# MODI
# ============================================
MOCK_SENSORS = False   # True = Zufallswerte statt MQTT (für lokale Entwicklung)
MQTT_ENABLED = True

# ============================================
# SENSOR-SCHWELLWERTE
# ============================================
SCHWELLWERTE = {
    "temperatur": {"ok": (19, 24), "warn": (17, 26)},
    "luftfeuchte": {"ok": (40, 60), "warn": (30, 70)},
    "co2":         {"ok": (0, 1000), "warn": (0, 1400)},
}
