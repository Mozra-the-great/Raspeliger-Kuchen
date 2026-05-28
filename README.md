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

| Node | Hardware | Rolle |
|---|---|---|
| Pi 1 | Raspberry Pi 5 + Hailo-8 HAT | KI-Personenerkennung |
| Pi 2 | Raspberry Pi + Touchscreen | Kiosk-Display |
| Pi 3 | Raspberry Pi | Kamera-Streamer |
| Pi 4 | Raspberry Pi 4 | Flask-Backend + MariaDB |
| Pi 33 | Raspberry Pi | Sensor-Node (DHT22 + SCD30) |
| Pi 206 | Raspberry Pi | MQTT Broker + Home Assistant |

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
