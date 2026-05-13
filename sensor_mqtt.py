#!/usr/bin/env python3
"""
MQTT-Sender fuer Pi 33 (Sensor-Pi)
Nutzt die bestehende DHT22-Klasse und den SCD30 per I2C.
Sendet die Werte jede Sekunde an den MQTT-Broker auf Pi 206.
"""

import time
import sys
import signal
import paho.mqtt.client as mqtt

# ============================================
# KONFIGURATION
# ============================================
MQTT_HOST = "192.168.1.206"
MQTT_PORT = 1883
MQTT_USER = "raspi"
MQTT_PASS = "raspi"

RAUM_ID = "raum_a"
SEND_INTERVAL = 1           # Sekunden
DHT22_GPIO = 4
PRIMARY_TEMP_SENSOR = "scd30"  # "scd30" oder "dht22"

# ============================================
# SENSOREN INITIALISIEREN
# ============================================
print("Initialisiere Sensoren...")

dht_sensor = None
pi = None
try:
    import pigpio
    import DHT22
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpio daemon nicht erreichbar - DHT22 deaktiviert")
        pi = None
    else:
        pi.set_pull_up_down(DHT22_GPIO, pigpio.PUD_UP)
        dht_sensor = DHT22.sensor(pi, DHT22_GPIO)
        time.sleep(1)
        print(f"DHT22 bereit (GPIO{DHT22_GPIO})")
except Exception as e:
    print(f"DHT22 Fehler: {e}")
    dht_sensor = None

scd_sensor = None
try:
    import board
    import adafruit_scd30
    i2c = board.I2C()
    scd_sensor = adafruit_scd30.SCD30(i2c)
    print("SCD30 bereit (I2C)")
    time.sleep(2)
except Exception as e:
    print(f"SCD30 Fehler: {e}")
    scd_sensor = None

if not dht_sensor and not scd_sensor:
    print("Kein Sensor verfuegbar. Abbruch.")
    sys.exit(1)

# ============================================
# SENSOR-LESEFUNKTIONEN
# ============================================
def read_dht22():
    if not dht_sensor:
        return None, None
    for versuch in range(10):
        try:
            dht_sensor.trigger()
            time.sleep(0.5)
            t = dht_sensor.temperature()
            h = dht_sensor.humidity()
            if t != -999 and h > 0:
                return round(t, 1), round(h, 1)
        except Exception:
            pass
        time.sleep(0.3)
    return None, None

def read_scd30():
    if not scd_sensor:
        return None, None, None
    for _ in range(10):
        if scd_sensor.data_available:
            try:
                t = round(scd_sensor.temperature, 1)
                h = round(scd_sensor.relative_humidity, 1)
                c = round(scd_sensor.CO2)
                return t, h, c
            except Exception as e:
                print(f"SCD30-Lesefehler: {e}")
                return None, None, None
        time.sleep(0.5)
    return None, None, None

# ============================================
# MQTT VERBINDEN
# ============================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"MQTT verbunden mit {MQTT_HOST}")
    else:
        print(f"MQTT-Verbindung fehlgeschlagen (Code {rc})")

try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.on_connect = on_connect
client.username_pw_set(MQTT_USER, MQTT_PASS)

print(f"Verbinde mit {MQTT_HOST}:{MQTT_PORT} ...")
try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"Konnte nicht zum Broker verbinden: {e}")
    sys.exit(1)

# ============================================
# GRACEFUL SHUTDOWN
# ============================================
def shutdown(signum, frame):
    print("\nStoppe...")
    try:
        if dht_sensor:
            dht_sensor.cancel()
        if pi and pi.connected:
            pi.stop()
    except Exception:
        pass
    client.loop_stop()
    client.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# ============================================
# HAUPT-LOOP
# ============================================
print(f"Sende alle {SEND_INTERVAL}s als Raum '{RAUM_ID}' (STRG+C zum Beenden)")

base = f"sensor/{RAUM_ID}"

while True:
    dht_t, dht_h = read_dht22()
    scd_t, scd_h, scd_c = read_scd30()

    if PRIMARY_TEMP_SENSOR == "scd30" and scd_t is not None:
        prim_t, prim_h = scd_t, scd_h
    elif PRIMARY_TEMP_SENSOR == "dht22" and dht_t is not None:
        prim_t, prim_h = dht_t, dht_h
    else:
        prim_t = scd_t if scd_t is not None else dht_t
        prim_h = scd_h if scd_h is not None else dht_h

    if prim_t is not None:
        client.publish(f"{base}/temperatur", str(prim_t))
    if prim_h is not None:
        client.publish(f"{base}/luftfeuchte", str(prim_h))
    if scd_c is not None:
        client.publish(f"{base}/co2", str(scd_c))
    if dht_t is not None:
        client.publish(f"{base}/dht22/temperatur", str(dht_t))
        client.publish(f"{base}/dht22/luftfeuchte", str(dht_h))
    if scd_t is not None:
        client.publish(f"{base}/scd30/temperatur", str(scd_t))
        client.publish(f"{base}/scd30/luftfeuchte", str(scd_h))

    t_str = f"{prim_t}C" if prim_t is not None else "-"
    h_str = f"{prim_h}%" if prim_h is not None else "-"
    c_str = f"{scd_c}ppm" if scd_c is not None else "-"
    print(f"{RAUM_ID}: {t_str} | {h_str} | {c_str}")

    time.sleep(SEND_INTERVAL)
