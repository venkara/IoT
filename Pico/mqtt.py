from umqtt_simple import MQTTClient
import config
from utils import feed_wdt, wait_with_wdt
from socket import getaddrinfo
import node
import sys
import ujson
import clock
import errors

mqtt_topic_prefix       = None
mqtt_client_id          = None
mqtt_topic_temperature  = None
mqtt_topic_humidity     = None
node_suffix: str | None = None
mqtt_topic_status       = None
mqtt_topic_log          = None

def init_identity():
    global mqtt_topic_prefix, mqtt_client_id, mqtt_topic_temperature, mqtt_topic_humidity, mqtt_topic_status, mqtt_topic_log

    if mqtt_topic_prefix is not None:
        return # Already initialized

    node_suffix = node.get_node_suffix().lower()

    assert node_suffix is not None, "Node suffix should not be None"
    mqtt_topic_prefix = config.mqtt_topic_prefix + (node_suffix).encode()
                                                            
    print("MQTT topic prefix:", mqtt_topic_prefix.decode())

    mqtt_client_id = ("Sensor_" + node_suffix).encode()
    print("MQTT client ID:", mqtt_client_id.decode())

    mqtt_addr = getaddrinfo(config.mqtt_server, 8883)
    print(f"MQTT server: ", config.mqtt_server, mqtt_addr)  # Test DNS resolution

    mqtt_topic_temperature  = config.mqtt_topic_prefix + node_suffix + b"-t"
    mqtt_topic_humidity     = config.mqtt_topic_prefix + node_suffix + b"-h"
    mqtt_topic_status       = config.mqtt_topic_prefix + node_suffix + b"-status"
    mqtt_topic_log          = config.mqtt_topic_prefix + node_suffix + b"-log"

    print("MQTT topics:")
    print(mqtt_topic_temperature.decode())
    print(mqtt_topic_humidity.decode())
    print(mqtt_topic_status.decode())
    print(mqtt_topic_log.decode())
    return True


def publish_json(mqtt_client, topic, payload):
    try:
        message = ujson.dumps(payload).encode()
    except Exception as e:
        print("JSON encoding failed:")
        sys.print_exception(e)
        return False

    mqtt_client.publish(topic, message)
    wait_with_wdt(1)

    return True


def publish_dictionary(topic, payload):
    init_identity()
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
                ssl_params={"server_hostname": config.mqtt_server}
            )

            mqtt_client.connect()
            feed_wdt()

            publish_json(
                mqtt_client,
                topic,
                payload
            )

            mqtt_client.disconnect()
            return True

        except Exception as e:
            print(
                "MQTT publish attempt "
                f"{attempt + 1}/3 failed:"
            )
            sys.print_exception(e)
            last_exception = e

            try:
                if mqtt_client is not None:
                    mqtt_client.disconnect()
            except Exception:
                try:
                    if mqtt_client is not None and mqtt_client.sock is not None:
                        mqtt_client.sock.close()
                except Exception:
                    pass
            wait_with_wdt(5)

    print("Too many MQTT failures; skipping publish.")

    if last_exception is not None:
        print("Final MQTT exception:")
        sys.print_exception(last_exception)
        log_exception(SUBSYSTEM_MQTT, last_exception, False)  # Don't try to publish errors from MQTT to avoid recursion
    return False

    

def publish_log(payload):
    init_identity()  # Make sure we've initialized our topics.
    return publish_dictionary(mqtt_topic_log, payload)
 