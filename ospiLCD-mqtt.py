#!/usr/bin/env python

"""
ospiLCD-mqtt.py
OpenSprinkler status display, MQTT enabled
https://github.com/RonRN18/ospiLCD-mqtt
Based on sirkus7's build at https://github.com/sirkus7/ospiLCD-mqtt

"""
import json
import locale
import requests
import socket
import signal
import random
import paho.mqtt
import threading
import time
from os import system
from threading import Timer
from time import sleep
from time import *
from random import randint
from RPLCD import i2c
from subprocess import check_output
import paho.mqtt.client as mqtt


# Global Variables

######################### User Variables #########################
osAddress = "127.0.0.1"  # OpenSprinkler address (default 127.0.0.1)
osPort = 8080  # OpenSprinkler port (default 8080)
md5hash = "a6d82bced638de3def1e9bbb4983225c"  # OpenSprinkler password MD5 hash (default opendoor)
LCD_i2c_expander = "PCF8574"  # PCF8574 (default, ebay), MCP23008 (used in Adafruit I2C LCD backpack) or MCP23017
LCD_i2c_address = 0x27  # LCD I2C address (default 0x27)
LCD_cols = 20  # LCD columns (16 or 20)
LCD_rows = 4  # LCD rows (2 or 4)
date_locale = (
    "en_US.UTF-8"  # Set to your Raspberry pi locale eg. 'en_GB.UTF-8' or 'it_IT.UTF-8'
)


client_id = f"python-mqtt-{random.randint(0, 1000)}"  # MQTT requires a unique client ID for every client connection
backlight_timeout = 60.0  # Float, seconds to keep display lit after showing data before dimming. 0.0" Disables, keeps backlight on at all times.
api_url = f"http://{osAddress}:{osPort}/ja?pw={md5hash}"  # This URL provides OpenSprinkler's latest settings/status in JSON format

################################################
# Function defs


def signal_handler(sig, frame):
    global lcd
    global dim_timer
    dim_timer.cancel()
    lcd.backlight_enabled = False
    lcd.clear()
    print("Exiting.")
    sys.exit(0)


def mqtt_connect(client, userdata, flags, rc):
    print(
        "[Connected with result code {0}]".format(str(rc))
    )  # For debugging MQTT connect message
    client.subscribe(
        "opensprinkler/#"
    )  # Subscribe to the topic, receive any messages published on it
    lcd.backlight_enabled = True
    lcd.cursor_pos = (0, 0)
    lcd.write_string("MQTT Connected\r\nReqesting info")


def cycle_mqtt_message(client, userdata, msg):
    def run_cycle():
        while True:
            mqtt_message(client, userdata, msg)
            sleep(30)  # Sleep for 30 seconds between cycles

    # Start the cycling in a separate thread to avoid blocking the main thread
    cycle_thread = threading.Thread(target=run_cycle)
    cycle_thread.daemon = (
        True  # This ensures the thread will exit when the main program exits
    )
    cycle_thread.start()


def mqtt_message(client, userdata, msg):
    print("Msg:" + msg.topic + ": " + str(msg.payload))  # Debug MQTT messages recieved.
    update_display()


def get_data():

    os = requests.get(api_url).json()
    settings = os.get("settings", {})
    options = os.get("options", {})
    mqtt = settings.get("mqtt", {})
    status = os.get("status", {})

    device_time = settings.get("devt")
    device_enabled = settings.get("en")
    sensor1 = settings.get("sn1")
    sensor2 = settings.get("sn2")
    rain_delay = settings.get("rd")
    sunrise = settings.get("sunrise")
    sunset = settings.get("sunset")
    mqtt_en = mqtt.get("en")
    mqtt_host = mqtt.get("host")
    mqtt_port = mqtt.get("port")
    mqtt_user = mqtt.get("user")
    mqtt_password = mqtt.get("pass")
    device_name = settings.get("dname")
    den = settings.get("den")
    mas = settings.get("mas")
    mas2 = settings.get("mas2")
    remote_extension = options.get("re")
    sensor1_type = options.get("sn1t")
    water_level = options.get("wl")
    status_sn = status.get("sn")
    nstations = status.get("nstations")
    stations = os.get("stations", {})
    snames = stations.get("snames")
    program_status = settings.get("ps")

    return {
        "device_time": device_time,
        "device_enabled": device_enabled,
        "sensor1": sensor1,
        "sensor2": sensor2,
        "rain_delay": rain_delay,
        "sunrise": sunrise,
        "sunset": sunset,
        "mqtt_en": mqtt_en,
        "mqtt_host": mqtt_host,
        "mqtt_port": mqtt_port,
        "mqtt_user": mqtt_user,
        "mqtt_password": mqtt_password,
        "device_name": device_name,
        "den": den,
        "mas": mas,
        "mas2": mas2,
        "remote_extension": remote_extension,
        "sensor1_type": sensor1_type,
        "water_level": water_level,
        "status_sn": status_sn,
        "nstations": nstations,
        "stations": stations,
        "snames": snames,
        "program_status": program_status,
    }


def dim_backlight():  # Callback for dim_timer
    global lcd
    lcd.backlight_enabled = False
    print("[Backlight dimmed.]")


def update_display():
    global lcd
    global dim_timer

    # Parse JSON into an object with attributes corresponding to dict keys.
    ja = get_data()
    ja_mas = ja["mas"]
    ja_mas2 = ja["mas2"]
    ja_sn = ja["status_sn"]
    ja_nstations = ja["nstations"]
    ja_den = ja["den"]
    ja_re = ja["remote_extension"]
    ja_sn1t = ja["sensor1_type"]
    ja_rd = ja["rain_delay"]
    ja_ps = ja["program_status"]
    ja_devt = ja["device_time"]
    ja_wl = ja["water_level"]

    # get all station status
    mc = ""
    i = 1
    for x in range(0, 8):
        if ja_sn[x] == 0:
            mc = mc + "_"
        else:
            if i == ja_mas:  # MATER 1
                mc = mc + "M"
            elif i == ja_mas2:  # MASTER 2
                mc = mc + "N"
            else:
                mc = mc + str(i)
        i += 1

    mc2 = ""
    a = 9
    if ja_nstations > 8:
        for b in range(8, 16):
            if ja_sn[b] == 0:
                mc2 = mc2 + "_"
            else:
                if a == ja_mas:  # MATER 1
                    mc2 = mc2 + "M"
                elif a == ja_mas2:  # MASTER 2
                    mc2 = mc2 + "N"
                else:
                    mc2 = mc2 + str(a)
            a += 1

    # get system status
    if ja_den == 0:
        mc = "Disabled!"
    else:
        mc = mc + " "

    # get remote extension mode status
    if ja_re == 1:
        mc = mc + "\x05"
    else:
        mc = mc + " "

    # get sensor (0=none, 1=rain, 2=flow, 3=soil, 240=program switch)
    if ja_sn1t == 1:
        if ja_rd == 1:
            mc = mc + "\x03"
        else:
            mc = mc + " "
    elif ja_sn1t == 2:
        mc = mc + "\x06"
    elif ja_sn1t == 240:
        mc = mc + "\x07"
    else:
        mc = mc + ""  # Note, currently no icon for 3=soil. (todo)

    # check local network status
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    net_ip = s.getsockname()[0]
    if len(net_ip) > 7:
        mc = mc + "\x00"  # Shows WiFi logo
    else:
        mc = mc + "\x01"  # Shows WiFi logo with "x" to refer to no network

    # Count remaining watering time
    totaltime = 0
    for station in ja_ps:
        totaltime = totaltime + station[1]
    r_m, r_s = divmod(totaltime, 60)
    r_h, r_m = divmod(r_m, 60)

    # Define LCD lines 1 & 2
    locale.setlocale(locale.LC_ALL, date_locale)
    line1 = strftime("%H:%M %a %m-%d", gmtime(ja_devt))  # device time
    line2 = "MC:" + mc  # station status

    # 3rd LCD line
    if ja_nstations > 8:
        line3 = "E1:" + mc2 + " " + str(ja_wl) + "%"
    else:
        line3 = "Water level:" + str(ja_wl) + "%"

    # 4th LCD line
    if totaltime > 0:
        line4 = "Rt:%d:%02d:%02d h:m:s" % (r_h, r_m, r_s)  # Remaining watering time
    else:
        if len(net_ip) > 7:
            line4 = "" + net_ip  # internal IP
        else:
            line4 = "No Network!"

    print(line1)
    print(line2)
    if LCD_rows == 4:
        print(line3)
        print(line4)

    # Enable backlight to display new message.
    lcd.backlight_enabled = True

    # Write new information
    lcd.clear()
    lcd.write_string(line1)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(line2)
    if LCD_rows == 4:
        lcd.cursor_pos = (2, 0)
        lcd.write_string(line3)
        lcd.cursor_pos = (3, 0)
        lcd.write_string(line4)


##################################################################################3
# Globals
backlight = True
dim_timer = ""
dim_timer = Timer(backlight_timeout, dim_backlight)

signal.signal(signal.SIGINT, signal_handler)

# === Setup the Display ===
lcd = i2c.CharLCD(
    i2c_expander=LCD_i2c_expander,
    address=LCD_i2c_address,
    port=1,
    cols=LCD_cols,
    rows=LCD_rows,
    dotsize=8,
    charmap="A02",
    auto_linebreaks=True,
    backlight_enabled=True,
)

# Define Custom LCD characters
i_wific = (
    0b00000,
    0b00000,
    0b00000,
    0b00001,
    0b00001,
    0b00101,
    0b00101,
    0b10101,
)  # Wifi connected icon
i_wifid = (
    0b00000,
    0b10100,
    0b01000,
    0b10101,
    0b00001,
    0b00101,
    0b00101,
    0b10101,
)  # WiFi disconnected icon
i_usd = (
    0b00000,
    0b00000,
    0b11111,
    0b10001,
    0b11111,
    0b10001,
    0b10011,
    0b11110,
)  # uSD card icon
i_rain = (
    0b00000,
    0b00000,
    0b00110,
    0b01001,
    0b11111,
    0b00000,
    0b10101,
    0b10101,
)  # Rain icon
i_conn = (
    0b00000,
    0b00000,
    0b00111,
    0b00011,
    0b00101,
    0b01000,
    0b10000,
    0b00000,
)  # Connect icon
i_rext = (
    0b00000,
    0b00000,
    0b00000,
    0b10001,
    0b01011,
    0b00101,
    0b01001,
    0b11110,
)  # Remote extension icon
i_flow = (
    0b00000,
    0b00000,
    0b00000,
    0b11010,
    0b10010,
    0b11010,
    0b10011,
    0b00000,
)  # Flow sensor icon
i_psw = (
    0b00000,
    0b11100,
    0b10100,
    0b11100,
    0b10010,
    0b10110,
    0b00010,
    0b00111,
)  # Program switch icon

lcd.create_char(0, i_wific)
lcd.create_char(1, i_wifid)
lcd.create_char(2, i_usd)
lcd.create_char(3, i_rain)
lcd.create_char(4, i_conn)
lcd.create_char(5, i_rext)
lcd.create_char(6, i_flow)
lcd.create_char(7, i_psw)

lcd.clear()
lcd.write_string("Connecting to\r\nMQTT broker...")

# === Setup MQTT client, actions ===
ja = get_data()  # Obtains the latest OpenSprinkler settings (in JSON format)
user = ja["mqtt_user"]  # Acquires the MQTT username from OpenSprinkler setup
password = ja["mqtt_password"]  # Acquires the MQTT password from OpenSprinkler setup
mqttAddress = ja[
    "mqtt_host"
]  # Acquires the MQTT Broker's host from OpenSprinkler setup
mqttPort = ja[
    "mqtt_port"
]  # Acquires MQTT Broker's port number from OpenSprinkler setup


if paho.mqtt.__version__[0] > "1":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
else:
    client = mqtt.Client()
client.on_connect = mqtt_connect
client.on_message = cycle_mqtt_message
client.username_pw_set(user, password)
client.connect(mqttAddress, mqttPort, keepalive=60)
client.loop_forever()
