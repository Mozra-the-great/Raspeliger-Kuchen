#!/usr/bin/env python3
"""Patcht app.py: erweitert /api/raum/<raum_name>/buchungen um ?datum=Parameter."""

APP = '/home/raspi/dashboard_mariadb/app.py'

with open(APP) as f:
    content = f.read()

start_marker = '@app.route("/api/raum/<raum_name>/buchungen")'
end_marker = '@app.route("/buchen", methods=["POST"])'

if start_marker not in content:
    print("FEHLER: start_marker nicht gefunden")
elif end_marker not in content:
    print("FEHLER: end_marker nicht gefunden")
elif 'datum_str = request.args.get("datum")' in content:
    print("Patch bereits angewendet, skip")
else:
    start = content.index(start_marker)
    end = content.index(end_marker)

    new_function = '''@app.route("/api/raum/<raum_name>/buchungen")
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


'''

    new_content = content[:start] + new_function + content[end:]
    with open(APP, 'w') as f:
        f.write(new_content)
    print("api_raum_buchungen ersetzt — Service neu starten")
