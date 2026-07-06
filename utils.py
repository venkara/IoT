import time
from machine import Pin

led = None
ledState = False
wdt = None

def set_wdt(new_wdt):
    global wdt
    wdt = new_wdt

def feed_wdt():
    if wdt:
        wdt.feed()

def wait_with_wdt(delay):
    for _ in range(delay):
        feed_wdt()
        time.sleep(1)



def initialize_led():
    global led, ledState
    led = Pin("LED", Pin.OUT)
    ledState = False

def toggle_led():
    global led, ledState
    if led is None:
        return

    ledState = not ledState

    if ledState:
        led.off()
    else:
        led.on()