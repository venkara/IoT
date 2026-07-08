import network
from umqtt.simple import MQTTClient
import config
from utils import feed_wdt, wait_with_wdt
from socket import getaddrinfo
import node

mqtt_root = None
mqtt_client_id = None
mqtt_topic_temperature = None
mqtt_topic_humidity = None

   
def initialize_mqtt():
    global mqtt_root, mqtt_client_id

    if mqtt_root is not None:
        return # Already initialized

    sensor_number = node.get_sensor_number()
    node_suffix = node.get_node_suffix()

    mqtt_root = config.mqtt_root + str(sensor_number).encode()
    print("MQTT root:", mqtt_root.decode())
    mqtt_client_id = ("Sensor_" + node_suffix).encode()
    print("MQTT client ID:", mqtt_client_id.decode())
    mqtt_addr = getaddrinfo(config.mqtt_server, 8883)
    print(f"Adafruit MQTT server: ", mqtt_addr)  # Test DNS resolution
    mqtt_topic_temperature = mqtt_root + b't'
    mqtt_topic_humidity = mqtt_root + b'h'

    return True


def publish_mqtt(mqtt_client,topic, value):
    
    mqtt_client.publish(topic, str(value))
    wait_with_wdt(1) # Delay to allow publish to complete

    
def publish_readings(temperature, humidity):

    initialize_mqtt() # lazy initialization of MQTT parameters
    mqtt_failures = 0
    mqtt_client = MQTTClient(
        client_id=mqtt_client_id,
        server=config.mqtt_server,
        port=8883,
        user=config.mqtt_username,
        password=config.mqtt_password,
        keepalive=7200,
        ssl=True,
        ssl_params={'server_hostname': config.mqtt_server}
    )

    try:
        mqtt_client.connect()
        feed_wdt()

        publish_mqtt(mqtt_client, mqtt_topic_temperature, temperature)
        feed_wdt()

        publish_mqtt(mqtt_client, mqtt_topic_humidity, humidity)
        feed_wdt()

        mqtt_client.disconnect()
        return True

    except Exception as e:
        print("MQTT error:", e)
        mqtt_failures += 1
        if mqtt_failures >= 3:
            print("Too many MQTT failures, rebooting")
            reset()
        else:
            try:
                mqtt_client.socket().close()
                mqtt_client.disconnect()
                feed_wdt()
            except:
                pass

        return False