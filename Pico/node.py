import network
import utils
import ujson
import machine
import sys

boot_count = None
node_suffix = None
BOOT_COUNT_FILE = "bootcount.json"
RESET_CAUSE_STRS = {
    0: "PWRON_RESET",
    1: "HARD_RESET",
    2: "WDT_RESET",
    3: "DEEPSLEEP_RESET",
    4: "SOFT_RESET",
}


def initialize_node_identity():
    global node_suffix
    if node_suffix is not None:  # already initialized
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
    initialize_node_identity()  # ensure node identity is initialized
    return node_suffix


def get_boot_count():
    global boot_count

    if boot_count is None:
        try:
            with open(BOOT_COUNT_FILE, "r") as file:
                data = ujson.load(file)
            boot_count = int(data.get("boot_count", 0))
        except Exception as e:
            sys.print_exception(e)
            boot_count = 0

        reset_cause, _ = get_reset_cause()

        if (
            reset_cause < 2
        ):  # reset the boot count if it was a power-on reset or hard reset
            boot_count = 1
        else:
            boot_count += 1

        with open(BOOT_COUNT_FILE, "w") as file:
            ujson.dump({"boot_count": boot_count}, file)

    # print("boot_count: ", boot_count)
    return boot_count


def get_reset_cause():
    reset_cause = machine.reset_cause()
    reset_cause_str = RESET_CAUSE_STRS[reset_cause]
    return reset_cause, reset_cause_str
