from machine import Pin
import utils
import dht
import config
import node 

ht_sensor = None

def initialize_dht22():
    global ht_sensor
    if ht_sensor is not None:
        return # Sensor already initialized
    dht_pin = Pin(config.dht22_pin, Pin.OUT, Pin.PULL_UP)
    ht_sensor = dht.DHT22(dht_pin)
    utils.feed_wdt()


def get_sensor_readings():
    initialize_dht22() # Lazy initialization of the sensor

    for attempt in range(3):
        try:
            ht_sensor.measure()
            temperature = float(ht_sensor.temperature())
            humidity = float(ht_sensor.humidity())
            if (temperature >50) or (temperature < 5) or (humidity < 5):
                print("Invalid reading, retrying...")
                utils.wait_with_wdt(1)
                continue

            # Apply calibration offsets for the sensor
            temp_offset = config.SENSOR_TEMP_CAL.get(node.get_sensor_number(), 0.0)
            humidity_offset = config.SENSOR_RH_CAL.get(node.get_sensor_number(), 0.0)
            temperature = temperature + temp_offset
            humidity = humidity + humidity_offset
            return temperature, humidity

        except Exception as e:
            print("Sensor error:", e)
            utils.wait_with_wdt(1)

    raise RuntimeError("Failed to obtain valid sensor reading")
