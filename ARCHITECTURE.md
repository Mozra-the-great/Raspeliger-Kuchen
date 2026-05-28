# Architektur: Raspeliger-Kuchen

Dezentrales IoT-System zur intelligenten Raumverwaltung mit Buchungen, KI-basierter Personenerkennung und automatischer Komfortsteuerung. Das System verteilt sich auf mehrere Raspberry Pi Nodes, die über MQTT kommunizieren, mit Home Assistant als zentraler Automationsschicht und Flask als Backend.

---

## Systemübersicht

```
┌──────────────────────────────────────────┐
│  Pi 33 (192.168.1.233)                   │
│  kamera-stream.service:                  │
│    rpicam-vid 1080p@30fps                │
│    → UDP 192.168.1.211:9000              │
│  sensor.service:                         │
│    sensor_mqtt.py                        │
│    → MQTT sensor/raum_a/*               │
└────────┬─────────────────────────────────┘
         │ UDP :9000
┌────────▼──────────────────────────────────────┐
│  Pi 4 (192.168.1.211, raspberrypi-11)          │
│                                                │
│  ffmpeg-stream.service:                        │
│    ffmpeg udp://@:9000 → /tmp/frame.jpg @5fps  │
│                                                │
│  person-detection.service:                     │
│    person_detection.py                         │
│    /tmp/frame.jpg → Hailo-8 YOLOv8s            │
│    → /tmp/detections.json                      │
│    → MQTT room/raum_a/occupied                 │
│                                                │
│  debug-server.service → debug_server.py :5001  │
│  dashboard.service    → app.py :5000           │
└────────┬───────────────────────────────────────┘
         │ MQTT (room/*, sensor/*, cmd/*, state/*)
┌────────▼──────────────────────────────────┐
│  Pi 206 (192.168.1.206, raspberrypi-6)    │
│  MQTT Broker :1883 + Home Assistant       │
│  MariaDB :3306 (DB: raumverwaltung)       │
│  configuration.yaml, automations.yaml     │
│  ha_automations_prod_v1.yaml              │
└────────┬──────────────────────────────────┘
         │ HTTP
┌────────▼──────────────────────┐
│  Pi 2 (192.168.1.210 od. 232) │
│  Touchscreen Kiosk             │
│  Chromium → http://Pi4:5000   │
└───────────────────────────────┘
```

---

## Netzwerk & IP-Adressen

| Node | IP | Rolle |
|---|---|---|
| Pi 2 | 192.168.1.210 oder .232 | Touchscreen Kiosk (Chromium → Pi 4 :5000) |
| Pi 4 | 192.168.1.211 | Flask :5000 + Hailo-8 KI (person_detection.py) |
| Pi 33 | 192.168.1.233 | Sensor-Node (DHT22/SCD30) + Kamera-Streamer (= "Pi 3") |
| Pi 206 | 192.168.1.206 | MQTT Broker :1883 + Home Assistant |

---

## MQTT Topic-Schema

```
# Anwesenheit (Kamera-KI → app.py/HA)
room/raum_a/occupied          → "true" | "false"  (retain=true bei Release)

# Sensordaten (Sensor-Pi → app.py)
sensor/raum_a/temperatur      → float (°C)
sensor/raum_a/luftfeuchte     → float (%)
sensor/raum_a/co2             → int (ppm)
sensor/raum_a/dht22/temperatur → float (Rohwert DHT22)
sensor/raum_a/scd30/temperatur → float (Rohwert SCD30)

# Steuerbefehle (app.py → Hardware via HA)
cmd/raum_a/licht              ← "on" | "off"
cmd/raum_a/rollo              ← "up" | "down" | "stop"
cmd/raum_a/klima_modus        ← "off" | "heat" | "cool"
cmd/raum_a/klima_soll         ← "15"-"30" (int als String)

# Hardware-State-Feedback (Hardware → app.py)
state/raum_a/licht            → aktueller Zustand
state/raum_a/rollo            → aktueller Zustand
```

---

## Flask REST API (Pi 4 :5000)

Verifiziert aus `app.py`. Flask-Verzeichnis auf Pi 4: `/home/raspi/dashboard_mariadb/`

```
GET  /
     → render_template("index.html")

GET  /raum/<raum_id>
     → render_template("raum_detail.html", raum_id, raum_name)

GET  /api/raeume
     → [{name, belegt, nutzer, bis, naechste_buchung, anwesenheit}]
     # Sonderfall: MQTT occupied=true ohne Buchung → nutzer="Anwesend"

POST /buchen
     ← {raum, nutzer, start, ende}
     → {status: "ok"|"error", id|nachricht}

POST /buchen-schnell
     ← {raum, dauer_minuten, nutzer}
     → {status, id, start, ende}

GET  /api/raum/<raum_name>/buchungen?datum=YYYY-MM-DD
     → [{id, nutzer, start, ende, start_voll, ende_voll, status}]
     # status: "aktiv" | "geplant" | "vorbei"

GET  /api/raum/<raum_id>/anwesenheit
     → {occupied: bool|null, last_update: "YYYY-MM-DD HH:MM:SS"|null, alter_sek: int|null}

GET  /api/raum/<raum_name>/status
     → {licht, rollo, klima_modus, klima_soll, checkin, letzte_aenderung}

POST /api/raum/<raum_name>/licht
     ← {action: "on"|"off"|"toggle"}
     → {status: "ok", state: {...}}

POST /api/raum/<raum_name>/rollo
     ← {action: "up"|"stop"|"down"}
     → {status: "ok", state: {...}}

POST /api/raum/<raum_name>/klima
     ← {modus: "heat"|"cool"|"off"}  ODER  {soll: int (15-30)}
     → {status: "ok", state: {...}}

POST /api/raum/<raum_name>/checkin
     → {status: "ok", state: {...}}
     # Achtung: toggled nur In-Memory-Flag, schreibt NICHT checked_in_at in DB

GET  /api/sensoren
     → {temperatur, luftfeuchte, co2, zeitstempel, quelle, raum}
     # Liest HAUPT_RAUM aus config.py

GET  /api/sensoren/<raum_id>
     → {temperatur, luftfeuchte, co2, zeitstempel, raum}

GET  /api/raum/<raum_name>/verlauf
     → [{zeit, temperatur, luftfeuchte, co2}]  (24h, Demo-Daten)

GET  /api/wetter
     → {ort, current, forecast, tag, abgerufen}

GET  /api/verkehr
     → {status: "gruen"|"gelb"|"rot", label, beschreibung, details}

GET  /api/status
     → {zeit, db: "ok"|"error: ...", mqtt: {aktiv, raeume_mit_daten}}

POST /stornieren/<buchung_id>
     → {status: "ok"|"error", nachricht}

POST /raum/<raum_name>/frei
     → {status: "ok", id}  (HA No-Show-Trigger)
     # Setzt storniert=TRUE + publisht room/raum_x/occupied="false" (retain)
```

---

## Dateien

### `app.py` — Flask-Backend (Pi 4)

Zentrale Backend-Anwendung. Version 3. Liegt auf Pi 4 unter `/home/raspi/dashboard_mariadb/app.py`.

**Importiert aus `config.py`:**
```python
DB_CONFIG      # pymysql Verbindungsparameter
FLASK_HOST     # z.B. "0.0.0.0"
FLASK_PORT     # z.B. 5000
DEBUG          # bool
MQTT_CONFIG    # {host, port, username, password, keepalive}
MQTT_TOPICS    # Liste von Topics zum Subscriben
HAUPT_RAUM     # z.B. "raum_a" — Standard-Raum für /api/sensoren
MOCK_SENSORS   # bool — liefert Zufallswerte statt MQTT-Daten
MQTT_ENABLED   # bool
SCHWELLWERTE   # dict (wird importiert, aber in app.py nicht direkt verwendet)
```

**In-Memory-Caches (Thread-sicher via Locks):**

| Cache | Typ | Inhalt |
|---|---|---|
| `sensor_cache` | `{raum: {typ: (wert, datetime)}}` | Letzte MQTT-Sensorwerte |
| `belegung_cache` | `{raum: bool}` | Letzter `occupied`-Status |
| `belegung_timestamps` | `{raum: datetime}` | Zeitstempel des letzten MQTT-Updates |
| `control_state` | `{raum: {licht, rollo, klima_modus, klima_soll, checkin}}` | Gerätezustände (In-Memory, kein DB-Persist) |
| `wetter_cache` | `{data, ts}` | Wetter-Response, 10-Min TTL |
| `verkehr_cache` | `{status, last_change, next_change}` | Demo-Verkehrsstatus |

**MQTT `on_message` Routing:**
```
topic prefix "sensor/" → sensor_cache aktualisieren
topic prefix "room/"   → belegung_cache + belegung_timestamps aktualisieren
                         + mark_checked_in() aufrufen (Auto-Check-in)
topic prefix "state/"  → control_state aktualisieren
```

**`mark_checked_in(raum_anzeige)`:**
Wird bei MQTT `occupied=true` automatisch aufgerufen. Schreibt `checked_in_at = NOW()` in die DB auf die aktive Buchung — verhindert Auto-Release.

**`auto_release_loop()` — Background-Thread:**
- Läuft als Daemon-Thread, prüft alle 30 Sekunden
- SQL: `storniert=0 AND abgelaufen=0 AND checked_in_at IS NULL AND start <= NOW() - INTERVAL 1 MINUTE AND ende >= NOW()`
- Setzt `abgelaufen=1` (nicht `storniert`) — logisch unterschiedlich vom manuellen Storno
- **Achtung Bug:** Kommentar sagt "10 Min", SQL-Query löst aber bereits nach **1 Minute** aus

**Doppelter Auto-Release-Mechanismus:**
1. `auto_release_loop()` im Backend (alle 30s, SQL-basiert, setzt `abgelaufen=1`)
2. HA-Automation `ha_automations_prod_v1.yaml` (10-Min Timeout, setzt `storniert=TRUE` via `/raum/x/frei`)
Beide können unabhängig feuern — keine Deduplizierung.

**`fetch_verkehr()` — reines Demo:**
Simuliert Verkehr mit zufälligen Gewichtungen nach Tageszeit. Keine echte Verkehrs-API.

**Raum-ID Konvention:**
- URL-Parameter `raum_name` = `"raum_a"` (Kleinbuchstaben, Unterstrich)
- Intern: `raum_name.replace("_", " ").title()` → `"Raum A"` (für DB + control_state Key)
- `belegung_cache` Key: `raum["name"].lower().replace(" ", "_")` → `"raum_a"`

**Bekannter Bug — manueller Check-In:**
`POST /api/raum/<raum>/checkin` toggled nur `control_state["checkin"]` im RAM.
`checked_in_at` in der DB wird **nicht** gesetzt.
Folge: Manueller Check-In über den Button verhindert den Auto-Release **nicht**.
Auto-Release läuft trotzdem. Nur MQTT-Anwesenheitserkennung schreibt in die DB.

---

### `config.py` — Konfiguration (Pi 4, **fehlt noch im Repo**)

Liegt unter `/home/raspi/dashboard_mariadb/config.py`. Enthält alle Secrets und Einstellungen die `app.py` importiert. **Muss noch aus dem Pi kopiert werden** (oder mit Dummy-Werten neu erstellt werden).

Erwartete Struktur:
```python
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "...",
    "password": "...",
    "database": "..."
}
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
DEBUG = False
MQTT_CONFIG = {
    "host": "192.168.1.206",
    "port": 1883,
    "username": "raspi",
    "password": "raspi",
    "keepalive": 60
}
MQTT_TOPICS = ["sensor/#", "room/#", "state/#"]
HAUPT_RAUM = "raum_a"
MOCK_SENSORS = False
MQTT_ENABLED = True
SCHWELLWERTE = { ... }
```

---

### `configuration.yaml` — Home Assistant Hauptkonfiguration

Definiert alle MQTT-basierten Entities und REST-Sensoren.

**MQTT Lights** (`light.licht_raum_a/b/c/d`)
- Command-Topic: `cmd/raum_x/licht`
- Payloads: `on` / `off`
- `optimistic: true` — HA schaltet UI sofort, unabhängig vom Hardware-Feedback
- QoS: 1

**MQTT Covers** (`cover.rollo_raum_a/b/c/d`)
- Topics: `cmd/raum_x/rollo`
- Payload open/close/stop: `up` / `down` / `stop`
- QoS: 1

**MQTT Climate** (`climate.klima_raum_a/b/c/d`)
- Modi: `off`, `heat`, `cool`
- Mode-Command-Topic: `cmd/raum_x/klima_modus`
- Temperatur-Soll-Topic: `cmd/raum_x/klima_soll`
- Temperatur-Ist-Topic: `sensor/raum_x/temperatur`
- Bereich: 15–30°C, Schrittweite 1°C

**MQTT Sensors** (nur Raum A vollständig aktiviert)
- `sensor.temperatur_raum_a` ← `sensor/raum_a/temperatur`
- `sensor.luftfeuchte_raum_a` ← `sensor/raum_a/luftfeuchte`
- `sensor.co2_raum_a` ← `sensor/raum_a/co2`

**MQTT Binary Sensors** (`binary_sensor.anwesenheit_raum_a/b/c/d`)
- Topic: `room/raum_x/occupied`, Payloads: `"true"` / `"false"`
- Device-Class: `occupancy`

**MQTT Switches** (`switch.raum_a/b/c/d_belegt`)
- Topic: `room/raum_x/occupied`, Retain: true

**REST-Sensoren** (`sensor.buchung_aktiv_a/b/c/d`)
- Endpoint: `GET http://192.168.1.211:5000/api/raeume`, Poll: 30s
- Jinja2-Logik: `on` wenn `belegt == true` UND `nutzer != "Anwesend"`
- `"Anwesend"` ist der Sonder-Nutzername den `app.py` setzt wenn MQTT occupied=true aber keine Buchung aktiv ist — damit triggern reine Kamera-Erkennungen keine HA-Buchungsautomation

**REST-Command** (`rest_command.raum_frei`)
- `POST http://192.168.1.211:5000/raum/{raum_id}/frei`

---

### `automations.yaml` — HA Basisautomation

Einfache No-Show Auto-Release (Basisversion, ohne Komfortsteuerung).

Trigger: `sensor.buchung_aktiv_a/b/c/d` → `"on"`
Ablauf: Wartet 10 Min auf Anwesenheit → bei Timeout: `rest_command.raum_frei` + Notification
Mode: `parallel`, max. 4

---

### `ha_automations_prod_v1.yaml` — Produktionsautomationen

Vollständige Komfort- + No-Show-Automationen für alle 4 Räume.

Pro Raum jeweils 3 Blöcke:

**"Buchung Komfort"** (Trigger: `buchung_aktiv_x` → `"on"`)
- Licht AN, Rollo AUF, Klima ein (Mai–Sept: Kühlen 22°C, sonst: Heizen 21°C)
- Wartet 10 Min auf Anwesenheit — bei Timeout: Alles aus
- Mode: `restart`

**"Person erkannt"** (Trigger: `anwesenheit_raum_x` → `"on"`)
- Identische Komfort-Aktionen
- Mode: `single`, `max_exceeded: silent`

**"Person weg"** (Trigger: `anwesenheit_raum_x` → `"off"`)
- Bedingung: keine aktive Buchung
- Delay 2 Min → erneute Prüfung → Alles aus
- Mode: `restart`

**"No-Show Auto-Release"** (zentral, alle 4 Räume)
- Raum-ID aus `trigger.entity_id` extrahiert
- 10 Min Timeout → `rest_command.raum_frei` + Notification
- Mode: `parallel`, max. 4

---

### `ha_automations_test_v2.yaml` — Testautomationen

Identisch zu Prod, aber mit drastisch kürzeren Timeouts.

| | Prod | Test |
|---|---|---|
| Buchung Komfort Timeout | 10 Min | 10 Sek |
| Person weg Delay | 2 Min | 30 Sek |
| No-Show Release | 10 Min | 30 Sek |

Zusätzlich: "Buchung Ende" (Trigger: `buchung_aktiv_x` → `"off"`, Alles aus wenn niemand da)

---

### `index.html` — Haupt-Dashboard

Flask-Template (`render_template("index.html")`). Kiosk-Ansicht auf Pi 2.

Linke Spalte: Wetter Stuttgart, 3-Tage-Forecast, Sonnenauf/-untergang + UV, Verkehr
Rechte Spalte: 4 Raumkarten (Frei/Belegt, Nutzer, bis, nächste Buchung), Buchungsmodal

Flask erwartet dieses File unter `/home/raspi/dashboard_mariadb/templates/index.html`

---

### `raum_detail.html` — Raum-Detailseite

Flask-Template, aufgerufen von `GET /raum/<raum_id>`.
`raum_id` und `raum_name` werden als `data-*`-Attribute auf `<body>` gesetzt.

Sektionen: Header + Status-Badge, Sensoren-Zeile (3 Mini-Cards), Komfort-Card (Datum/KW + Anwesenheit), Buchungs-Timeline (3 Tabs), Steuerung (Licht/Rollo/Klima), Schnell-Aktionen, Toast

Flask erwartet dieses File unter `/home/raspi/dashboard_mariadb/templates/raum_detail.html`

---

### `detail.css` — Styling Raum-Detail

Dark Theme (`#0f172a` / `#1e293b`). Responsive via `clamp()` und Media-Query <520px Höhe.

Farben: OK `#22c55e`, Warn `#fbbf24`, Kritisch `#ef4444`, Unbekannt `#64748b`, Akzent `#38bdf8`

Auf Pi 4 unter `/home/raspi/dashboard_mariadb/static/detail.css`

---

### `dashboard.js` — Frontend-Logik Dashboard

Version `dropdowns-v2-20260527`. Polling-Intervalle:

| Funktion | Intervall | Endpoint |
|---|---|---|
| `updateClock()` | 1s | — |
| `ladeRaeume()` | 30s | `GET /api/raeume` |
| `ladeVerkehr()` | 60s | `GET /api/verkehr` |
| `ladeWetter()` | 600s | `GET /api/wetter` |

Buchungsmodal: `fuelleDatumOptionen()` (15 Tage), `fuelleZeitOptionen()` (8:00–18:00, 30-Min), `naechsteHalbeStunde()` (Vorauswahl). Speichern via `POST /buchen`.

Auf Pi 4 unter `/home/raspi/dashboard_mariadb/static/dashboard.js`

---

### `detail.js` — Frontend-Logik Raum-Detail

Version `compact-3sections-v10-20260527`. Polling-Intervalle:

| Funktion | Intervall | Endpoint |
|---|---|---|
| `loadPresence()` | 5s | `GET /api/raum/{id}/anwesenheit` |
| `loadControlState()` | 5s | `GET /api/raum/{id}/status` |
| `loadSensors()` | 10s | `GET /api/sensoren/{id}` |
| `loadBookings()` | 30s | `GET /api/raum/{id}/buchungen?datum=...` |

Sensor-Schwellwerte:

| Sensor | OK | Warn | Kritisch |
|---|---|---|---|
| Temperatur | 19–24°C | 17–26°C | außerhalb |
| Luftfeuchte | 40–60% | 30–70% | außerhalb |
| CO2 | 0–1000 ppm | 0–1400 ppm | >1400 ppm |

Timeline: Zeitbereich 07:00–20:00, Lane-System für Überlappungen, Jetzt-Linie (nur heute).
Anwesenheit: `true` → 👤 blau, `false` → 🚪 grau, `null` → ⏳ grau.

Auf Pi 4 unter `/home/raspi/dashboard_mariadb/static/detail.js`

---

### `person_detection.py` — KI-Personenerkennung (Pi 1)

YOLOv8s auf Hailo-8 AI Accelerator. Liest `/tmp/frame.jpg` (von Pi 3), führt Inferenz durch, publisht `room/raum_a/occupied`.

Glättung: Sliding Window über 5 Frames — `true` nur wenn ≥3 von 5 positiv.
Fallback: `last_good_frame` wenn Frame nicht lesbar.

```python
MQTT_HOST = "192.168.1.206"
CONFIDENCE = 0.3
SEND_INTERVAL = 5
HEF_PATH = "/usr/share/hailo-models/yolov8s_h8l.hef"
```

---

### `sensor_mqtt.py` — Sensor-Publisher (Pi 33)

DHT22 (GPIO 4) + SCD30 (I2C). Publiziert sekündlich an `sensor/raum_a/*`.
Primary: SCD30, Fallback: DHT22. Je 10 Leseversuche mit Delay.

---

### `debug_server.py` — Kamera-Debug (Pi 1, :5001)

MJPEG-Stream mit eingezeichneten Bounding Boxes. Liest `/tmp/frame.jpg` + `/tmp/detections.json`.
Rotiert Frame 180° (Kamera hängt umgekehrt). Qualität 70, 500ms Delay.

---

### `stream_test.py` — Einmaliger Verbindungstest

Liest einen Frame von `udp://@:9000` und speichert nach `/home/raspi/test_stream.jpg`. Zur Verifikation des UDP-Streams von Pi 3.

---

### `patch_anwesenheit.py` — Einmaliger Patch (veraltet)

Fügte `belegung_timestamps` und `/api/raum/<id>/anwesenheit` zu einer älteren Version von `app.py` hinzu. Beide Features sind in der aktuellen `app.py` bereits integriert — dieses Skript ist obsolet.

---

### `patch_buchungen.py` — Einmaliger Patch (veraltet)

Ersetzte den alten Buchungs-Endpoint durch die datumsgefilterte Version mit Status-Berechnung. Ebenfalls in der aktuellen `app.py` integriert — obsolet.

---

### `install_emoji.sh` — Einmaliges Setup (Pi 2)

Installiert `fonts-noto-color-emoji` + `fonts-symbola`, rebuildet Font-Cache, startet Chromium neu.

---

## Wichtige Datenflüsse

### Buchung erstellen

```
Browser (dashboard.js)
  → POST /buchen {raum, nutzer, start, ende}
  → Flask: INSERT INTO buchungen (belegt=1)
  ← {status: "ok", id}
  → ladeRaeume() + loadBookings() neu laden
```

### Buchung aktiviert → Komfort ein

```
HA REST-Sensor (alle 30s) → GET /api/raeume
  ← prüft: belegt=true UND nutzer != "Anwesend"
  → sensor.buchung_aktiv_x = "on"
  → Automation "Buchung Komfort" feuert
  → MQTT cmd/raum_x/licht = "on", rollo = "up"
  → MQTT cmd/raum_x/klima_modus = "heat"|"cool", klima_soll = "21"|"22"
```

### Person erkannt → Auto-Check-in

```
Pi 33 (kamera-stream.service):
  rpicam-vid → UDP 192.168.1.211:9000

Pi 4 (ffmpeg-stream.service):
  ffmpeg udp://@:9000 → /tmp/frame.jpg (5fps, immer überschrieben)

Pi 4 (person-detection.service):
  person_detection.py liest /tmp/frame.jpg
  → Hailo-8 YOLOv8s Inferenz
  → /tmp/detections.json
  → MQTT room/raum_a/occupied = "true"

app.py on_message():
  → belegung_cache["raum_a"] = True
  → mark_checked_in("Raum A")
    → UPDATE buchungen SET checked_in_at=NOW() WHERE id=<aktive>

HA: binary_sensor.anwesenheit_raum_a = "on"
  → Automation "Person erkannt" → Komfort einschalten

Detail-Frontend (5s): GET /api/raum/raum_a/anwesenheit
  ← {occupied: true, alter_sek: 2}
  → renderPresence() → 👤 "PERSON ERKANNT"
```

### No-Show — zwei parallele Mechanismen

```
[Weg 1: Backend auto_release_loop, alle 30s]
  SQL: start <= NOW() - INTERVAL 1 MINUTE AND checked_in_at IS NULL
  → UPDATE buchungen SET abgelaufen=1

[Weg 2: HA Automation, 10 Min Timeout]
  sensor.buchung_aktiv_x = "on" → wartet 10 Min auf Anwesenheit
  → POST /raum/raum_x/frei
  → UPDATE buchungen SET storniert=TRUE
  → MQTT room/raum_x/occupied = "false" (retain)
  → HA Notification

Beide können unabhängig feuern. abgelaufen=1 vs. storniert=TRUE sind
verschiedene Zustände — beide werden in Queries mit AND abgelaufen=0
AND storniert=FALSE ausgefiltert.
```

### Sensordaten anzeigen

```
Pi 33 (sekündlich) → MQTT sensor/raum_a/temperatur|luftfeuchte|co2
  → app.py on_message() → sensor_cache["raum_a"]

Detail-Frontend (10s): GET /api/sensoren/raum_a
  ← {temperatur: 22.5, luftfeuchte: 45.2, co2: 800}
  → bewerteWert() + sensorMessage() → Farben + Empfehlungen
```

---

## MariaDB-Schema (Pi 206, DB: `raumverwaltung`)

Verifiziert aus `schema.sql`. Läuft auf Pi 206 (192.168.1.206), nicht Pi 4.

```sql
CREATE TABLE raeume (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(50) NOT NULL UNIQUE,  -- z.B. "Raum A"
    mqtt_key     VARCHAR(20) UNIQUE,           -- z.B. "raum_a"
    kapazitaet   INT DEFAULT 4,
    aktiv        TINYINT DEFAULT 1,
    erstellt_am  DATETIME DEFAULT current_timestamp()
);
-- AUTO_INCREMENT=5 → 4 Räume angelegt (A–D)

CREATE TABLE buchungen (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    raum          VARCHAR(50) NOT NULL,        -- z.B. "Raum A" (entspricht raeume.name)
    nutzer        VARCHAR(100) NOT NULL,
    start         DATETIME NOT NULL,
    ende          DATETIME NOT NULL,
    belegt        TINYINT DEFAULT 1,
    storniert     TINYINT DEFAULT 0,
    checked_in_at DATETIME DEFAULT NULL,       -- gesetzt bei MQTT occupied=true
    abgelaufen    TINYINT DEFAULT 0,           -- gesetzt von auto_release_loop()
    erstellt_am   DATETIME DEFAULT current_timestamp(),
    KEY idx_raum (raum),
    KEY idx_start (start),
    KEY idx_zeitraum (start, ende)
);
-- AUTO_INCREMENT=51 → ~50 Buchungen bereits erfasst

CREATE TABLE sensordaten (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    raum         VARCHAR(50) NOT NULL,
    temperatur   DECIMAL(4,1),
    luftfeuchte  DECIMAL(4,1),
    co2          INT,
    zeitstempel  DATETIME DEFAULT current_timestamp(),
    KEY idx_raum_zeit (raum, zeitstempel)
);
-- Historisches Feature: Sensor-Verlauf sollte hier persistiert werden.
-- Wurde angedacht aber nie fertig implementiert und wieder entfernt.
-- GET /api/raum/<raum>/verlauf gibt Mock-Daten zurück, Tabelle bleibt leer.
```

**Unterschied `storniert` vs. `abgelaufen`:**
- `storniert = 1`: manuelles Storno (User-Aktion oder HA-Automation via `/raum/x/frei`)
- `abgelaufen = 1`: automatisches Release durch `auto_release_loop()` im Backend (kein Check-in nach 1 Min)

---

## Nutzer & Räume

**Nutzer (hardcoded im Frontend):** Nick, Moritz, Niklas, Robin

**Räume:** Raum A, Raum B, Raum C, Raum D
- ID-Konvention: `"Raum A"` (DB/HA/control_state) ↔ `"raum_a"` (URL/MQTT/belegung_cache)
- Nur Raum A hat vollständige Sensor-Entities in `configuration.yaml`

**Sondernutzer `"Anwesend"`:** Wird von `app.py` gesetzt wenn MQTT `occupied=true` aber keine aktive Buchung. Der HA REST-Sensor schließt diesen Wert explizit aus damit reine Kamera-Erkennungen keine Komfort-Automation triggern.

---

## Deployment

| Pi | Pfad | Services | Dateien im Repo |
|---|---|---|---|
| Pi 2 | — | Chromium Kiosk | `install_emoji.sh` ✅ |
| Pi 4 | `/home/raspi/` & `/home/raspi/dashboard_mariadb/` | Flask, MariaDB, FFmpeg, Hailo-8 KI | `app.py` ✅, `config.py` ✅, `person_detection.py` ✅, `debug_server.py` ✅, `stream_test.py` ✅, `dashboard.service` ✅, `ffmpeg-stream.service` ✅, `person-detection.service` ✅, `debug-server.service` ✅ |
| Pi 33 | `/home/raspi/` | Sensoren + Kamera-Streamer | `sensor_mqtt.py` ✅, `DHT22.py` ✅, `test_dht.py` ✅, `test_co2.py` ✅, `kamera-stream.service` ✅, `sensor.service` ✅ |
| Pi 206 | `/config/` | Mosquitto, Home Assistant | `configuration.yaml` ✅, `automations.yaml` ✅, `ha_automations_prod_v1.yaml` ✅, `ha_automations_test_v2.yaml` ✅ |

Für Produktion: `ha_automations_prod_v1.yaml` in HA laden.
Für Tests: `ha_automations_test_v2.yaml` (kürzere Timeouts).

---

## Noch fehlende Dateien

Siehe nächsten Abschnitt — vollständige Checkliste was noch vom Pi geholt werden muss.
