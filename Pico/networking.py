import network
from utils import wait_with_wdt, feed_wdt
from machine import reset
import socket
import sys
import errors

BACKOFF_DELAYS = [
    (5, 3),
    (10, 3),
    (30, 3),
    (60, 5),
    (300, 100),
]


def is_connected():
    return network.WLAN(network.STA_IF).status() == 3


def status():
    return network.WLAN(network.STA_IF).status()


def wifi_status_string(status_code):
    status_strings = {
        0: "Not enabled",
        1: "Currently scanning for networks",
        2: "Connecting to a network",
        3: "Connected to a network",
        4: "Failed to connect to a network",
    }
    return status_strings.get(status_code, "Unknown")


def ensure_wifi(ssid, password):
    if is_connected():
        return True

    print("WiFi not connected. Reconnecting...")
    return reconnect_wifi(ssid, password)


def initialize_wifi(ssid, password, timeout=30):

    print(f"Initializing Wi-Fi connection to SSID: {ssid}")
    network.country("US")
    wlan = network.WLAN(network.STA_IF)
    # Force the stack to resolve names strictly via IPv4
    # This bypasses the multi-second IPv6 timeout loop
    try:
        network.ipconfig(prefer=network.IPCONFIG_V4)
        print("Enforced IPv4 priority.")
    except AttributeError:
        # Older firmware compatibility fallback
        pass

    wlan.active(True)
    wlan.config(pm=0xA11140)

    wait_with_wdt(2)  # Wait for the interface to become active
    # Connect to the network
    wlan.connect(ssid, password)

    # Wait for Wi-Fi connection
    while timeout > 0:
        wait_with_wdt(2)
        wifi_status = wlan.status()
        if wifi_status >= 3:
            break
        timeout -= 2
        print(f"Waiting for Wi-Fi connection... {wifi_status_string(wifi_status)}")

    # Check if connection is successful
    if wifi_status != 3:
        print(f"Failed to connect: {wifi_status_string(wifi_status)}")
        return False
    else:
        network_info = wlan.ifconfig()
        print("Connection successful!")
        print(f"Received Signal Strength Indicator: {wlan.status('rssi')}dBm")
        print("IFCONFIG:", network_info)
        print(
            "Waiting 6 seconds for network to stabilize before testing TCP connection..."
        )
        wait_with_wdt(6)
        return test_wifi_connection()


def test_wifi_connection():
    s = None
    try:
        print("Testing DNS Lookup to google.com...  ", end="")
        addr = socket.getaddrinfo("google.com", 80)[0][-1]
        print(addr)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Socket created. ", end="")
        s.connect(addr)
        print("TCP connect worked. ", end="")
        s.close()
        print("Socket closed")
        return True

    except Exception as e:
        print("TCP test failed: ", end="")
        sys.print_exception(e)
        errors.log_exception(errors.SUBSYSTEM_WIFI, e, True)
        return False

    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def reconnect_wifi(ssid, password):

    errors.log_message(
        errors.SUBSYSTEM_WIFI, "Lost WiFi. Attempting to reconnect.", True
    )
    for delay, attempts in BACKOFF_DELAYS:
        for _ in range(attempts):
            if initialize_wifi(ssid, password, timeout=30):
                return True

            print(f"Waiting {delay} seconds before next attempt...")
            wait_with_wdt(delay)

    print("Too many failures, rebooting")
    reset()


def get_wifi_rssi():
    wlan = network.WLAN(network.STA_IF)
    return wlan.status("rssi")
