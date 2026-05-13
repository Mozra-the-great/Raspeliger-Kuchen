import cv2
import os

# FFmpeg-Logs unterdrücken
devnull = open(os.devnull, 'w')
old_stderr = os.dup(2)
os.dup2(devnull.fileno(), 2)

cap = cv2.VideoCapture('udp://@:9000?overrun_nonfatal=1&fifo_size=50000000', cv2.CAP_FFMPEG)

# stderr wiederherstellen
os.dup2(old_stderr, 2)
devnull.close()

print('Verbinde mit Kamera Pi 3...')

ret, frame = cap.read()

if ret:
    print('Verbindung erfolgreich - Bild empfangen!')
    cv2.imwrite('/home/raspi/test_stream.jpg', frame)
    print('Testbild gespeichert: test_stream.jpg')
else:
    print('Fehler - Laeuft der Stream auf Pi 3?')

cap.release()
