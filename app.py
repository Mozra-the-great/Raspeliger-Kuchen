"""
Raumverwaltung Dashboard - v3
- Wetter (Open-Meteo, Stuttgart)
- Verkehr (Demo-Status)
- Buchungs-Anzeige nur wenn aktiv (Bugfix)
- Raum-Detail-View mit Steuerung
"""

from flask import Flask, render_template, jsonify, request
import pymysql
import pymysql.cursors
import random
import threading
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
from config import (
    DB_CONFIG, FLASK_HOST, FLASK_PORT, DEBUG,
    MQTT_CONFIG, MQTT_TOPICS, HAUPT_RAUM,
    MOCK_SENSORS, MQTT_ENABLED, SCHWELLWERTE
)

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("⚠️  paho-mqtt nicht installiert - MQTT deaktiviert")

app = Flask(__name__)

# ============================================
# CACHES
# ============================================
sensor_cache = {}
cache_lock = threading.Lock()
belegung_cache = {}
belegung_timestamps = {}

control_state = {}
control_lock = threading.Lock()

wetter_cache = {"data": None, "ts": 0}
wetter_lock = threading.Lock()

verkehr_cache = {"status": "gruen", "last_change": 0, "next_change": 300}
verkehr_lock = threading.Lock()


def get_control_state(raum):
    with control_lock:
        if raum not in control_state:
            control_state[raum] = {
                "licht": "off",
                "rollo": "up",
                "klima_modus": "off",
                "klima_soll": 22,
                "checkin": False,
                "letzte_aenderung": datetime.now().isoformat()
            }
        return dict(control_state[raum])


def set_control_state(raum, key, value):
    with control_lock:
        if raum not in control_state:
            control_state[raum] = {
                "licht": "off", "rollo": "up", "klima_modus": "off",
                "klima_soll": 22, "checkin": False,
                "letzte_aenderung": datetime.now().isoformat()
            }
        control_state[raum][key] = value
        control_state[raum]["letzte_aenderung"] = datetime.now().isoformat()
        return dict(control_state[raum])


# ============================================
# MQTT
# ============================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ MQTT verbunden mit {MQTT_CONFIG['host']}")
        for topic in MQTT_TOPICS:
            client.subscribe(topic)
    else:
        print(f"❌ MQTT-Verbindung fehlgeschlagen (Code {rc})")


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode("utf-8").strip()
        teile = topic.split("/")

        if teile[0] == "sensor" and len(teile) == 3:
            raum, typ = teile[1], teile[2]
            with cache_lock:
                if raum not in sensor_cache:
                    sensor_cache[raum] = {}
                sensor_cache[raum][typ] = (payload, datetime.now())

        elif teile[0] == "room" and len(teile) == 3 and teile[2] == "occupied":
            raum = teile[1]
            occupied = payload.lower() in ("true", "1", "yes")
            with cache_lock:
                belegung_cache[raum] = occupied
                belegung_timestamps[raum] = datetime.now()
            # Phase C.3: Auto-Check-in bei erkannter Anwesenheit
            if occupied:
                raum_anzeige = raum.replace("_", " ").title()
                mark_checked_in(raum_anzeige)

        elif teile[0] == "state" and len(teile) == 3:
            raum, typ = teile[1], teile[2]
            raum_name = raum.replace("_", " ").title()
            set_control_state(raum_name, typ, payload)

    except Exception as e:
        print(f"⚠️  MQTT-Parse-Fehler: {e}")


def mqtt_start():
    if not MQTT_AVAILABLE or not MQTT_ENABLED:
        return None
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if MQTT_CONFIG.get("username"):
        client.username_pw_set(MQTT_CONFIG["username"], MQTT_CONFIG["password"])
    try:
        client.connect(MQTT_CONFIG["host"], MQTT_CONFIG["port"], MQTT_CONFIG.get("keepalive", 60))
        client.loop_start()
        return client
    except Exception as e:
        print(f"❌ MQTT-Start fehlgeschlagen: {e}")
        return None


mqtt_client = None


def mqtt_publish_command(raum, geraet, befehl):
    if not mqtt_client:
        return False
    raum_id = raum.lower().replace(" ", "_")
    topic = f"cmd/{raum_id}/{geraet}"
    try:
        mqtt_client.publish(topic, str(befehl))
        return True
    except Exception:
        return False


# ============================================
# DB-HELPER
# ============================================
def get_db():
    return pymysql.connect(
        **DB_CONFIG,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )


def parse_db_datetime(val):
    if isinstance(val, datetime):
        return val
    if not val:
        return None
    s = str(val).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
        except ValueError:
            continue
    return None



# ============================================
# BUCHUNGS-HELPERS (Phase C.2)
# ============================================
def find_aktive_buchung(cursor, raum_anzeige):
    """Findet die aktuell laufende Buchung fuer den Raum (oder None)."""
    cursor.execute("""
        SELECT id, nutzer, start, ende, checked_in_at
        FROM buchungen
        WHERE raum = %s
          AND storniert = 0
          AND abgelaufen = 0
        ORDER BY start ASC
    """, (raum_anzeige,))
    jetzt = datetime.now()
    for b in cursor.fetchall():
        start_dt = parse_db_datetime(b["start"])
        ende_dt  = parse_db_datetime(b["ende"])
        if start_dt and ende_dt and start_dt <= jetzt <= ende_dt:
            return b
    return None


def mark_checked_in(raum_anzeige):
    """Setzt checked_in_at=NOW auf die aktive Buchung (falls vorhanden + nicht schon eingecheckt)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                aktive = find_aktive_buchung(cursor, raum_anzeige)
                if aktive and not aktive.get("checked_in_at"):
                    cursor.execute(
                        "UPDATE buchungen SET checked_in_at = NOW() WHERE id = %s",
                        (aktive["id"],)
                    )
                    conn.commit()
                    print(f"OK Auto-Check-in: Buchung #{aktive['id']} ({raum_anzeige}, {aktive['nutzer']})")
                    return aktive["id"]
    except Exception as e:
        print(f"WARN mark_checked_in error: {e}")
    return None


def auto_release_loop():
    """Background-Thread: alle 30s Buchungen ohne Check-in nach 10 Min freigeben."""
    import time
    while True:
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, raum, nutzer
                        FROM buchungen
                        WHERE storniert = 0
                          AND abgelaufen = 0
                          AND checked_in_at IS NULL
                          AND start <= NOW() - INTERVAL 1 MINUTE
                          AND ende >= NOW()
                    """)
                    rows = cursor.fetchall()
                    for r in rows:
                        cursor.execute(
                            "UPDATE buchungen SET abgelaufen = 1 WHERE id = %s",
                            (r["id"],)
                        )
                        print(f"AUTO-RELEASE: Buchung #{r['id']} ({r['raum']}, {r['nutzer']}) — kein Check-in nach 10min")
                    conn.commit()
        except Exception as e:
            print(f"WARN auto_release_loop error: {e}")
        time.sleep(30)


# ============================================
# WETTER (Open-Meteo)
# ============================================
STUTTGART_LAT = 48.78
STUTTGART_LON = 9.18

WMO_CODES = {
    0:  {"icon": "☀️", "text": "Sonnig"},
    1:  {"icon": "🌤️", "text": "Heiter"},
    2:  {"icon": "⛅",  "text": "Wolkig"},
    3:  {"icon": "☁️", "text": "Bedeckt"},
    45: {"icon": "🌫️", "text": "Nebel"},
    48: {"icon": "🌫️", "text": "Reifnebel"},
    51: {"icon": "🌦️", "text": "Leichter Nieselregen"},
    53: {"icon": "🌦️", "text": "Nieselregen"},
    55: {"icon": "🌧️", "text": "Starker Nieselregen"},
    61: {"icon": "🌧️", "text": "Leichter Regen"},
    63: {"icon": "🌧️", "text": "Regen"},
    65: {"icon": "🌧️", "text": "Starker Regen"},
    71: {"icon": "🌨️", "text": "Leichter Schnee"},
    73: {"icon": "🌨️", "text": "Schnee"},
    75: {"icon": "❄️",  "text": "Starker Schnee"},
    77: {"icon": "🌨️", "text": "Schneegriesel"},
    80: {"icon": "🌦️", "text": "Schauer"},
    81: {"icon": "🌧️", "text": "Starke Schauer"},
    82: {"icon": "⛈️", "text": "Gewitterschauer"},
    95: {"icon": "⛈️", "text": "Gewitter"},
    96: {"icon": "⛈️", "text": "Gewitter mit Hagel"},
    99: {"icon": "⛈️", "text": "Schweres Gewitter"},
}


def fetch_wetter():
    now = time.time()
    with wetter_lock:
        if wetter_cache["data"] and (now - wetter_cache["ts"] < 600):
            return wetter_cache["data"]

    params = {
        "latitude": STUTTGART_LAT,
        "longitude": STUTTGART_LON,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_probability_max",
        "timezone": "Europe/Berlin",
        "forecast_days": 4,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            raw = json.load(resp)

        cur = raw.get("current", {})
        daily = raw.get("daily", {})
        wcode = int(cur.get("weather_code", 0))
        wmo = WMO_CODES.get(wcode, {"icon": "❓", "text": f"Code {wcode}"})

        forecast = []
        days = daily.get("time", [])
        wochentage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for i, d in enumerate(days):
            dc = int(daily["weather_code"][i])
            forecast.append({
                "datum": d,
                "tag":  wochentage[datetime.fromisoformat(d).weekday()],
                "icon": WMO_CODES.get(dc, {}).get("icon", "?"),
                "text": WMO_CODES.get(dc, {}).get("text", ""),
                "max":  round(daily["temperature_2m_max"][i]),
                "min":  round(daily["temperature_2m_min"][i]),
                "regen_pct": daily.get("precipitation_probability_max", [0]*len(days))[i] or 0,
            })

        sunrise = daily["sunrise"][0] if daily.get("sunrise") else None
        sunset  = daily["sunset"][0] if daily.get("sunset") else None
        uv      = daily["uv_index_max"][0] if daily.get("uv_index_max") else 0

        data = {
            "ort": "Stuttgart",
            "current": {
                "temp":       round(cur.get("temperature_2m", 0), 1),
                "feels_like": round(cur.get("apparent_temperature", 0), 1),
                "humidity":   cur.get("relative_humidity_2m", 0),
                "wind":       round(cur.get("wind_speed_10m", 0), 1),
                "is_day":     bool(cur.get("is_day", 1)),
                "icon":       wmo["icon"],
                "text":       wmo["text"],
            },
            "tag": {
                "sunrise": sunrise[-5:] if sunrise else "--:--",
                "sunset":  sunset[-5:] if sunset else "--:--",
                "uv":      round(uv or 0, 1),
            },
            "forecast": forecast,
            "abgerufen": datetime.now().strftime("%H:%M"),
        }

        with wetter_lock:
            wetter_cache["data"] = data
            wetter_cache["ts"] = now
        return data

    except Exception as e:
        print(f"⚠️  Wetter-API Fehler: {e}")
        return wetter_cache.get("data") or {"error": str(e)}


# ============================================
# VERKEHR (Demo)
# ============================================
def fetch_verkehr():
    now = time.time()
    with verkehr_lock:
        if now - verkehr_cache["last_change"] > verkehr_cache["next_change"]:
            stunde = datetime.now().hour
            if 7 <= stunde <= 9 or 16 <= stunde <= 19:
                verkehr_cache["status"] = random.choices(
                    ["gruen", "gelb", "rot"], weights=[20, 50, 30]
                )[0]
            elif 22 <= stunde or stunde <= 5:
                verkehr_cache["status"] = "gruen"
            else:
                verkehr_cache["status"] = random.choices(
                    ["gruen", "gelb", "rot"], weights=[70, 25, 5]
                )[0]
            verkehr_cache["last_change"] = now
            verkehr_cache["next_change"] = random.randint(300, 600)
        status = verkehr_cache["status"]

    info = {
        "gruen": {
            "status": "gruen",
            "label": "Frei",
            "beschreibung": "Verkehr läuft flüssig",
            "details": ["A8 frei", "A81 frei", "Innenstadt normal"]
        },
        "gelb": {
            "status": "gelb",
            "label": "Mäßig",
            "beschreibung": "Erhöhtes Verkehrsaufkommen",
            "details": ["A8 zähflüssig", "B14 stockend", "Stadtmitte voll"]
        },
        "rot": {
            "status": "rot",
            "label": "Stau",
            "beschreibung": "Stau auf Hauptstrecken",
            "details": ["A8: 12 km Stau", "Verzögerung 25 Min", "Umfahrung empfohlen"]
        },
    }
    return info[status]


# ============================================
# ROUTES
# ============================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/raum/<raum_id>")
def raum_detail(raum_id):
    raum_name = raum_id.replace("_", " ").title()
    return render_template("raum_detail.html", raum_id=raum_id, raum_name=raum_name)


@app.route("/api/wetter")
def api_wetter():
    return jsonify(fetch_wetter())


@app.route("/api/verkehr")
def api_verkehr():
    return jsonify(fetch_verkehr())


@app.route("/api/sensoren")
def api_sensoren():
    if MOCK_SENSORS:
        return jsonify({
            "temperatur": round(21.5 + random.uniform(-1.5, 2.0), 1),
            "luftfeuchte": round(45 + random.uniform(-5, 10), 1),
            "co2": round(600 + random.uniform(-50, 400)),
            "zeitstempel": datetime.now().strftime("%H:%M:%S"),
            "quelle": "mock"
        })
    with cache_lock:
        raum_data = sensor_cache.get(HAUPT_RAUM, {})
        temp = raum_data.get("temperatur", (None, None))[0]
        hum  = raum_data.get("luftfeuchte", (None, None))[0]
        co2  = raum_data.get("co2", (None, None))[0]
        zeiten = [v[1] for v in raum_data.values() if v[1]]
        letzte = max(zeiten).strftime("%H:%M:%S") if zeiten else "–"
    return jsonify({
        "temperatur": float(temp) if temp else None,
        "luftfeuchte": float(hum) if hum else None,
        "co2": int(float(co2)) if co2 else None,
        "zeitstempel": letzte,
        "quelle": "mqtt",
        "raum": HAUPT_RAUM
    })


@app.route("/api/sensoren/<raum_id>")
def api_sensoren_raum(raum_id):
    if MOCK_SENSORS:
        return jsonify({
            "temperatur": round(21.5 + random.uniform(-1.5, 2.0), 1),
            "luftfeuchte": round(45 + random.uniform(-5, 10), 1),
            "co2": round(600 + random.uniform(-50, 400)),
            "zeitstempel": datetime.now().strftime("%H:%M:%S"),
            "raum": raum_id
        })
    with cache_lock:
        raum_data = sensor_cache.get(raum_id, {})
        temp = raum_data.get("temperatur", (None, None))[0]
        hum  = raum_data.get("luftfeuchte", (None, None))[0]
        co2  = raum_data.get("co2", (None, None))[0]
        zeiten = [v[1] for v in raum_data.values() if v[1]]
        letzte = max(zeiten).strftime("%H:%M:%S") if zeiten else "–"
    return jsonify({
        "temperatur": float(temp) if temp else None,
        "luftfeuchte": float(hum) if hum else None,
        "co2": int(float(co2)) if co2 else None,
        "zeitstempel": letzte,
        "raum": raum_id
    })


@app.route("/api/raeume")
def api_raeume():
    """Räume-Liste mit echter 'aktiv'-Prüfung (Bugfix)."""
    try:
        jetzt = datetime.now()
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM raeume WHERE aktiv = TRUE ORDER BY name")
                raeume = cursor.fetchall()
                for raum in raeume:
                    cursor.execute("""
                        SELECT id, nutzer, start, ende
                        FROM buchungen
                        WHERE raum = %s
                          AND storniert = FALSE
                          AND abgelaufen = 0
                        ORDER BY start ASC
                    """, (raum["name"],))
                    alle_buchungen = cursor.fetchall()

                    aktuell = None
                    for b in alle_buchungen:
                        start_dt = parse_db_datetime(b["start"])
                        ende_dt  = parse_db_datetime(b["ende"])
                        if start_dt and ende_dt and start_dt <= jetzt <= ende_dt:
                            aktuell = b
                            break

                    raum_key = raum["name"].lower().replace(" ", "_")
                    mqtt_belegt = belegung_cache.get(raum_key)

                    if aktuell:
                        ende_dt = parse_db_datetime(aktuell["ende"])
                        raum["belegt"] = True
                        raum["nutzer"] = aktuell["nutzer"]
                        raum["bis"]    = ende_dt.strftime("%H:%M") if ende_dt else None
                    else:
                        raum["belegt"] = False
                        raum["nutzer"] = None
                        raum["bis"]    = None

                    naechste = None
                    for b in alle_buchungen:
                        start_dt = parse_db_datetime(b["start"])
                        if start_dt and start_dt > jetzt:
                            naechste = b
                            break
                    if naechste:
                        start_dt = parse_db_datetime(naechste["start"])
                        raum["naechste_buchung"] = {
                            "nutzer": naechste["nutzer"],
                            "start":  start_dt.strftime("%H:%M") if start_dt else None,
                        }
                    else:
                        raum["naechste_buchung"] = None

                    raum["anwesenheit"] = mqtt_belegt

                    # Anwesenheit ueberschreibt belegt (auch ohne Buchung)
                    if not aktuell and mqtt_belegt:
                        raum["belegt"] = True
                        raum["nutzer"] = "Anwesend"
                        raum["bis"] = None
        return jsonify(raeume)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/raum/<raum_name>/buchungen")
def api_raum_buchungen(raum_name):
    """Buchungen fuer Raum: pro Tag, Parameter ?datum=YYYY-MM-DD (default: heute)."""
    raum_anzeige = raum_name.replace("_", " ").title()
    try:
        jetzt = datetime.now()
        datum_str = request.args.get("datum")
        if datum_str:
            try:
                ziel_datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Ungueltiges Datum"}), 400
        else:
            ziel_datum = jetzt.date()
        tag_start = datetime.combine(ziel_datum, datetime.min.time())
        tag_ende = tag_start + timedelta(days=1)

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, nutzer, start, ende
                    FROM buchungen
                    WHERE raum = %s AND storniert = FALSE AND abgelaufen = 0
                """, (raum_anzeige,))
                rohdaten = cursor.fetchall()

        ergebnisse = []
        for b in rohdaten:
            start_dt = parse_db_datetime(b["start"])
            ende_dt  = parse_db_datetime(b["ende"])
            if not start_dt or not ende_dt:
                continue
            if ende_dt <= tag_start or start_dt >= tag_ende:
                continue
            if start_dt > ende_dt:
                start_dt, ende_dt = ende_dt, start_dt
            if ende_dt < jetzt:
                status = "vorbei"
            elif start_dt <= jetzt <= ende_dt:
                status = "aktiv"
            else:
                status = "geplant"
            ergebnisse.append({
                "id": b["id"],
                "nutzer": b["nutzer"],
                "start": start_dt.strftime("%H:%M"),
                "ende":  ende_dt.strftime("%H:%M"),
                "start_voll": start_dt.strftime("%Y-%m-%d %H:%M"),
                "ende_voll":  ende_dt.strftime("%Y-%m-%d %H:%M"),
                "status": status
            })
        ergebnisse.sort(key=lambda x: x["start"])
        return jsonify(ergebnisse)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/buchen", methods=["POST"])
def buchen():
    daten = request.get_json() or request.form
    for feld in ("raum", "nutzer", "start", "ende"):
        if not daten.get(feld):
            return jsonify({"status": "error", "nachricht": f"Feld fehlt: {feld}"}), 400
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO buchungen (raum, nutzer, start, ende, belegt)
                    VALUES (%s, %s, %s, %s, 1)
                """, (daten["raum"], daten["nutzer"], daten["start"], daten["ende"]))
                conn.commit()
                neue_id = cursor.lastrowid
        return jsonify({"status": "ok", "id": neue_id})
    except Exception as e:
        return jsonify({"status": "error", "nachricht": str(e)}), 500


@app.route("/buchen-schnell", methods=["POST"])
def buchen_schnell():
    daten = request.get_json() or request.form
    raum = daten.get("raum")
    dauer = int(daten.get("dauer_minuten", 30))
    nutzer = daten.get("nutzer", "Spontan")
    if not raum:
        return jsonify({"status": "error", "nachricht": "Raum fehlt"}), 400
    start = datetime.now()
    ende = start + timedelta(minutes=dauer)
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO buchungen (raum, nutzer, start, ende, belegt)
                    VALUES (%s, %s, %s, %s, 1)
                """, (raum, nutzer,
                      start.strftime("%Y-%m-%d %H:%M:%S"),
                      ende.strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                neue_id = cursor.lastrowid
        return jsonify({
            "status": "ok",
            "id": neue_id,
            "start": start.strftime("%H:%M"),
            "ende": ende.strftime("%H:%M")
        })
    except Exception as e:
        return jsonify({"status": "error", "nachricht": str(e)}), 500


@app.route("/stornieren/<int:buchung_id>", methods=["POST"])
def stornieren(buchung_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE buchungen SET storniert = TRUE WHERE id = %s", (buchung_id,))
                conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "nachricht": str(e)}), 500


@app.route("/api/raum/<raum_name>/status")
def api_raum_status(raum_name):
    raum_anzeige = raum_name.replace("_", " ").title()
    return jsonify(get_control_state(raum_anzeige))


@app.route("/api/raum/<raum_name>/licht", methods=["POST"])
def api_licht(raum_name):
    raum_anzeige = raum_name.replace("_", " ").title()
    daten = request.get_json() or {}
    action = daten.get("action", "toggle")
    state = get_control_state(raum_anzeige)
    if action == "toggle":
        action = "off" if state["licht"] == "on" else "on"
    if action not in ("on", "off"):
        return jsonify({"status": "error"}), 400
    new_state = set_control_state(raum_anzeige, "licht", action)
    mqtt_publish_command(raum_anzeige, "licht", action)
    return jsonify({"status": "ok", "state": new_state})


@app.route("/api/raum/<raum_name>/rollo", methods=["POST"])
def api_rollo(raum_name):
    raum_anzeige = raum_name.replace("_", " ").title()
    daten = request.get_json() or {}
    action = daten.get("action")
    if action not in ("up", "down", "stop"):
        return jsonify({"status": "error"}), 400
    new_state = set_control_state(raum_anzeige, "rollo", action)
    mqtt_publish_command(raum_anzeige, "rollo", action)
    return jsonify({"status": "ok", "state": new_state})


@app.route("/api/raum/<raum_name>/klima", methods=["POST"])
def api_klima(raum_name):
    raum_anzeige = raum_name.replace("_", " ").title()
    daten = request.get_json() or {}
    modus = daten.get("modus")
    soll = daten.get("soll")
    if modus and modus in ("heat", "cool", "off"):
        set_control_state(raum_anzeige, "klima_modus", modus)
        mqtt_publish_command(raum_anzeige, "klima_modus", modus)
    if soll is not None:
        try:
            soll_int = int(soll)
            if 15 <= soll_int <= 30:
                set_control_state(raum_anzeige, "klima_soll", soll_int)
                mqtt_publish_command(raum_anzeige, "klima_soll", soll_int)
        except (ValueError, TypeError):
            pass
    return jsonify({"status": "ok", "state": get_control_state(raum_anzeige)})


@app.route("/api/raum/<raum_name>/checkin", methods=["POST"])
def api_checkin(raum_name):
    raum_anzeige = raum_name.replace("_", " ").title()
    state = get_control_state(raum_anzeige)
    new_state = set_control_state(raum_anzeige, "checkin", not state["checkin"])
    return jsonify({"status": "ok", "state": new_state})


@app.route("/api/raum/<raum_name>/verlauf")
def api_verlauf(raum_name):
    jetzt = datetime.now()
    points = []
    for i in range(24):
        zeit = jetzt - timedelta(hours=23-i)
        temp = round(21 + (i / 24) * 3 + random.uniform(-0.8, 0.8), 1)
        hum  = round(50 + random.uniform(-10, 10), 1)
        co2  = round(500 + (i % 8) * 80 + random.uniform(-50, 100))
        points.append({"zeit": zeit.strftime("%H:%M"), "temperatur": temp, "luftfeuchte": hum, "co2": co2})
    return jsonify(points)


@app.route("/api/status")
def api_status():
    status = {"zeit": datetime.now().strftime("%H:%M:%S")}
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"error: {e}"
    with cache_lock:
        status["mqtt"] = {
            "aktiv": MQTT_ENABLED and MQTT_AVAILABLE,
            "raeume_mit_daten": list(sensor_cache.keys())
        }
    return jsonify(status)

@app.route("/raum/<raum_name>/frei", methods=["POST"])
def raum_frei(raum_name):
    """Storniert die aktive Buchung des Raums (HA-Trigger no-show)."""
    raum_anzeige = raum_name.replace("_", " ").title()
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                aktive = find_aktive_buchung(cursor, raum_anzeige)
                if not aktive:
                    return jsonify({"status": "ok", "nachricht": "keine aktive Buchung"})
                cursor.execute(
                    "UPDATE buchungen SET storniert = TRUE WHERE id = %s",
                    (aktive["id"],)
                )
                conn.commit()
                if mqtt_client:
                    mqtt_client.publish(f"room/{raum_name}/occupied", "false", retain=True)
                print(f"AUTO-RELEASE durch HA: Buchung #{aktive['id']} ({raum_anzeige})")
                return jsonify({"status": "ok", "id": aktive["id"]})
    except Exception as e:
        return jsonify({"status": "error", "nachricht": str(e)}), 500


@app.route("/api/raum/<raum_id>/anwesenheit")
def api_raum_anwesenheit(raum_id):
    """Anwesenheits-Status fuer einen Raum (live von Kamera-KI via MQTT)."""
    with cache_lock:
        occupied = belegung_cache.get(raum_id)
        ts = belegung_timestamps.get(raum_id)
    return jsonify({
        "occupied": occupied,
        "last_update": ts.strftime("%Y-%m-%d %H:%M:%S") if ts else None,
        "alter_sek": int((datetime.now() - ts).total_seconds()) if ts else None
    })


if __name__ == "__main__":
    print("=" * 50)
    print(f"Dashboard v3 startet auf http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"DB:           {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"MQTT:         {'an' if (MQTT_ENABLED and MQTT_AVAILABLE) else 'aus'}")
    print(f"Wetter:       Stuttgart (Open-Meteo)")
    print("=" * 50)
    mqtt_client = mqtt_start() if MQTT_ENABLED else None
    import threading
    threading.Thread(target=auto_release_loop, daemon=True).start()
    print("Auto-Release-Thread gestartet (Check alle 30s)")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
