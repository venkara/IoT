import time
from machine import Pin, WDT
import config

led = None
ledState = False
wdt = None
wait_start_time = None


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


def wait_till_scheduled_event(delta_time):
    global wait_start_time
    if wait_start_time is None:
        wait_start_time = time.ticks_ms()

    scheduled_time = time.ticks_add(wait_start_time, delta_time * 1000)
    print(f'flag1: {wait_start_time}, flag2: {scheduled_time}, flag3: {time.ticks_ms()}')
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