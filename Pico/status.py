import clock
import node
import time
import networking
import mqtt
import config
import errors

last_status_published_time: int | None = None
scheduled_time: int | None = None

def get_status():
    exception_counts = {}
    status = {
        "timestamp": clock.current_utc_iso(),
        "uptime_s": time.ticks_ms() // 1000,
        "rssi_dbm": networking.get_wifi_rssi(),
        "boot_count": node.get_boot_count(),
        "msg_queue": mqtt.get_publish_queue_length(),
        "type": "status"
    }
    exception_counts["ExceptionCounts"] = errors.get_exception_counts()
    status.update(exception_counts)
    return status


def maybe_publish_status():
    global scheduled_time
    if scheduled_time is None:
        mqtt.publish_diagnostics(get_status())
        scheduled_time = time.ticks_add(time.ticks_ms(), config.mqtt_status_interval * 1000)
        return True
    else:
        if time.ticks_ms() >= scheduled_time:
            mqtt.publish_diagnostics(get_status())
            scheduled_time = time.ticks_add(time.ticks_ms(), config.mqtt_status_interval * 1000)
            return True
        else:
            return False
    