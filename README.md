# Raspeliger-Kuchen

Unser Raspberry Pi Challenge Projekt — ein dezentrales IoT-System zur intelligenten Raumverwaltung mit Buchungssystem, KI-basierter Personenerkennung und automatischer Komfortsteuerung.

---

## Projektbeschreibung

Das System verwaltet vier Meetingräume (A–D) und verbindet Buchungslogik, Umgebungssensorik und Raumsteuerung in einer einheitlichen Plattform. Kernfunktionen:

- **Raumbuchung** über ein Web-Dashboard (Touchscreen-Kiosk + Browser)
- **KI-Personenerkennung** per Kamera und Hailo-8L AI Accelerator (YOLOv8s)
- **Automatische Komfortsteuerung** Licht, Rollos und Klimaanlage schalten sich beim Betreten automatisch ein
- **No-Show Auto-Release** nicht angetretene Buchungen werden nach Timeout freigegeben
- **Live-Sensordaten** Temperatur, Luftfeuchte und CO₂ pro Raum mit Handlungsempfehlungen
- **Home Assistant Automationen** für die Komfortlogik

---

## Hardware

| Node | IP | Rolle | Hardware-Besonderheit |
|---|---|---|---|
| Pi 1 — Webserver | 192.168.1.211 | Flask-Webserver, REST-API, Hailo-8L KI (Personenerkennung) | Hailo-8L M.2 HAT+ (Firmware 4.23.0, identifiziert als "Hailo-8") |
| Pi 2 — Datenbank | 192.168.1.206 | MariaDB 11.8.6, Mosquitto MQTT-Broker, Raumfreigabe-Logik | — |
| Pi 3 — Sensorik | 192.168.1.233 | DHT22, SCD30 (CO₂), Kamera-Modul, UDP-Stream | I²C (`dtparam=i2c_arm=on`), CSI-Kamera (`camera_auto_detect=1`) |
| Pi 4 — Automatisierung | 192.168.1.210 | Home Assistant OS (Port 8123) | kein SSH (Web-UI + File-Editor-Add-on) |
| Pi 5 — GUI | 192.168.1.232 | Touchscreen-Kiosk (Chromium, labwc/Wayland) | Touchscreen WaveShare WS170120 (800×480, kapazitiv, HDMI-A-2) |

Netzwerk: alle Pis statisch über NetworkManager (`Wired connection 1`), Gateway 192.168.1.3, DNS 1.1.1.1 + 8.8.8.8.

---

## Tech-Stack

- **Backend:** Python / Flask 3.0.0, MariaDB 11.8.6, `paho-mqtt`, `pymysql`
- **Frontend:** Vanilla JS, HTML/CSS (Dark Theme, Kiosk-optimiert mit `clamp()`/`vw`/`vh`)
- **IoT:** MQTT (Mosquitto), Home Assistant OS
- **KI:** YOLOv8s (`yolov8s_h8l.hef`) auf Hailo-8L Accelerator (`hailort==4.23.0`)
- **Kamera:** `rpicam-vid` (1080p@30fps UDP) → `ffmpeg` (5 fps JPEG)
- **Sensoren:** DHT22 (Temp/Feuchte via `pigpio`), SCD30 (Temp/Feuchte/CO₂ via I²C/`adafruit-circuitpython-scd30`)
- **Wetter:** Open-Meteo API (Stuttgart)
- **OS:** Raspberry Pi OS Bookworm/Trixie 64-bit (Pi 1/2/3/5), Home Assistant OS (Pi 4), Pi 5 mit Wayland-Compositor `labwc`

---

## Repository-Struktur

```
.
├── app.py, person_detection.py, debug_server.py    Pi 1: Flask + KI
├── sensor_mqtt.py, DHT22.py, test_*.py             Pi 3: Sensor-Skripte
├── config.example.py                               Pi 1: Config-Template
├── *.service                                       systemd Units (Pi 1 + Pi 3)
├── configuration.yaml, automations.yaml,           Pi 4: Home Assistant
│   scripts.yaml, scenes.yaml, secrets.example.yaml
├── ha_automations_prod_v1.yaml,                    Pi 4: Komfort-Automationen
│   ha_automations_test_v2.yaml
├── schema.sql, raeume_seed.sql                     Pi 2: MariaDB
├── requirements_pi1.txt, requirements_pi3.txt      Pip-Pakete
├── install_emoji.sh                                Pi 5: Setup-Skript
├── README.md, ARCHITECTURE.md                      Doku
│
├── static/                                         Pi 1: Flask-Assets
│   ├── style.css, detail.css
│   └── dashboard.js, detail.js
├── templates/                                      Pi 1: Flask-Templates
│   ├── index.html
│   └── raum_detail.html
├── pi2/mosquitto/                                  Pi 2: MQTT-Config
│   ├── mosquitto.conf
│   └── conf.d/default.conf
├── pi3/                                            Pi 3: Boot-Config
│   └── boot_config.txt
└── pi5/                                            Pi 5: Kiosk-Setup
    ├── labwc-autostart
    ├── labwc-environment
    └── labwc-rc.xml
```

---

## Architektur

Eine vollständige Beschreibung aller Komponenten, Datenflüsse, MQTT-Topics und Setup-Schritte findet sich in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

`DHT22.py` enthält Code aus den pigpio-Beispielen (Joan2937, Public Domain).

---

*Robin, Nick, Niklas, Moritz — 2026*
