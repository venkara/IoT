from machine import reset, reset_cause
import time
import networking
import utils
import config
import sensor
import mqtt
import sys
import clock

print("Reset cause:", reset_cause())
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
#    print(f"Time\t\t\tTemp°C\tRH%")

    while True:
        utils.feed_wdt()
        
        # Read sensor data
        timestamp, temperature, humidity = sensor.get_sensor_readings()

        networking.ensure_wifi(config.wifi_ssid, config.wifi_password) # How's the wifi doing?
        mqtt.publish_readings(temperature, humidity)      # Publish to MQTT broker

        # Housekeeping tasks
        clock.maybe_sync_time()
        utils.track_memory_status()

        print(f"{timestamp}\t{temperature:.2f}°C\t{humidity:.2f}%")          

        # Wait until next scheduled reading
        utils.wait_since_prev_event(config.mqtt_publish_interval)

except Exception as e:
    print("---------------- Exception ----------------")
    sys.print_exception(e)
    print("-------------------------------------------")
    time.sleep(1)
    print('Attempting soft reset')
    reset()
