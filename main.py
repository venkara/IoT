import micropython
from machine import Pin
import time
import network
from umqtt.simple import MQTTClient
import config
import dht


# MQTT Parameters
MQTT_SERVER = config.mqtt_server
MQTT_PORT = 0
MQTT_USER = config.mqtt_username
MQTT_PASSWORD = config.mqtt_password
MQTT_CLIENT_ID = b"raspberrypi_picow"
MQTT_KEEPALIVE = 7200
MQTT_SSL = True   # set to False if using local Mosquitto MQTT broker
MQTT_SSL_PARAMS = {'server_hostname': MQTT_SERVER}
MQTT_ROOT = config.mqtt_root
MQTT_INTERVAL_MS = config.data_interval_sec * 1000
# Constants for MQTT Topics
MQTT_TOPIC_TEMPERATURE = MQTT_ROOT + b'-temp'
MQTT_TOPIC_HUMIDITY = MQTT_ROOT + b'-humidity'

# Initialize DHT
dhtPIN = 16
sensor = dht.DHT11(Pin(dhtPIN, Pin.OUT, Pin.PULL_UP))


def get_sensor_readings():
    #temp = random.randint(70, 100)
    #hum = random.randint(40, 70)
    sensor.measure()
    temperature = float(sensor.temperature())
    temperature = temperature * 1.8 + 32.0  # Convert from °C to °F
    humidity = float(sensor.humidity())
    return temperature, humidity


def initialize_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Connect to the network
    wlan.connect(ssid, password)

    # Wait for Wi-Fi connection
    connection_timeout = 30
    while connection_timeout > 0:
        if wlan.status() >= 3:
            break
        connection_timeout -= 1
        print('Waiting for Wi-Fi connection...')
        time.sleep(1)

    # Check if connection is successful
    if wlan.status() != 3:
        return False
    else:
        print('Connection successful!')
        network_info = wlan.ifconfig()
        print('IP address:', network_info[0])
        return True


def publish_mqtt(topic, value):
    mqtt_client.publish(topic, value)
    print(f"{value} --> {topic.decode('utf-8')}")
    time.sleep(2) # Delay to allow publish to finish
        
try:
    if not initialize_wifi(config.wifi_ssid, config.wifi_password):
        print('Error connecting to the network...  exiting program')
    else:
        # Create MQTT client
        mqtt_client = MQTTClient(client_id=MQTT_CLIENT_ID,
                            server=MQTT_SERVER,
                            port=MQTT_PORT,
                            user=MQTT_USER,
                            password=MQTT_PASSWORD,
                            keepalive=MQTT_KEEPALIVE,
                            ssl=MQTT_SSL,
                            ssl_params=MQTT_SSL_PARAMS)
        
        now_time = time.ticks_ms()
        while True:
            # Mark start time of next task
            print(f"Current time: {now_time}")
            scheduled_time = time.ticks_add(now_time, MQTT_INTERVAL_MS)

            # Read sensor data
            temperature, humidity = get_sensor_readings()

            # Connect to MQTT broker
            mqtt_client.connect()
            
            # Publish as MQTT payloads
            publish_mqtt(MQTT_TOPIC_TEMPERATURE, str(temperature))
            publish_mqtt(MQTT_TOPIC_HUMIDITY, str(humidity))
            
            # Disconnect from MQTT broker (AdafruitIO has a timeout, better to disconnect and reconnect)
            mqtt_client.disconnect()
            
            # Wait until scheduled time
            print(f"Waiting till {scheduled_time}...")
            while time.ticks_diff(scheduled_time, time.ticks_ms()) > 0:
                pass
            now_time = scheduled_time

except Exception as e:
    print('Error:', e)
    time.sleep(5)
    print('Attempting soft reset')    
    machine.reset()
