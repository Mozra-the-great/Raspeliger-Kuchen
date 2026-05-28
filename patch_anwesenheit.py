#!/usr/bin/env python3
"""Patch: erweitert app.py um /api/raum/<id>/anwesenheit Endpoint + Timestamp-Cache."""

APP = '/home/raspi/dashboard_mariadb/app.py'

with open(APP) as f:
    content = f.read()

changed = False

# 1. belegung_timestamps Cache ergaenzen
if 'belegung_timestamps' not in content:
    content = content.replace(
        'belegung_cache = {}',
        'belegung_cache = {}\nbelegung_timestamps = {}'
    )
    changed = True

# 2. on_message: Timestamp mitschreiben
old_msg = '''            with cache_lock:
                belegung_cache[raum] = occupied'''
new_msg = '''            with cache_lock:
                belegung_cache[raum] = occupied
                belegung_timestamps[raum] = datetime.now()'''
if old_msg in content and 'belegung_timestamps[raum] = datetime.now()' not in content:
    content = content.replace(old_msg, new_msg)
    changed = True

# 3. Neuer Endpoint vor if __name__
endpoint = '''
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


'''

if 'def api_raum_anwesenheit(' not in content:
    if 'if __name__ == "__main__":' in content:
        content = content.replace('if __name__ == "__main__":', endpoint + 'if __name__ == "__main__":')
        changed = True
    else:
        print('FEHLER: if __name__ nicht gefunden, Endpoint NICHT eingefuegt')

if changed:
    with open(APP, 'w') as f:
        f.write(content)
    print('Patch angewendet — Service neu starten')
else:
    print('Patch bereits drin, skip')
