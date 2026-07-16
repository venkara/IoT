import time
import ntptime
import utils
import errors

time_is_set = False
last_sync = None


def sync_time(max_attempts=3):
    global time_is_set, last_sync
    last_exception = None

    for attempt in range(max_attempts):
        try:
            ntptime.settime()  # sets RTC to UTC
            last_sync = time.time()
            time_is_set = True
            print("NTP time set:", current_utc_iso())
            return True

        except Exception as e:
            print(f"NTP sync {attempt+1} failed: {e}")
            last_exception = e
            utils.wait_with_wdt(5)

    if last_exception is not None:
        errors.log_exception(errors.SUBSYSTEM_NTP, last_exception, True)

    return False


def current_utc_iso():
    t = time.gmtime()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )


def is_time_set():
    return time_is_set


def maybe_sync_time():
    global last_sync

    if last_sync is None:
        return sync_time()

    # Resync every 12 hours
    if time.time() - last_sync > 12 * 3600:
        return sync_time()

    return True

    import ntptime
