import network
import config
import utils

node_suffix = None


def initialize_node_identity():
    global node_suffix
    if node_suffix is not None: # already initialized
        return
    
    wlan = network.WLAN(network.STA_IF)

    for _ in range(10):
        mac = wlan.config("mac")
        candidate_suffix = "".join("{:02X}".format(b) for b in mac[-3:])

        if candidate_suffix != "000000":
            node_suffix = candidate_suffix
            break

        print("MAC not ready, retrying...")
        utils.wait_with_wdt(1)

    if node_suffix is None:
        raise RuntimeError("Failed to read valid MAC address")

    print("Node ID:", node_suffix)



def get_node_suffix():
    initialize_node_identity() # ensure node identity is initialized
    return node_suffix