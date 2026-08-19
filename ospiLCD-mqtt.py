#!/usr/bin/env python

"""
ospiLCD-mqtt.py
OpenSprinkler status display, MQTT enabled
https://github.com/RonRN18/ospiLCD-mqtt
Based on sirkus7's build at https://github.com/sirkus7/ospiLCD-mqtt
"""

import configparser
import locale
import random
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from threading import Timer
from time import localtime, strftime

import paho.mqtt.client as mqtt
import requests
from RPLCD import i2c


######################### Configuration #########################

config_file = Path(__file__).with_name("ospilcd.ini")

if not config_file.exists():
    raise FileNotFoundError(
        f"Configuration file not found: {config_file}\n"
        "Copy ospilcd.ini.example to ospilcd.ini and edit it for your system."
    )

config = configparser.ConfigParser()
config.read(config_file)

osAddress = config.get(
    "OpenSprinkler",
    "address",
    fallback="127.0.0.1",
)

osPort = config.getint(
    "OpenSprinkler",
    "port",
    fallback=8080,
)

md5hash = config.get(
    "OpenSprinkler",
    "password_hash",
)

LCD_i2c_expander = config.get(
    "LCD",
    "i2c_expander",
    fallback="PCF8574",
)

LCD_i2c_address = int(
    config.get(
        "LCD",
        "i2c_address",
        fallback="0x27",
    ),
    0,
)

LCD_cols = config.getint(
    "LCD",
    "columns",
    fallback=20,
)

LCD_rows = config.getint(
    "LCD",
    "rows",
    fallback=4,
)

backlight_timeout = config.getfloat(
    "LCD",
    "backlight_timeout",
    fallback=60.0,
)

date_locale = config.get(
    "Regional",
    "locale",
    fallback="en_US.UTF-8",
)

client_id = f"python-mqtt-{random.randint(0, 1000)}"

api_url = f"http://{osAddress}:{osPort}/ja?pw={md5hash}"


######################### Globals #########################

lcd = None

lcd_lock = threading.Lock()
update_lock = threading.Lock()
timer_lock = threading.Lock()
stop_event = threading.Event()

dim_timer = None


######################### Utility Functions #########################


def format_lcd_line(text):
    """
    Pad or truncate text so that exactly one LCD row is written.

    Writing a complete row avoids needing to clear the entire display
    during routine updates and reduces LCD flicker.
    """
    return str(text)[:LCD_cols].ljust(LCD_cols)


def format_clock_line():
    """
    Return the Pi's local time formatted for the first LCD row.

    Example on a 20-column LCD:
        10:04:27 Wed 08-19
    """
    return strftime("%H:%M:%S %a %m-%d", localtime())


def reset_backlight_timer():
    """
    Restart the timer that turns off the LCD backlight.

    A timeout of 0 or less means leave the backlight on indefinitely.
    """
    global dim_timer

    with timer_lock:
        if dim_timer is not None:
            dim_timer.cancel()

        dim_timer = None

        if backlight_timeout > 0:
            dim_timer = Timer(
                backlight_timeout,
                dim_backlight,
            )
            dim_timer.daemon = True
            dim_timer.start()


def wake_backlight():
    """
    Turn on the LCD backlight and restart its timeout timer.
    """
    with lcd_lock:
        lcd.backlight_enabled = True

    reset_backlight_timer()


def dim_backlight():
    """
    Callback used by the backlight timeout timer.
    """
    with lcd_lock:
        lcd.backlight_enabled = False

    print("[Backlight dimmed.]")


######################### Signal Handling #########################


def signal_handler(sig, frame):
    """
    Cleanly shut down when Ctrl+C or SIGINT is received.
    """
    global dim_timer

    stop_event.set()

    with timer_lock:
        if dim_timer is not None:
            dim_timer.cancel()

    with lcd_lock:
        if lcd is not None:
            lcd.clear()
            lcd.backlight_enabled = False

    print("Exiting.")
    sys.exit(0)


######################### OpenSprinkler API #########################

class OpenSprinklerAuthenticationError(Exception):
    pass


class OpenSprinklerConnectionError(Exception):
    pass

def get_data():
    """
    Retrieve the current OpenSprinkler state from the JSON API.
    """
    try:
        response = requests.get(
            api_url,
            timeout=5,
        )

        response.raise_for_status()

    except requests.RequestException as e:
        raise OpenSprinklerConnectionError(
            f"Unable to connect to OpenSprinkler: {e}"
        ) from e

    try:
        os_data = response.json()

    except requests.JSONDecodeError as e:
        raise OpenSprinklerConnectionError(
            "OpenSprinkler returned an invalid JSON response."
        ) from e

    if "settings" not in os_data:
        raise OpenSprinklerAuthenticationError(
            "OpenSprinkler API authentication failed. "
            "Check the password hash in ospilcd.ini."
        )

    settings = os_data.get("settings", {})
    options = os_data.get("options", {})
    mqtt_settings = settings.get("mqtt", {})
    status = os_data.get("status", {})

    device_time = settings.get("devt")
    device_enabled = settings.get("en")
    sensor1 = settings.get("sn1")
    sensor2 = settings.get("sn2")
    rain_delay = settings.get("rd")
    sunrise = settings.get("sunrise")
    sunset = settings.get("sunset")

    mqtt_en = mqtt_settings.get("en")
    mqtt_host = mqtt_settings.get("host")
    mqtt_port = mqtt_settings.get("port")
    mqtt_user = mqtt_settings.get("user")
    mqtt_password = mqtt_settings.get("pass")

    device_name = settings.get("dname")

    den = options.get("den")
    mas = options.get("mas")
    mas2 = options.get("mas2")

    remote_extension = options.get("re")
    sensor1_type = options.get("sn1t")
    water_level = options.get("wl")

    status_sn = status.get("sn")
    nstations = status.get("nstations")

    stations = os_data.get("stations", {})
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


######################### LCD Display #########################


def update_clock():
    """
    Update only the first LCD row once per second.

    This does not query OpenSprinkler and does not perform any MQTT
    operations. It simply uses the Raspberry Pi's local system clock.
    """
    while not stop_event.is_set():
        try:
            line1 = format_clock_line()

            with lcd_lock:
                lcd.cursor_pos = (0, 0)
                lcd.write_string(format_lcd_line(line1))

        except Exception as e:
            print(f"Clock update failed: {e}")

        # Sleep until approximately the beginning of the next second.
        delay = 1.0 - (time.time() % 1.0)

        if stop_event.wait(delay):
            break

def show_error(line1, line2="", line3="", line4="", wake=True):
    """
    Display an error message on the LCD.
    """
    if wake:
        wake_backlight()

    with lcd_lock:
        lcd.cursor_pos = (0, 0)
        lcd.write_string(format_lcd_line(line1))

        if LCD_rows >= 2:
            lcd.cursor_pos = (1, 0)
            lcd.write_string(format_lcd_line(line2))

        if LCD_rows >= 3:
            lcd.cursor_pos = (2, 0)
            lcd.write_string(format_lcd_line(line3))

        if LCD_rows >= 4:
            lcd.cursor_pos = (3, 0)
            lcd.write_string(format_lcd_line(line4))

def periodic_refresh():
    while not stop_event.wait(30):
        try:
            update_display(wake=False)

        except OpenSprinklerAuthenticationError as e:
            print(e)

            show_error(
                "OpenSprinkler",
                "Login failed",
                "Check password",
                "in ospilcd.ini",
                wake=True,
            )

        except OpenSprinklerConnectionError as e:
            print(e)

            show_error(
                "OpenSprinkler",
                "Connection failed",
                "Check address",
                "and network",
                wake=True,
            )

        except Exception as e:
            print(f"Periodic display refresh failed: {e}")


def update_display(wake=True):
    """
    Query OpenSprinkler and update the status portions of the LCD.

    If wake=True, the LCD backlight is turned on and its timeout timer
    is restarted. MQTT-triggered updates use wake=True.

    The periodic 30-second refresh uses wake=False so it does not
    continually turn the backlight back on.
    """

    # Prevent multiple full API/display updates from running at once.
    with update_lock:
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
        ja_wl = ja["water_level"]

        ######################### Main Controller Status #########################

        mc = ""
        station_number = 1

        for x in range(0, 8):
            if ja_sn[x] == 0:
                mc += "_"

            else:
                if station_number == ja_mas:
                    mc += "M"

                elif station_number == ja_mas2:
                    mc += "N"

                else:
                    mc += str(station_number)

            station_number += 1

        ######################### Expansion Board Status #########################

        mc2 = ""
        station_number = 9

        if ja_nstations > 8:
            for x in range(8, 16):
                if ja_sn[x] == 0:
                    mc2 += "_"

                else:
                    if station_number == ja_mas:
                        mc2 += "M"

                    elif station_number == ja_mas2:
                        mc2 += "N"

                    else:
                        mc2 += str(station_number)

                station_number += 1

        ######################### Controller Enabled/Disabled #########################

        if ja_den == 0:
            mc = "Disabled!"

        else:
            mc += " "

        ######################### Remote Extension Status #########################

        if ja_re == 1:
            mc += "\x05"

        else:
            mc += " "

        ######################### Sensor Status #########################

        # Sensor types:
        #   0   = none
        #   1   = rain
        #   2   = flow
        #   3   = soil
        #   240 = program switch

        if ja_sn1t == 1:
            if ja_rd == 1:
                mc += "\x03"

            else:
                mc += " "

        elif ja_sn1t == 2:
            mc += "\x06"

        elif ja_sn1t == 240:
            mc += "\x07"

        # Currently no custom icon for soil sensor type 3.

        ######################### Local Network Status #########################

        net_ip = None
        network_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        try:
            network_socket.connect(("8.8.8.8", 80))
            net_ip = network_socket.getsockname()[0]

        except OSError:
            net_ip = None

        finally:
            network_socket.close()

        if net_ip:
            mc += "\x00"

        else:
            mc += "\x01"

        ######################### Remaining Watering Time #########################

        total_time = 0

        if ja_ps:
            for station in ja_ps:
                total_time += station[1]

        remaining_minutes, remaining_seconds = divmod(
            total_time,
            60,
        )

        remaining_hours, remaining_minutes = divmod(
            remaining_minutes,
            60,
        )

        ######################### Build LCD Rows #########################

        line1 = format_clock_line()
        line2 = "MC:" + mc

        if ja_nstations > 8:
            line3 = "E1:" + mc2 + " " + str(ja_wl) + "%"

        else:
            line3 = "Water level:" + str(ja_wl) + "%"

        if total_time > 0:
            line4 = "Rt:%d:%02d:%02d h:m:s" % (
                remaining_hours,
                remaining_minutes,
                remaining_seconds,
            )

        else:
            if net_ip:
                line4 = net_ip

            else:
                line4 = "No Network!"

        ######################### Terminal Debug Output #########################

        print(line1)
        print(line2)

        if LCD_rows == 4:
            print(line3)
            print(line4)

        ######################### Write LCD #########################

        if wake:
            wake_backlight()

        with lcd_lock:
            # Do NOT clear the entire LCD here.
            #
            # Writing an entire padded row removes old characters while
            # avoiding the visible flicker caused by lcd.clear().

            lcd.cursor_pos = (0, 0)
            lcd.write_string(format_lcd_line(line1))

            lcd.cursor_pos = (1, 0)
            lcd.write_string(format_lcd_line(line2))

            if LCD_rows == 4:
                lcd.cursor_pos = (2, 0)
                lcd.write_string(format_lcd_line(line3))

                lcd.cursor_pos = (3, 0)
                lcd.write_string(format_lcd_line(line4))


######################### MQTT Callbacks #########################


def mqtt_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties,
):
    """
    Called when the Paho MQTT client connects to the broker.
    """
    print(
        f"[Connected with result code {reason_code}]"
    )

    if reason_code.is_failure:
        print(
            f"MQTT connection failed: {reason_code}"
        )
        return

    client.subscribe("opensprinkler/#")

    wake_backlight()

    with lcd_lock:
        lcd.cursor_pos = (0, 0)
        lcd.write_string(
            format_lcd_line("MQTT Connected")
        )

        lcd.cursor_pos = (1, 0)
        lcd.write_string(
            format_lcd_line("Requesting info")
        )


def mqtt_message(
    client,
    userdata,
    msg,
):
    """
    Immediately refresh the OpenSprinkler status whenever an MQTT
    message is received.
    """
    print(
        "Msg:"
        + msg.topic
        + ": "
        + str(msg.payload)
    )

    update_display(wake=True)


######################### Program Startup #########################


# Set the locale once rather than doing so during every display refresh.
locale.setlocale(
    locale.LC_TIME,
    date_locale,
)

signal.signal(
    signal.SIGINT,
    signal_handler,
)


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


######################### Custom LCD Characters #########################

i_wific = (
    0b00000,
    0b00000,
    0b00000,
    0b00001,
    0b00001,
    0b00101,
    0b00101,
    0b10101,
)

i_wifid = (
    0b00000,
    0b10100,
    0b01000,
    0b10101,
    0b00001,
    0b00101,
    0b00101,
    0b10101,
)

i_usd = (
    0b00000,
    0b00000,
    0b11111,
    0b10001,
    0b11111,
    0b10001,
    0b10011,
    0b11110,
)

i_rain = (
    0b00000,
    0b00000,
    0b00110,
    0b01001,
    0b11111,
    0b00000,
    0b10101,
    0b10101,
)

i_conn = (
    0b00000,
    0b00000,
    0b00111,
    0b00011,
    0b00101,
    0b01000,
    0b10000,
    0b00000,
)

i_rext = (
    0b00000,
    0b00000,
    0b00000,
    0b10001,
    0b01011,
    0b00101,
    0b01001,
    0b11110,
)

i_flow = (
    0b00000,
    0b00000,
    0b00000,
    0b11010,
    0b10010,
    0b11010,
    0b10011,
    0b00000,
)

i_psw = (
    0b00000,
    0b11100,
    0b10100,
    0b11100,
    0b10010,
    0b10110,
    0b00010,
    0b00111,
)


with lcd_lock:
    lcd.create_char(0, i_wific)
    lcd.create_char(1, i_wifid)
    lcd.create_char(2, i_usd)
    lcd.create_char(3, i_rain)
    lcd.create_char(4, i_conn)
    lcd.create_char(5, i_rext)
    lcd.create_char(6, i_flow)
    lcd.create_char(7, i_psw)

    lcd.clear()

    lcd.cursor_pos = (0, 0)
    lcd.write_string(
        format_lcd_line("Connecting to")
    )

    lcd.cursor_pos = (1, 0)
    lcd.write_string(
        format_lcd_line("MQTT broker...")
    )


######################### MQTT Setup #########################

try:
    ja = get_data()

except OpenSprinklerAuthenticationError as e:
    print(e)

    show_error(
        "OpenSprinkler",
        "Login failed",
        "Check password",
        "in ospilcd.ini",
        wake=True,
    )

    sys.exit(1)

except OpenSprinklerConnectionError as e:
    print(e)

    show_error(
        "OpenSprinkler",
        "Connection failed",
        "Check address",
        "and network",
        wake=True,
    )

    sys.exit(1)

user = ja["mqtt_user"]
password = ja["mqtt_password"]
mqttAddress = ja["mqtt_host"]
mqttPort = ja["mqtt_port"]


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=client_id,
)

client.on_connect = mqtt_connect
client.on_message = mqtt_message

client.username_pw_set(
    user,
    password,
)

client.connect(
    mqttAddress,
    mqttPort,
    keepalive=60,
)


######################### Background Threads #########################

# One thread performs a complete API refresh every 30 seconds.
refresh_thread = threading.Thread(
    target=periodic_refresh,
    daemon=True,
    name="periodic-refresh",
)

refresh_thread.start()


# One lightweight thread updates only the clock once per second.
clock_thread = threading.Thread(
    target=update_clock,
    daemon=True,
    name="lcd-clock",
)

clock_thread.start()


######################### MQTT Service Loop #########################

client.loop_forever()