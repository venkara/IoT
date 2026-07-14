from machine import reset
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
import gc
import node

FIRMWARE_VERSION = "1.14"

print("-----------------------------\n\n\n")
cause, cause_str = node.get_reset_cause()
utils.feed_wdt()
node.initialize_node_identity()

try:
    if not networking.initialize_wifi(config.wifi_ssid, config.wifi_password):
        print("Initial WiFi connect failed. Reconnecting with backoff...")
        networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)

    # Sync time with NTP server on startup
    clock.sync_time()

    # Set up MQTT identity
    mqtt.init_identity()
    
    payload = {
        "Type":         "boot",
        "Timestamp":    clock.current_utc_iso(),
        "Firmware":     FIRMWARE_VERSION,
        "BootCount":    node.get_boot_count(),
        "ResetCause":   cause_str,
        "FreeMemory":   gc.mem_free()
    }
    print(payload)
    mqtt.publish_diagnostics(payload)

    print("-----------------------------\n\n\n")

    while True:
        utils.feed_wdt()
        
        # Read sensor data
        timestamp, temperature, humidity = sensor.get_sensor_readings()

        # How's the wifi doing?
        networking.ensure_wifi(config.wifi_ssid, config.wifi_password)
        
        mqtt.queue_for_publish(mqtt.mqtt_topic_temperature, {"reading": temperature,"timestamp": timestamp})
        mqtt.queue_for_publish(mqtt.mqtt_topic_humidity, {"reading": humidity,"timestamp": timestamp})

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
    print('Attempting reset')
    reset()
