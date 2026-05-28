# Raspeliger-Kuchen

Unser Raspberry Pi Challenge Projekt, ein dezentrales IoT-System zur intelligenten Raumverwaltung mit Buchungssystem, KI-basierter Personenerkennung und automatischer Komfortsteuerung.

---

## Projektbeschreibung

Das System verwaltet mehrere Meetingräume und verbindet Buchungslogik, Umgebungssensorik und Raumsteuerung in einer einheitlichen Plattform. Kernfunktionen:

- **Raumbuchung** über ein Web-Dashboard (Touchscreen-Kiosk + Browser)
- **KI-Personenerkennung** per Kamera und Hailo-8 AI Accelerator (YOLOv8s)
- **Automatische Komfortsteuerung** Licht, Rollos und Klimaanlage schalten sich beim Betreten automatisch ein
- **No-Show Auto-Release** nicht angetretene Buchungen werden nach Timeout freigegeben
- **Live-Sensordaten** Temperatur, Luftfeuchte und CO2 pro Raum mit Handlungsempfehlungen
- **Home Assistant Automationen** für die Komfortlogik

---

## Hardware

| Node | IP | Rolle |
|---|---|---|
| Pi 1 — Webserver | 192.168.1.211 | Flask-Webserver, REST-API, Hailo-8 KI (Personenerkennung) |
| Pi 2 — Datenbank | 192.168.1.206 | MariaDB, MQTT-Broker (Mosquitto), Raumfreigabe-Logik |
| Pi 3 — Sensorik | 192.168.1.233 | DHT22, SCD30 (CO2), Kamera-Modul, UDP-Stream |
| Pi 4 — Automatisierung | 192.168.1.210 | Home Assistant (Port 8123) |
| Pi 5 — GUI | 192.168.1.232 | Touchscreen-Kiosk (Chromium) |

---

## Tech-Stack

- **Backend:** Python / Flask, MariaDB, paho-mqtt
- **Frontend:** Vanilla JS, HTML/CSS (Dark Theme, Kiosk-optimiert)
- **IoT:** MQTT (Mosquitto), Home Assistant
- **KI:** YOLOv8s auf Hailo-8 AI Accelerator
- **Sensoren:** DHT22 (Temp/Feuchte), SCD30 (Temp/Feuchte/CO2)
- **Wetter:** Open-Meteo API (Stuttgart)

---

## Architektur

Eine vollständige Beschreibung aller Komponenten, Datenflüsse und Dateien findet sich in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

*Robin, Nick, Niklas, Moritz — 2026*
