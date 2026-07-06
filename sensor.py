from machine import Pin
import utils
import dht

ht_sensor = None

def initialize_dht22(pin_number):
    global ht_sensor
    dht_pin = Pin(pin_number, Pin.OUT, Pin.PULL_UP)
    ht_sensor = dht.DHT22(dht_pin)


def get_sensor_readings():
    if ht_sensor is None:
        raise RuntimeError("DHT22 sensor not initialized")
    
    for attempt in range(3):
        try:
            ht_sensor.measure()
            utils.feed_wdt()
            temperature = float(ht_sensor.temperature())
            humidity = float(ht_sensor.humidity())
            if (temperature >50) or (temperature < 5) or (humidity < 5):
                print("Invalid reading, retrying...")
                utils.wait_with_wdt(1)
                utils.feed_wdt()
                continue

            return temperature, humidity

        except Exception as e:
            print("Sensor error:", e)
            utils.wait_with_wdt(1)
            utils.feed_wdt()

    raise RuntimeError("Failed to obtain valid sensor reading")
