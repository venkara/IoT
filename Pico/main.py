from machine import reset, reset_cause, WDT
import gc
import time
import networking
import utils
import config
import sensor
from mqtt import publish_readings


print("\n\n\nReset cause:", reset_cause())
print("-----------------------------")
gc.collect()
print("Free memory:", gc.mem_free())

# Set up heartbeat LED
utils.initialize_led()


if config.fahrenheit==True:
    temp_unit = "°F"
else:
    temp_unit = "°C"


try:
    if not networking.initialize_wifi(config.wifi_ssid, config.wifi_password):
        print("Initial WiFi failed. Reconnecting with backoff...")
        networking.reconnect_wifi(config.wifi_ssid, config.wifi_password)
  
    print("-----------------------------\n\n\n")
    print(f"Time\tTemp{temp_unit}\tRH%\tNet\tMem")



    while True:
        utils.feed_wdt()
        # Read sensor data
        temperature, humidity = sensor.get_sensor_readings()
        if config.fahrenheit is True:
            temperature = temperature * 1.8 + 32  # convert °C to °F

        # How's the wifi doing?
        networking.ensure_wifi()
        # Publish to MQTT broker
        publish_readings(temperature, humidity)
       
        gc.collect()
        #print(f"{now_time}\t{temperature:.2f}\t{humidity:.2f}\t{wifi_status}\t{gc.mem_free()}")          

        # Wait until next scheduled time
        wait_till_scheduled_event(config.mqtt_publish_interval * 1000)

except Exception as e:
    print('Error:', e)
    time.sleep(1)
    print('Attempting soft reset')
    reset()
