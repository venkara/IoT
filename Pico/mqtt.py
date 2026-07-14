from umqtt_simple import MQTTClient
import config
from utils import feed_wdt, wait_with_wdt
import node
import sys
import ujson
import networking

mqtt_topic_prefix       = None
mqtt_client_id          = None
mqtt_topic_temperature  = None
mqtt_topic_humidity     = None
mqtt_topic_status       = None
mqtt_topic_log          = None


message_cache = []
MAX_CACHED_MESSAGES = 100



def init_identity():
    global mqtt_topic_prefix, mqtt_client_id
    global mqtt_topic_temperature, mqtt_topic_humidity
    global mqtt_topic_status, mqtt_topic_log

    if mqtt_topic_prefix is not None:  # Initialization already done
        return

    node_suffix = node.get_node_suffix().lower()
    node_suffix_bytes = node_suffix.encode()

    mqtt_topic_prefix = config.mqtt_topic_prefix + node_suffix_bytes
    mqtt_client_id = ("Sensor_" + node_suffix).encode()

    mqtt_topic_temperature = mqtt_topic_prefix + b"-t"
    mqtt_topic_humidity = mqtt_topic_prefix + b"-h"
    mqtt_topic_status = mqtt_topic_prefix + b"-status"
    mqtt_topic_log = mqtt_topic_prefix + b"-log"

    # print("MQTT topics:")
    # print(mqtt_topic_temperature.decode())
    # print(mqtt_topic_humidity.decode())
    # print(mqtt_topic_status.decode())
    # print(mqtt_topic_log.decode())
    return True


def publish_json(mqtt_client, topic, payload):
    try:
        message = ujson.dumps(payload).encode()
        mqtt_client.publish(topic, message)
        wait_with_wdt(1)
        return True
    
    except Exception as e:
        print("Publish failed:")
        sys.print_exception(e)
        return False

    
def publish_queue():
    init_identity()

    if not networking.is_connected():
        return True

    if not message_cache:  # Nothing to publish
        return True

    last_exception = None

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
                ssl_params={
                    "server_hostname": config.mqtt_server
                }
            )

            mqtt_client.connect()
            feed_wdt()

            while message_cache:
                cached = message_cache[-1]

                if  publish_json(mqtt_client, 
                                cached["topic"], 
                                cached["payload"]):
                    # Remove message from queue if it was sucessfully published
                    message_cache.pop()
                else:   
                    raise RuntimeError("Cached MQTT publish failed")

            mqtt_client.disconnect()
            return True

        except Exception as e:
            print(
                f"MQTT attempt {attempt + 1}/3 failed:"
            )
            sys.print_exception(e)
            last_exception = e

            try:
                if mqtt_client is not None:
                    mqtt_client.disconnect()
            except Exception:
                try:
                    mqtt_client.sock.close()
                except Exception:
                    pass

            wait_with_wdt(5)

    print("Too many MQTT failures; messages remain cached.")

    if last_exception is not None:
        sys.print_exception(last_exception)

    return False
    

def publish_log(payload):
    init_identity()  # Make sure we've initialized our topics
    return queue_for_publish(mqtt_topic_log, payload)
 


def queue_for_publish(topic, payload):
    global message_cache
  
    # Check queue length and discard oldest message if it's too long
    if get_publish_queue_length() >= MAX_CACHED_MESSAGES:
        tmp = message_cache.pop(0)
        print(f"Queue too long, discarding {tmp}")

    # Form new message and add it to the end of the queue
    message = {"topic": topic, "payload": payload}
    message_cache.append(message)

    return publish_queue()

def get_publish_queue_length():
    return len(message_cache)