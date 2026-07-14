from machine import reset, reset_cause
import time
import networking
import utils
import config
import sensor
import mqtt
import sys
import clock
import node
import status
import errors

FIRMWARE_VERSION = "1.0.0.2"


cause, cause_str = node.get_reset_cause()
print("Reset cause: ", cause_str)
print("-----------------------------")
utils.feed_wdt()

try:
    if not networking.initialize_wifi(config.wifi_ssid, config.wifi_password):
        print("Initial WiFi connect failed. Reconnecting with backoff...")
        networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)

    # Sync time with NTP server on startup
    clock.sync_time()

    # Set up MQTT identity
    mqtt.init_identity()

    print("-----------------------------\n\n\n")

    while True:
        utils.feed_wdt()
        
        # Read sensor data
        timestamp, temperature, humidity = sensor.get_sensor_readings()

        # How's the wifi doing?
        networking.ensure_wifi(config.wifi_ssid, config.wifi_password)
        
        mqtt.publish_dictionary(mqtt.mqtt_topic_temperature, {"reading": temperature,"timestamp": timestamp})
        mqtt.publish_dictionary(mqtt.mqtt_topic_humidity, {"reading": humidity,"timestamp": timestamp})

        # Housekeeping tasks
        clock.maybe_sync_time()
        utils.track_memory_status()
        status.maybe_publish_status()

        print(f"{timestamp}\t{temperature:.2f}°C\t{humidity:.2f}%")          

        # Wait until next scheduled reading
        utils.wait_since_prev_event(config.mqtt_publish_interval)

except Exception as e:
    print("---------------- Exception ----------------")
    sys.print_exception(e)
    print("-------------------------------------------")
    errors.log_exception(errors.SUBSYSTEM_UNKNOWN, e, True)
    time.sleep(1)
    print('Attempting soft reset')
    reset()
