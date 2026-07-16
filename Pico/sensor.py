from machine import Pin
import utils
import dht
import config
import clock
import errors

ht_sensor: dht.DHT22 | None = None


def initialize_dht22():
    global ht_sensor
    if ht_sensor is not None:
        return  # Sensor already initialized
    dht_pin = Pin(config.dht22_pin, Pin.OUT, Pin.PULL_UP)
    ht_sensor = dht.DHT22(dht_pin)
    utils.feed_wdt()


def get_sensor_readings():
    initialize_dht22()  # Lazy initialization of the sensor
    last_exception = None
    assert ht_sensor is not None
    for attempt in range(3):
        try:
            timestamp = clock.current_utc_iso()
            ht_sensor.measure()
            temperature = float(ht_sensor.temperature())
            humidity = float(ht_sensor.humidity())
            if (temperature > 50) or (temperature < 5) or (humidity < 5):
                print("Invalid reading, retrying...", attempt + 1)
                utils.wait_with_wdt(1)
                continue
            return timestamp, temperature, humidity

        except Exception as e:
            print("Sensor error:", e)
            last_exception = e
            utils.wait_with_wdt(1)

    if last_exception is not None:
        errors.log_exception(errors.SUBSYSTEM_SENSOR, last_exception, True)
        return None
