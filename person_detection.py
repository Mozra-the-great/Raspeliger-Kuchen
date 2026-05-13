import cv2
import numpy as np
import os
import shutil
import time
import json
import paho.mqtt.client as mqtt
from hailo_platform import (VDevice, HEF, ConfigureParams,
                             InputVStreamParams, OutputVStreamParams,
                             InferVStreams, FormatType, HailoStreamInterface)

# === KONFIGURATION ===
HEF_PATH      = '/usr/share/hailo-models/yolov8s_h8l.hef'
MQTT_HOST     = '192.168.1.206'
MQTT_PORT     = 1883
MQTT_USER     = 'raspi'
MQTT_PASS     = 'raspi'
MQTT_TOPIC    = 'room/raum_a/occupied'
CONFIDENCE    = 0.3
SEND_INTERVAL = 5

# === KAMERA ===
last_good_frame = None

def read_frame():
    global last_good_frame
    try:
        shutil.copy2('/tmp/frame.jpg', '/tmp/frame_read.jpg')
        frame = cv2.imread('/tmp/frame_read.jpg')
        if frame is not None and frame.size > 0:
            last_good_frame = frame
            return frame
        return last_good_frame
    except:
        return last_good_frame

# === Erster Frame testen ===
print('Warte auf ersten Frame...')
for _ in range(40):
    time.sleep(0.5)
    frame = read_frame()
    if frame is not None:
        print('Stream empfangen')
        break
else:
    print('Kein Frame empfangen')
    exit(1)

# === MQTT ===
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.connect(MQTT_HOST, MQTT_PORT)
mqtt_client.loop_start()
print('MQTT verbunden')

# === HAILO ===
target = VDevice()
hef = HEF(HEF_PATH)
configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
network_groups = target.configure(hef, configure_params)
network_group = network_groups[0]
network_group_params = network_group.create_params()
input_name  = hef.get_input_vstream_infos()[0].name
output_name = hef.get_output_vstream_infos()[0].name
input_params  = InputVStreamParams.make(network_group, format_type=FormatType.UINT8)
output_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
print('Hailo bereit')
print('Starte Personenerkennung...')

last_state = None
last_send  = 0
recent_detections = []

try:
    with InferVStreams(network_group, input_params, output_params) as pipeline:
        with network_group.activate(network_group_params):
            while True:
                frame = read_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                time.sleep(0.1)

                h_orig, w_orig = frame.shape[:2]
                scale = min(640 / w_orig, 640 / h_orig)
                new_w, new_h = int(w_orig * scale), int(h_orig * scale)
                pad_x = (640 - new_w) // 2
                pad_y = (640 - new_h) // 2
                resized = cv2.resize(frame, (new_w, new_h))
                letterbox = np.zeros((640, 640, 3), dtype=np.uint8)
                letterbox[pad_y:pad_y+new_h, pad_x:pad_x+new_w] = resized
                rgb = cv2.cvtColor(letterbox, cv2.COLOR_BGR2RGB)
                input_data = {input_name: np.expand_dims(rgb, axis=0)}

                output_data  = pipeline.infer(input_data)
                detections   = output_data[output_name][0]
                person_class = detections[0]

                if person_class.size == 0 or person_class.ndim < 2:
                    detected_now = False
                    boxes = []
                else:
                    if person_class.shape[0] == 5:
                        scores  = person_class[4]
                        get_box = lambda i: (person_class[0][i], person_class[1][i],
                                             person_class[2][i], person_class[3][i], scores[i])
                    else:
                        scores  = person_class[:, 4]
                        get_box = lambda i: (person_class[i][0], person_class[i][1],
                                             person_class[i][2], person_class[i][3], person_class[i][4])
                    detected_now = bool(np.any(scores > CONFIDENCE))
                    boxes = []
                    for i in range(len(scores)):
                        x1, y1, x2, y2, score = get_box(i)
                        if float(score) > CONFIDENCE:
                            boxes.append({
                                'x1': (float(x1) * 640 - pad_x) / scale / w_orig,
                                'y1': (float(y1) * 640 - pad_y) / scale / h_orig,
                                'x2': (float(x2) * 640 - pad_x) / scale / w_orig,
                                'y2': (float(y2) * 640 - pad_y) / scale / h_orig,
                                'score': float(score)
                            })

                with open('/tmp/detections.json', 'w') as f:
                    json.dump({'person_detected': detected_now, 'boxes': boxes}, f)

                recent_detections.append(detected_now)
                if len(recent_detections) > 5:
                    recent_detections.pop(0)
                person_detected = recent_detections.count(True) >= 3

                now   = time.time()
                state = 'true' if person_detected else 'false'
                if state != last_state or (now - last_send) > SEND_INTERVAL:
                    mqtt_client.publish(MQTT_TOPIC, state)
                    status = 'Person erkannt' if person_detected else 'Niemand'
                    print(f'{status} -> {MQTT_TOPIC}: {state}')
                    last_state = state
                    last_send  = now

except KeyboardInterrupt:
    print('Gestoppt')
    mqtt_client.publish(MQTT_TOPIC, 'false')
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
