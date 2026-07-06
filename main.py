from machine import reset, reset_cause, WDT
import gc
import time
import networking
import utils
import config
import sensor
from mqtt import setup_node_identity, publish_readings
DEBUG_NO_WDT = True


# MAIN 
print("Reset cause:", reset_cause())
print("-----------------------------\n\n\n")
gc.collect()
print("Free memory:", gc.mem_free())

# initialize the DHT22 sensor on pin 16
sensor.initialize_dht22(16)

# Set up heartbeat LED
utils.initialize_led()

# MQTT Parameters
setup_node_identity()
mqtt_interval_ms = config.data_interval_sec * 1000

# 8 second timeout for watchdog
if not DEBUG_NO_WDT:
    wdt = WDT(timeout=8000)
else:
    wdt = None
utils.set_wdt(wdt)


try:
    if not networking.initialize_wifi(config.wifi_ssid, config.wifi_password):
        print("Initial WiFi failed. Reconnecting with backoff...")
        networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)
    else:
        print("-----------------------------\n\n\n")
        print(f"Time\tTemp°F\tRH%\tNet\tMem")
        mqtt_failures = 0
        now_time = time.ticks_ms()

        while True:
            utils.feed_wdt()
            # Read sensor data
            temperature, humidity = sensor.get_sensor_readings()
            temperature = temperature * 1.8 + 32  # convert °C to °F
            utils.feed_wdt()

            # How's the wifi doing?
            wifi_status = networking.status()
            if wifi_status != 3:
                print("WiFi lost. Reconnecting with backoff...")
                networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)
                
            # Publish to MQTT broker
            if publish_readings(temperature, humidity):
                mqtt_failures = 0
            else:
                mqtt_failures += 1
                if mqtt_failures >= 3:
                    print("Too many MQTT failures, rebooting")
                    reset()
                continue
            
            utils.feed_wdt()
            gc.collect()
            print(f"{now_time}\t{temperature:.2f}\t{humidity:.2f}\t{wifi_status}\t{gc.mem_free()}")          

            # Wait until scheduled time
            scheduled_time = time.ticks_add(now_time, mqtt_interval_ms)

            while time.ticks_diff(scheduled_time, time.ticks_ms()) > 0:
                utils.feed_wdt()
                time.sleep_ms(500)
                utils.toggle_led()  # heartbeats 

            now_time = scheduled_time

except Exception as e:
    print('Error:', e)
    time.sleep(1)
    print('Attempting soft reset')
    reset()
