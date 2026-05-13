import cv2
import json
import os
import time
from flask import Flask, Response, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Kamera Debug</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { background: #111; color: #fff; font-family: monospace; text-align: center; }
        h1 { margin: 20px; }
        img { max-width: 100%; border: 2px solid #444; }
        .status { font-size: 2em; margin: 20px; }
        .true  { color: #0f0; }
        .false { color: #888; }
    </style>
</head>
<body>
    <h1>Kamera Debug - Pi 33</h1>
    <div class="status {{ status_class }}">{{ status_text }}</div>
    <img src="/stream" />
</body>
</html>
"""

def get_detections():
    try:
        with open('/tmp/detections.json') as f:
            return json.load(f)
    except:
        return {'person_detected': False, 'boxes': []}

def generate():
    while True:
        frame = cv2.imread('/tmp/frame.jpg')
        if frame is None:
            time.sleep(0.5)
            continue

        frame = cv2.rotate(frame, cv2.ROTATE_180)
        data = get_detections()
        h, w = frame.shape[:2]

        for box in data.get('boxes', []):
            x1 = int(box['x1'] * w)
            y1 = int(box['y1'] * h)
            x2 = int(box['x2'] * w)
            y2 = int(box['y2'] * h)
            score = box['score']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'Person {score:.0%}', (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        label = 'PERSON ERKANNT' if data['person_detected'] else 'NIEMAND'
        color = (0, 255, 0) if data['person_detected'] else (128, 128, 128)
        cv2.putText(frame, label, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        time.sleep(0.5)

@app.route('/')
def index():
    data = get_detections()
    status_class = 'true' if data['person_detected'] else 'false'
    status_text  = 'Person erkannt' if data['person_detected'] else 'Niemand im Raum'
    return render_template_string(HTML, status_class=status_class, status_text=status_text)

@app.route('/stream')
def stream():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print('Debug-Server auf http://192.168.1.211:5001')
    app.run(host='0.0.0.0', port=5001, threaded=True)
