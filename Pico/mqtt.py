from umqtt.simple import MQTTClient
import config
from utils import feed_wdt, wait_with_wdt
from socket import getaddrinfo
import node
import sys


mqtt_root = None
mqtt_client_id = None
mqtt_topic_temperature = None
mqtt_topic_humidity = None
node_suffix: str | None = None
   
def init_identity():
    global mqtt_root, mqtt_client_id, mqtt_topic_temperature, mqtt_topic_humidity

    if mqtt_root is not None:
        return # Already initialized

    node_suffix = node.get_node_suffix()
    assert node_suffix is not None, "Node suffix should not be None"
    mqtt_topic_root = (config.mqtt_topic_root + node_suffix).encode()
                                                            
    print("MQTT root:", mqtt_topic_root.decode())

    mqtt_client_id = ("Sensor_" + node_suffix).encode()
    print("MQTT client ID:", mqtt_client_id.decode())

    mqtt_addr = getaddrinfo(config.mqtt_server, 8883)
    
    print(f"MQTT server: ", config.mqtt_server, mqtt_addr)  # Test DNS resolution

    mqtt_topic_temperature = mqtt_topic_root + b't'
    mqtt_topic_humidity = mqtt_topic_root + b'h'

    print("MQTT topic for temperature:", mqtt_topic_temperature.decode())
    print("MQTT topic for humidity:", mqtt_topic_humidity.decode())
    return True


def publish_mqtt(mqtt_client,topic, value):
    mqtt_client.publish(topic, str(value))
    wait_with_wdt(1) # Delay to allow publish to complete

    
def publish_readings(temperature, humidity):
    init_identity() # lazy initialization of MQTT parameters

    for attempt in range(3):
        mqtt_client = None

        try:
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

            mqtt_client.connect()
            feed_wdt()
            publish_mqtt(mqtt_client, mqtt_topic_temperature, temperature)
            publish_mqtt(mqtt_client, mqtt_topic_humidity, humidity)
            mqtt_client.disconnect()
            return True

        except Exception as e:
            print("---------------- Exception ----------------")
            sys.print_exception(e)
            print("-------------------------------------------")
            try:
                if mqtt_client is not None:
                    mqtt_client.disconnect()
            except Exception:
                try:
                    mqtt_client.sock.close()
                except Exception:
                    pass
            feed_wdt()
    
    print("Too many MQTT failures, skipping publish for this cycle.")
    return False