"""
LAB 6: Smart RFID System with Cloud & SD Logging
ESP32 + MicroPython (Thonny)

DEBUG VERSION — includes CHECKPOINT prints to isolate where execution
freezes. Once the freeze point is found, these can be removed.
"""

from machine import Pin, SPI
from mfrc522 import MFRC522
import network
import urequests
import ujson
import time
import os
import sdcard

print("CHECKPOINT 0 - imports done")

# ─── SD CARD CONFIG ────────────────────────────────────────
SD_SCK = 14
SD_MOSI = 15
SD_MISO = 2
SD_CS = 13
CSV_PATH = "/sd/attendance.csv"

# ─── SD CARD SETUP ─────────────────────────────────────────
sd_spi = SPI(2, baudrate=1000000, sck=Pin(SD_SCK), mosi=Pin(SD_MOSI), miso=Pin(SD_MISO))
sd_cs = Pin(SD_CS)
sd_ok = False
try:
    sd = sdcard.SDCard(sd_spi, sd_cs)
    vfs = os.VfsFat(sd)
    os.mount(vfs, "/sd")
    sd_ok = True
    print("SD card mounted at /sd")
    try:
        os.stat(CSV_PATH)
    except OSError:
        with open(CSV_PATH, "w") as f:
            f.write("UID,Name,StudentID,Major,DateTime\n")
        print("Created new CSV with header")
except OSError as e:
    print("SD card mount failed:", e)

print("CHECKPOINT 1 - after SD setup")

# ─── WIFI CONFIG ───────────────────────────────────────────
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, PASSWORD)
print("Connecting WiFi", end="")
while not wifi.isconnected():
    print(".", end="")
    time.sleep(0.5)
print("\nConnected:", wifi.ifconfig())

print("CHECKPOINT 2 - after WiFi connect")

# ─── TIME SYNC ─────────────────────────────────────────────
TIMEZONE_OFFSET_HOURS = 7  # Phnom Penh = UTC+7

try:
    import ntptime
    ntptime.settime()  # sets RTC to UTC
    print("Time synced via NTP")
except Exception as e:
    print("NTP sync failed:", e)

print("CHECKPOINT 3 - after time sync")


def get_datetime_string():
    t = time.localtime(time.time() + TIMEZONE_OFFSET_HOURS * 3600)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )


# ─── FIRESTORE CONFIG ──────────────────────────────────────
PROJECT_ID = "rfid-g2"
FIRESTORE_COLLECTION = "rfid_logs"
url = "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents/{}".format(
    PROJECT_ID, FIRESTORE_COLLECTION
)

print("CHECKPOINT 4 - after firestore config")


def send_to_firestore(uid, info, dt_string):
    data = {
        "fields": {
            "UID": {"stringValue": uid},
            "Name": {"stringValue": info["name"]},
            "StudentID": {"stringValue": info["student_id"]},
            "Major": {"stringValue": info["major"]},
            "DateTime": {"stringValue": dt_string},
        }
    }
    try:
        res = urequests.post(url, json=data)
        print("Sent to Firestore:", res.status_code)
        res.close()
        return True
    except Exception as e:
        print("Error sending to Firestore:", e)
        return False


# ─── RFID SETUP ────────────────────────────────────────────
spi = SPI(1, baudrate=1000000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
rdr = MFRC522(spi=spi, gpioRst=Pin(22), gpioCs=Pin(16))

print("CHECKPOINT 5 - after RFID setup")

# ─── BUZZER SETUP ──────────────────────────────────────────
BUZZER_PIN = 4
VALID_BUZZ_SEC = 0.3
INVALID_BUZZ_SEC = 3.0

buzzer = Pin(BUZZER_PIN, Pin.OUT)
buzzer.value(0)


def buzz(seconds):
    buzzer.value(1)
    time.sleep(seconds)
    buzzer.value(0)


print("CHECKPOINT 6 - after buzzer setup")

# ─── STUDENT DATABASE (UID string -> info) ────────────────
STUDENT_DB = {
    "1425411918150": {"name": "Khorn Sokhadom", "student_id": "2023517", "major": "Computer Science"},
}

print("CHECKPOINT 7 - entering main loop")

# ─── MAIN LOOP ─────────────────────────────────────────────
print("Scan RFID...")

while True:
    (stat, tag_type) = rdr.request(rdr.REQIDL)

    if stat == rdr.OK:
        (stat, uid) = rdr.anticoll()
        if stat == rdr.OK:
            uid_str = "".join([str(i) for i in uid])
            dt_string = get_datetime_string()
            print("\nUID:", uid_str)

            info = STUDENT_DB.get(uid_str)

            if info:
                print("Valid student:", info["name"])
                buzz(VALID_BUZZ_SEC)
                if sd_ok:
                    try:
                        with open(CSV_PATH, "a") as f:
                            f.write("{},{},{},{},{}\n".format(
                                uid_str, info["name"], info["student_id"],
                                info["major"], dt_string
                            ))
                        print("Saved to SD:", CSV_PATH)
                    except OSError as e:
                        print("SD write failed:", e)
                else:
                    print("SD not mounted — skipping local save.")
                send_to_firestore(uid_str, info, dt_string)
            else:
                print("Unknown Card")
                buzz(INVALID_BUZZ_SEC)

            time.sleep(2)

