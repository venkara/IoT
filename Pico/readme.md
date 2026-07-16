# Playa del Carmen Environmental Monitor (Pico W + MicroPython)

Personal home monitoring using multiple Raspberry Pi Pico W nodes. Each node reads a DHT22 (temperature/humidity) sensor and publishes JSON payloads to Adafruit IO via MQTT over TLS, then disconnects. Design emphasizes clarity, robustness, bounded RAM use, and strong diagnostics.

Status: v1.14 deployed and stable on three nodes.


## Highlights
- Multiple Pico W nodes; identity = last 3 bytes of MAC in uppercase hex (e.g., 131A17)
- DHT22 sensor readings with embedded ISO‑8601 UTC timestamps from the Pico
- In‑RAM bounded message queue (max 100), newest-first drain (LIFO)
- Non‑persistent MQTT: connect → drain queue → disconnect
- Robust Wi‑Fi connect logic with backoff, watchdog‑friendly waits, and DNS sanity check
- NTP time sync at boot and every 12 hours
- Diagnostics feed with boot, status, and exception payloads
- Anti‑recursive logging: MQTT failures are never reported via MQTT
- Minimal dependencies, readability over cleverness


## Hardware
- Raspberry Pi Pico W (RP2040)
- DHT22 connected to GPIO pin configured in config.py (default: GP16)
- Home Wi‑Fi (isolated IoT subnet); router forces Cloudflare DNS for reliability


## Software
- MicroPython v1.28.0 (2026‑04‑06) on Pico W
- Local copy of MicroPython’s umqtt.simple at umqtt_simple.py (TLS with SNI)
- Modules in this repo:
  - main.py: orchestrates startup, loop, and housekeeping
  - config.py: Wi‑Fi, Adafruit IO credentials, intervals, WDT enable
  - networking.py: Wi‑Fi init, backoff reconnect, DNS/TCP sanity check
  - mqtt.py: queueing, connect/drain/disconnect, diagnostics publishing
  - clock.py: NTP sync and UTC timestamp generation
  - sensor.py: DHT22 init and robust reads
  - errors.py: exception and message logging, counts, recursion guard
  - status.py: periodic status publishing (RSSI, queue length, exception counts)
  - node.py: node identity (MAC suffix), boot count, reset cause
  - utils.py: watchdog, LED heartbeat, pacing, memory tracking
  - dht.py: sensor driver (bundled)
  - umqtt_simple.py: MQTT client (slightly instrumented)


## Adafruit IO feeds and payloads
Topics/feeds are derived from a prefix and node suffix:
- Prefix (from config.py): rvenkat/feeds/tres-lunas.
- Node suffix: uppercase hex, e.g., 131A17
- Feeds:
  - Temperature: rvenkat/feeds/tres-lunas.131A17-t
  - Humidity:    rvenkat/feeds/tres-lunas.131A17-h
  - Diagnostics: rvenkat/feeds/tres-lunas.131A17-diagnostics

All payloads contain an embedded timestamp to ensure correct ordering on dashboards (never rely on Adafruit IO’s created_at).

Examples
- Measurement (temperature or humidity streams):
```
{ "reading": 28.42, "timestamp": "2026-07-13T15:58:39Z" }
```
- Boot diagnostics:
```
{ "Type":"boot", "Timestamp":"2026-07-13T15:58:39Z", "Firmware":"1.14", "BootCount":3, "ResetCause":"WDT_RESET", "FreeMemory":183000 }
```
- Exception payload:
```
{ "Type":"exception", "Timestamp":"2026-07-13T15:58:39Z", "SubsystemCode":"NTP", "Location":"sync_time:37", "ExcepType":"OSError", "Message":"ETIMEDOUT" }
```
- Status payload (every 30 min by default):
```
{ "type":"status", "timestamp":"2026-07-13T15:58:39Z", "uptime_s": 123456, "rssi_dbm": -43, "boot_count": 7, "msg_queue": 0, "ExceptionCounts": { "WiFi":0, "Sensor":0, "MQTT":1, "NTP":0, "Memory":0, "Unknown":0 } }
```


## Message queue and publish lifecycle
- queue_for_publish(topic, payload)
  - Appends message to an in‑RAM queue (max 100). If full, discards the oldest.
  - Immediately calls publish_queue().
- publish_queue()
  - If Wi‑Fi is disconnected, returns True (deferred; queue untouched).
  - If queue is empty, returns True.
  - Otherwise, up to 3 attempts:
    - Create TLS MQTT client (port 8883, SNI), connect.
    - While queue not empty: publish the newest message (LIFO), wait 1s between publishes.
    - On publish success, remove message. On failure, abort attempt and retry after 5s.
  - After 3 failures, print errors and keep messages cached for a future run.
- MQTT failures are printed and counted but never published via MQTT (recursion guard in errors.py).

Rationale: LIFO is acceptable because each payload embeds its own timestamp; bounded queue provides backpressure without unbounded RAM growth; non‑persistent sessions simplify recovery.


## Timekeeping
- NTP via ntptime.settime() at boot and every 12 hours.
- All timestamps originate on the Pico in ISO‑8601 UTC (YYYY‑MM‑DDThh:mm:ssZ).
- Before first NTP sync, times may look like 2021‑01‑01T00:00:xxZ; dashboards must sort by embedded timestamps.


## Logging and diagnostics
- Diagnostics feed aggregates:
  - Boot events (firmware version, boot count, reset cause, free memory)
  - Periodic status (RSSI, queue length, uptime, exception counts)
  - Exceptions with subsystem, approximate location, type, message
- Exception counting is local (RAM) and published via status.
- Anti‑recursion: SUBSYSTEM_MQTT exceptions/messages never attempt MQTT publishes.


## Web dashboard
Live dashboard: https://venkara.github.io/IoT/web/

Notes
- The dashboard reads from Adafruit IO and must sort by the embedded payload timestamps, not by created_at.
- Pre‑NTP timestamps may appear as 2021‑01‑01T00:00:xxZ; the dashboard should still render these in correct order using the payload times.
- Planned features include per‑node filtering and spreadsheet‑style status/log tables.


## Networking and DNS robustness
- Wi‑Fi init prefers IPv4 resolution and disables power‑save quirks.
- After connect, performs DNS lookup and TCP connect test to google.com:80 to catch early DNS/TCP problems.
- Reconnect uses staged backoff; after many failures, the device reboots.
- DNS is forced to Cloudflare on the router for the IoT subnet; firmware does not pin DNS.


## Watchdog, pacing, and LED heartbeat
- Watchdog enables ~10s after boot unless BOOTSEL is held or disabled in config.ENABLE_WDT.
- Timeout ~8s; all long waits use utils.wait_with_wdt() to feed WDT and blink LED.
- Draining large queues intentionally paces at ~1s/message to remain watchdog‑ and broker‑friendly.


## Setup and deployment
1) Install MicroPython v1.28.0 on Pico W.
2) Copy project files to the board (e.g., with mpremote, rshell, or Thonny). Ensure umqtt_simple.py is included.
3) Create/update config.py:
   - Wi‑Fi SSID/password
   - Adafruit IO username/key
   - mqtt_topic_prefix (e.g., b"your-aio-username/feeds/tres-lunas.")
   - Optional intervals and ENABLE_WDT
4) First boot will create/maintain bootcount.json.
5) main.py runs automatically; monitor the serial console for:
   - Node ID (MAC‑based suffix)
   - Wi‑Fi RSSI and IFCONFIG
   - NTP set confirmation
   - Boot diagnostics payload
   - Periodic measurement lines and memory tracker messages

Security note: config.py contains credentials. Keep it out of version control.


## File‑by‑file tour
- main.py: Startup sequence; sensor read/publish loop; housekeeping; reset on unhandled exception
- mqtt.py: Identity init; bounded queue; connect/drain/disconnect; diagnostics publish
- networking.py: Wi‑Fi attach; IPv4 preference; status strings; sanity TCP test; backoff reconnect; RSSI read
- clock.py: NTP sync; last‑sync tracking; UTC formatting
- sensor.py: Lazy DHT22 init; 3‑try read with simple outlier screening
- errors.py: Exception and message logging; local counts; recursion guard against MQTT self‑logging
- status.py: Periodic status payload with exception counts
- node.py: MAC‑based node suffix; boot count persistence; reset cause mapping
- utils.py: Watchdog feeding; heartbeat LED; paced waits; memory tracking helpers
- umqtt_simple.py: Local MQTT client (TLS + SNI)


## Development guidelines
- Prefer explicit, readable code over abstraction or cleverness
- Be conservative with error handling and logging; print enough to reconstruct issues later
- Avoid adding dependencies without clear value
- Maintain non‑persistent MQTT sessions and bounded in‑RAM queue
- Never generate MQTT diagnostics from MQTT failures


## Troubleshooting
- Wi‑Fi won’t connect:
  - Check SSID/password in config.py
  - Watch networking.initialize_wifi() logs for status changes and RSSI
- DNS/TCP test fails:
  - Router should force Cloudflare DNS on the IoT subnet; power‑cycle router if needed
  - Ensure the Pico has IPv4 address in IFCONFIG
- No timestamps or 2021‑01‑01 dates persist:
  - NTP may be blocked; verify outbound UDP/123; sync occurs at boot and every 12h
- Large backlog drains slowly:
  - Intentional 1s pacing; leave powered to drain; messages retain embedded timestamps


## Future improvements
- Dashboard: spreadsheet‑style status and log tables with per‑node filtering
- Diagnostics visualizations and DNS/MQTT reachability timing metrics
- Optional local ring buffer of last N diagnostics for post‑mortem after reboots
