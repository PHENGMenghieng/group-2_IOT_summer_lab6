from machine import Pin, SPI
from mfrc522 import MFRC522
import network
import urequests
import ujson
import time


SSID = "SSID"
PASSWORD = "password"

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, PASSWORD)

print("Connecting WiFi", end="")
while not wifi.isconnected():
    print(".", end="")
    time.sleep(0.5)

print("\nConnected:", wifi.ifconfig())

PROJECT_ID = "firestore-ID"

url = "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents/rfid_logs".format(PROJECT_ID)


spi = SPI(1, baudrate=1000000,
          sck=Pin(18), mosi=Pin(23), miso=Pin(19))

rdr = MFRC522(spi=spi, gpioRst=Pin(22), gpioCs=Pin(16))

print("Scan RFID...")

def send_to_firestore(uid):
    data = {
        "fields": {
            "uid": {"stringValue": uid},
            "time": {"stringValue": str(time.time())}
        }
    }

    try:
        res = urequests.post(url, json=data)
        print("Sent:", res.text)
        res.close()
    except Exception as e:
        print("Error sending:", e)


while True:
    (stat, tag_type) = rdr.request(rdr.REQIDL)

    if stat == rdr.OK:
        (stat, uid) = rdr.anticoll()

        if stat == rdr.OK:
            uid_str = "".join([str(i) for i in uid])
            print("UID:", uid_str)

            send_to_firestore(uid_str)

            time.sleep(2)
