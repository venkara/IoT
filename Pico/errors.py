import sys
import mqtt
import clock
import config

SUBSYSTEM_NONE = 0
SUBSYSTEM_WIFI = 1
SUBSYSTEM_SENSOR = 2
SUBSYSTEM_MQTT = 3
SUBSYSTEM_NTP = 4
SUBSYSTEM_MEMORY = 5
SUBSYSTEM_UNKNOWN = 99

subsystem_names = {
    SUBSYSTEM_NONE: "None",
    SUBSYSTEM_WIFI: "WiFi",
    SUBSYSTEM_SENSOR: "Sensor",
    SUBSYSTEM_MQTT: "MQTT",
    SUBSYSTEM_NTP: "NTP",
    SUBSYSTEM_MEMORY: "Memory",
    SUBSYSTEM_UNKNOWN: "Unknown"
}


last_exception = None

exception_counts = {
    SUBSYSTEM_WIFI: 0,
    SUBSYSTEM_SENSOR: 0,
    SUBSYSTEM_MQTT: 0,
    SUBSYSTEM_NTP: 0,
    SUBSYSTEM_MEMORY: 0,
    SUBSYSTEM_UNKNOWN: 0
}

def log_exception(subsystem_code, e, publish=True):
    global last_exception, exception_counts
    location = None
    try:
        frame = sys._getframe(1)

        location = (
            f"{frame.f_code.co_name}"
            f":{frame.f_lineno}"
        )
    except Exception:
        location = "unknown"

    payload = {
        "Timestamp":        clock.current_utc_iso(),
        "Type":             "exception",
        "SubsystemCode":    subsystem_names[subsystem_code],
        "Location":         location,
        "ExcepType":        type(e).__name__,
        "Message":          str(e)
    }
    
    exception_counts[subsystem_code] += 1
    last_exception = e
    if publish:
        mqtt.publish_diagnostics(payload)
    return
    

def log_message(subsystem_code, message, publish=True):
    payload = {
        "Timestamp":        clock.current_utc_iso(),
        "Type":             "message",
        "SubsystemCode":    subsystem_names[subsystem_code],
        "Message":          message
    }
    if publish:
        mqtt.publish_diagnostics(payload)
    return

def get_exception_counts():
    payload = {
        subsystem_names[subsystem]: count
        for subsystem, count
        in exception_counts.items()
    }
    return payload