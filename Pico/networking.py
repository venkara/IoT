import network
from utils import wait_with_wdt, feed_wdt
from machine import reset

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
        4: "Failed to connect to a network"
    }
    return status_strings.get(status_code, "Unknown") 


def initialize_wifi(ssid, password, timeout=30):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wait_with_wdt(1)
    # Connect to the network
    wlan.connect(ssid, password)

    # Wait for Wi-Fi connection

    while timeout > 0:
        wifi_status = wlan.status()
        if wifi_status >= 3:
            break
        timeout -= 1
        print(f'Waiting for Wi-Fi connection... {wifi_status_string(wifi_status)}')
        wait_with_wdt(1)

    # Check if connection is successful
    if wifi_status != 3:
        print(f'Failed to connect: {wifi_status_string(wifi_status)}')
        return False
    else:
        network_info = wlan.ifconfig()
        print('Connection successful! IP address:', network_info[0])
        print("RSSI:", wlan.status('rssi'))

        return True




def reconnect_wifi(ssid, password):
    for delay, attempts in BACKOFF_DELAYS:
        for _ in range(attempts):
            if initialize_wifi(ssid, password, timeout=30):
                return True

            print(f"Waiting {delay} seconds before next attempt...")
            wait_with_wdt(delay)

    print("Too many failures, rebooting")
    reset()