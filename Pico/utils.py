import time
from machine import Pin, WDT
import config
import gc

led = None
ledState = False
wdt = None
wait_start_time = None
memory_baseline = None
memory_last_reported = None

def feed_wdt():
    global wdt
    if wdt is None and not config.DEBUG_NO_WDT:
        wdt = WDT(timeout=8000)

    if wdt is not None:
        wdt.feed()


def wait_with_wdt(delay):
    for _ in range(delay*2):
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
    global led, ledState
    initialize_led()
    if ledState:
        led.off()
    else:
        led.on()
    ledState = not ledState



def track_memory_status(step_threshold=100, leak_threshold=2000):
    global memory_baseline, memory_last_reported
    gc.collect()
    current = gc.mem_free()

    if memory_baseline is None:
        memory_baseline = current
        memory_last_reported = current
        print(f"Free memory baseline: {current}")
        return

    change_since_last = current - memory_last_reported
    change_since_start = current - memory_baseline

    if abs(change_since_last) >= step_threshold:
        print(f"Free memory: {current} ({change_since_last:+})")
        memory_last_reported = current

    if change_since_start <= -leak_threshold:
        print(f"Possible memory leak: {current} ({change_since_start:+} from baseline)")
        memory_baseline = current
        memory_last_reported = current