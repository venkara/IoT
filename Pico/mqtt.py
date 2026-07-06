import network
from umqtt.simple import MQTTClient
import config
import utils


mqtt_root = None
mqtt_client_id = None
mqtt_topic_temperature = None
mqtt_topic_humidity = None

def setup_node_identity():
    global mqtt_root, mqtt_client_id, mqtt_topic_temperature, mqtt_topic_humidity
   
    wlan = network.WLAN(network.STA_IF)
    mac = wlan.config('mac')
    node_suffix = ''.join('{:02X}'.format(b) for b in mac[-3:])

    sensor_number = config.SENSOR_NUMBERS.get(node_suffix)

    if sensor_number is None:
        raise RuntimeError("Unknown MAC suffix: " + node_suffix)

    mqtt_root = ("rvenkat/feeds/tres-lunas." + str(sensor_number)).encode()
    mqtt_client_id = ("Sensor_" + node_suffix).encode()
    mqtt_topic_temperature = mqtt_root + b't'
    mqtt_topic_humidity = mqtt_root + b'h'

    print("Node ID:", node_suffix)
    print("Sensor Number:", sensor_number)
    print("MQTT root:", mqtt_root.decode())
    print("MQTT client ID:", mqtt_client_id.decode())
    return True


def publish_mqtt(mqtt_client,topic, value):
    mqtt_client.publish(topic, str(value))
    utils.wait_with_wdt(1) # Delay to allow publish to complete

    
def publish_readings(temperature, humidity):

    if mqtt_root is None:
        raise RuntimeError("MQTT node identity not initialized")

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
        #print("Connecting MQTT...")
        mqtt_client.connect()
        utils.feed_wdt()

        publish_mqtt(mqtt_client, mqtt_topic_temperature, temperature)
        utils.feed_wdt()

        publish_mqtt(mqtt_client, mqtt_topic_humidity, humidity)
        utils.feed_wdt()

        mqtt_client.disconnect()
        return True

    except Exception as e:
        print("MQTT error:", e)

        try:
            mqtt_client.disconnect()
        except:
            pass

        return False


