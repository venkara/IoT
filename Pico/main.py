from machine import reset, reset_cause
import gc
import time
import networking
import utils
import config
import sensor
import mqtt
import sys
import clock

print("\n\n\nReset cause:", reset_cause())
print("-----------------------------")

if config.fahrenheit==True:
    temp_unit = "°F"
else:
    temp_unit = "°C"


try:
    if not networking.initialize_wifi(config.wifi_ssid, config.wifi_password):
        print("Initial WiFi connect failed. Reconnecting with backoff...")
        networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)

    # Sync time with NTP server on startup
    clock.sync_time()

    # Set up MQTT identity
    mqtt.init_identity()

    print("-----------------------------\n\n\n")
    print(f"Time\t\t\tTemp{temp_unit}\tRH%")

    while True:
        utils.feed_wdt()

        # Read sensor data
        temperature, humidity = sensor.get_sensor_readings()
        if config.fahrenheit is True:
            temperature = temperature * 1.8 + 32  # convert °C to °F

        networking.ensure_wifi(config.wifi_ssid, config.wifi_password) # How's the wifi doing?

        timestamp = clock.current_utc_iso()
        mqtt.publish_readings(temperature, humidity)      # Publish to MQTT broker
        print(f"{timestamp}\t{temperature:.2f}\t{humidity:.2f}")          

        clock.maybe_sync_time()
        utils.track_memory_status()

        # Wait until next scheduled time
        utils.wait_since_prev_event(config.mqtt_publish_interval)

except Exception as e:
    print("---------------- Exception ----------------")
    sys.print_exception(e)
    print("-------------------------------------------")
    time.sleep(1)
    print('Attempting soft reset')
    reset()
