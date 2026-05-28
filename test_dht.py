import pigpio
import DHT22
import time

pi = pigpio.pi()

# Internen Pull-up auf GPIO4 aktivieren
pi.set_pull_up_down(4, pigpio.PUD_UP)

s = DHT22.sensor(pi, 4)

time.sleep(1)  # Sensor aufwärmen lassen

for i in range(10):
    s.trigger()
    time.sleep(0.5)
    temp = s.temperature()
    humi = s.humidity()
    if temp != -999:
        print(f"Temperatur: {temp:.1f} °C")
        print(f"Luftfeuchte: {humi:.1f} %")
        break
    else:
        print(f"Versuch {i+1}: kein Signal...")

s.cancel()
pi.stop()
