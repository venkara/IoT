import time
from machine import Pin, WDT
import config
import gc
import rp2


led: Pin | None = None
led_state = False
wdt: WDT | None = None
wait_start_time: int | None = None
memory_baseline: int | None = None
memory_last_reported: int | None = None
wdt_allowed: bool | None = None
boot_sel = False
BOOT_TIME = time.ticks_ms()

def feed_wdt():
    global wdt, wdt_allowed, boot_sel

    if wdt_allowed is None:
        elapsed = time.ticks_diff(time.ticks_ms(), BOOT_TIME)

        if elapsed <= 10000:
            boot_sel = boot_sel or rp2.bootsel_button()
            return

        wdt_allowed = config.ENABLE_WDT and not boot_sel

        if wdt_allowed:
            wdt = WDT(timeout=8000)
            print("Watchdog enabled")
        elif boot_sel:
            print("Watchdog disabled (BOOTSEL held)")
        else:
            print("Watchdog disabled (config)")

    if wdt is not None:
        wdt.feed()


def wait_with_wdt(delay_seconds):
    for _ in range(delay_seconds * 2): # Check every 0.5 seconds
        feed_wdt()
        time.sleep_ms(500)
        toggle_led()  # heartbeats 


def wait_since_prev_event(delta_time):
    global wait_start_time
    if wait_start_time is None:
        wait_start_time = time.ticks_ms()

    scheduled_time = time.ticks_add(wait_start_time, delta_time * 1000)
    while time.ticks_diff(scheduled_time, time.ticks_ms()) > 0:
        feed_wdt()
        time.sleep_ms(500)
        toggle_led()  # heartbeats 

    wait_start_time = scheduled_time


def initialize_led():
    global led
    if led is None:
        led = Pin("LED", Pin.OUT)


def toggle_led():
    global led, led_state
    initialize_led()
    assert led is not None
    if led_state:
        led.off()
    else:
        led.on()
    led_state = not led_state



def track_memory_status(step_threshold=100, leak_threshold=2000):
    global memory_baseline, memory_last_reported
    gc.collect()
    current = gc.mem_free()

    if memory_baseline is None:
        memory_baseline = current
        memory_last_reported = current
        print(f"Free memory baseline: {current}")
        return
    assert memory_last_reported is not None
    change_since_last = current - memory_last_reported
    change_since_start = current - memory_baseline

    if abs(change_since_last) >= step_threshold:
        print(f"Free memory: {current} ({change_since_last:+})")
        memory_last_reported = current

    if change_since_start <= -leak_threshold:
        print(f"Possible memory leak: {current} ({change_since_start:+} from baseline)")
        memory_baseline = current
        memory_last_reported = current
