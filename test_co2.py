from scd30_i2c import SCD30
import time

scd30 = SCD30()
scd30.set_measurement_interval(2)
scd30.start_periodic_measurement()

print("Warte auf Messung...")
time.sleep(3)

for i in range(10):
    if scd30.get_data_ready():
        m = scd30.read_measurement()
        if m is not None:
            print(f"CO2:         {m[0]:.0f} ppm")
            print(f"Temperatur:  {m[1]:.1f} °C")
            print(f"Luftfeuchte: {m[2]:.1f} %")
            break
    print(f"Versuch {i+1}: warte...")
    time.sleep(2)
