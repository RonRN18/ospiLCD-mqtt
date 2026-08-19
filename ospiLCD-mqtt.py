#!/usr/bin/env python

"""
ospiLCD-mqtt.py
OpenSprinkler status display, MQTT enabled
https://github.com/RonRN18/ospiLCD-mqtt

Based on sirkus7's build:
https://github.com/sirkus7/ospiLCD-mqtt

Originally based on Stanley's ospiLCD:
https://github.com/stanoba/ospiLCD
"""

import configparser
import locale
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

# MD5 hash of OpenSprinkler's default password, "opendoor".
md5hash = config.get(
    "OpenSprinkler",
    "password_hash",
    fallback="a6d82bced638de3def1e9bbb4983225c",
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

client_id = f"ospiLCD-mqtt-{socket.gethostname()}"

api_url = f"http://{osAddress}:{osPort}/ja?pw={md5hash}"


######################### Globals #########################

lcd = None
dim_timer = None

lcd_lock = threading.Lock()
update_lock = threading.Lock()
timer_lock = threading.Lock()

stop_event = threading.Event()
error_active = threading.Event()


######################### Custom Exceptions #########################


class OpenSprinklerAuthenticationError(Exception):
    """Raised when OpenSprinkler rejects the configured password hash."""


class OpenSprinklerConnectionError(Exception):
    """Raised when the OpenSprinkler API cannot be reached or read."""


######################### Utility Functions #########################


def format_lcd_line(text):
    """
    Pad or truncate text so exactly one LCD row is written.

    This prevents stale characters without clearing the entire display.
    """
    return str(text)[:LCD_cols].ljust(LCD_cols)


def format_clock_line():
    """
    Return the Raspberry Pi's local time for LCD row 1.

    Example:
        14:32:17 Wed 08-19
    """
    return strftime("%H:%M:%S %a %m-%d", localtime())


def reset_backlight_timer():
    """
    Restart the timer that turns off the LCD backlight.

    A timeout of zero or less leaves the backlight on indefinitely.
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
    Turn off the LCD backlight when its timeout expires.
    """
    with lcd_lock:
        lcd.backlight_enabled = False

    print("[Backlight dimmed.]")


def signal_handler(_sig, _frame):
    """
    Cleanly shut down on Ctrl+C or systemd service stop.
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


def get_data(timeout=5):
    """
    Retrieve the current OpenSprinkler state from the JSON API.
    """
    try:
        response = requests.get(
            api_url,
            timeout=timeout,
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

    # OpenSprinkler currently responds to an incorrect password with
    # HTTP 200 and a small JSON object such as {"fwv":221}.  A valid
    # /ja response contains the "settings" object.
    if "settings" not in os_data:
        raise OpenSprinklerAuthenticationError(
            "OpenSprinkler API authentication failed. "
            "Check the password hash in ospilcd.ini."
        )

    settings = os_data.get("settings", {})
    options = os_data.get("options", {})
    status = os_data.get("status", {})
    mqtt_settings = settings.get("mqtt", {})

    return {
        "mqtt_enabled": mqtt_settings.get("en"),
        "mqtt_host": mqtt_settings.get("host"),
        "mqtt_port": mqtt_settings.get("port"),
        "mqtt_user": mqtt_settings.get("user"),
        "mqtt_password": mqtt_settings.get("pass"),
        "den": options.get("den"),
        "mas": options.get("mas"),
        "mas2": options.get("mas2"),
        "remote_extension": options.get("re"),
        "sensor1_type": options.get("sn1t"),
        "water_level": options.get("wl"),
        "rain_delay": settings.get("rd"),
        "status_sn": status.get("sn"),
        "nstations": status.get("nstations"),
        "program_status": settings.get("ps"),
    }


######################### LCD Error Display #########################


def show_error(line1, line2="", line3="", line4="", wake=True):
    """
    Display an error message and suspend the live clock.
    """
    error_active.set()

    if wake:
        wake_backlight()

    lines = (
        line1,
        line2,
        line3,
        line4,
    )

    with lcd_lock:
        for row, text in enumerate(lines[:LCD_rows]):
            lcd.cursor_pos = (row, 0)
            lcd.write_string(format_lcd_line(text))


def show_opensprinkler_error(error):
    """
    Display the appropriate OpenSprinkler API error.
    """
    print(error)

    if isinstance(error, OpenSprinklerAuthenticationError):
        show_error(
            "OpenSprinkler",
            "Login failed",
            "Check password",
            "in ospilcd.ini",
            wake=True,
        )

    else:
        show_error(
            "OpenSprinkler",
            "Connection failed",
            "Check address",
            "and network",
            wake=True,
        )


######################### LCD Status Helpers #########################


def build_station_group(
    station_status,
    start_index,
    end_index,
    first_station_number,
    master1,
    master2,
):
    """
    Build a compact station status string.

    Inactive station: "_"
    Master 1:         "M"
    Master 2:         "N"
    Other active:     station number
    """
    result = ""
    station_number = first_station_number

    for index in range(start_index, end_index):
        if station_status[index] == 0:
            result += "_"

        elif station_number == master1:
            result += "M"

        elif station_number == master2:
            result += "N"

        else:
            result += str(station_number)

        station_number += 1

    return result


def build_remote_extension_icon(remote_extension):
    """
    Return the LCD icon for remote extension mode.
    """
    if remote_extension == 1:
        return "\x05"

    return " "


def build_sensor_icon(sensor_type, rain_delay):
    """
    Return the LCD icon representing the configured sensor.

    Sensor types:
        0   = none
        1   = rain
        2   = flow
        3   = soil
        240 = program switch

    There is currently no custom icon for soil sensors.
    """
    if sensor_type == 1:
        if rain_delay == 1:
            return "\x03"

        return " "

    sensor_icons = {
        2: "\x06",  # Flow sensor
        240: "\x07",  # Program switch
    }

    return sensor_icons.get(sensor_type, " ")


def build_network_icon(network_connected):
    """
    Return the network-connected or disconnected custom LCD icon.
    """
    if network_connected:
        return "\x00"

    return "\x01"


def build_main_controller_status(ja, network_connected):
    """
    Build the status string shown after 'MC:' on LCD row 2.
    """
    status = build_station_group(
        station_status=ja["status_sn"],
        start_index=0,
        end_index=8,
        first_station_number=1,
        master1=ja["mas"],
        master2=ja["mas2"],
    )

    if ja["den"] == 0:
        status = "Disabled!"

    else:
        status += " "

    status += build_remote_extension_icon(ja["remote_extension"])

    status += build_sensor_icon(
        ja["sensor1_type"],
        ja["rain_delay"],
    )

    status += build_network_icon(network_connected)

    return status


def build_expansion_status(ja):
    """
    Build the station-status string for the first expansion board.

    Return an empty string when there are eight or fewer stations.
    """
    if ja["nstations"] <= 8:
        return ""

    return build_station_group(
        station_status=ja["status_sn"],
        start_index=8,
        end_index=16,
        first_station_number=9,
        master1=ja["mas"],
        master2=ja["mas2"],
    )


def get_network_ip():
    """
    Determine the Pi's IPv4 address used for outbound traffic.

    A UDP connect is sufficient for Linux to select the local
    interface and source address; no packet is actually sent.
    """
    network_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        network_socket.connect(("8.8.8.8", 80))
        return network_socket.getsockname()[0]

    except OSError:
        return None

    finally:
        network_socket.close()


def calculate_remaining_time(program_status):
    """
    Calculate total remaining watering time in seconds.
    """
    if not program_status:
        return 0

    return sum(station[1] for station in program_status)


def format_remaining_time(total_time):
    """
    Convert seconds into hours, minutes, and seconds.
    """
    remaining_minutes, remaining_seconds = divmod(
        total_time,
        60,
    )

    remaining_hours, remaining_minutes = divmod(
        remaining_minutes,
        60,
    )

    return (
        remaining_hours,
        remaining_minutes,
        remaining_seconds,
    )


def build_display_lines(
    ja,
    main_status,
    expansion_status,
    net_ip,
    total_time,
):
    """
    Build the logical LCD rows.
    """
    line1 = format_clock_line()
    line2 = "MC:" + main_status

    if ja["nstations"] > 8:
        line3 = "E1:" + expansion_status + " " + str(ja["water_level"]) + "%"

    else:
        line3 = "Water level:" + str(ja["water_level"]) + "%"

    if total_time > 0:
        hours, minutes, seconds = format_remaining_time(total_time)

        line4 = "Rt:%d:%02d:%02d h:m:s" % (
            hours,
            minutes,
            seconds,
        )

    elif net_ip:
        line4 = net_ip

    else:
        line4 = "No Network!"

    return (
        line1,
        line2,
        line3,
        line4,
    )


def print_display_lines(lines):
    """
    Print displayed information to the terminal for debugging.
    """
    for line in lines[:LCD_rows]:
        print(line)


def write_display(lines, wake=True):
    """
    Write complete padded rows without clearing the LCD.

    This avoids stale characters and minimizes visible flicker.
    """
    if wake:
        wake_backlight()

    with lcd_lock:
        for row, text in enumerate(lines[:LCD_rows]):
            lcd.cursor_pos = (row, 0)
            lcd.write_string(format_lcd_line(text))


######################### Display Update #########################


def update_display(wake=True):
    """
    Query OpenSprinkler and refresh the LCD status display.
    """
    with update_lock:
        ja = get_data()

        net_ip = get_network_ip()

        main_status = build_main_controller_status(
            ja,
            network_connected=(net_ip is not None),
        )

        expansion_status = build_expansion_status(ja)

        total_time = calculate_remaining_time(ja["program_status"])

        lines = build_display_lines(
            ja,
            main_status,
            expansion_status,
            net_ip,
            total_time,
        )

        print_display_lines(lines)
        write_display(lines, wake=wake)

        # Do not allow the one-second clock to overwrite an error
        # message until a complete successful display refresh occurs.
        error_active.clear()


def safe_update_display(wake=True):
    """
    Refresh the display while handling OpenSprinkler API failures.

    Return True on success and False on API failure.
    """
    try:
        update_display(wake=wake)
        return True

    except (
        OpenSprinklerAuthenticationError,
        OpenSprinklerConnectionError,
    ) as e:
        show_opensprinkler_error(e)
        return False


######################### Clock Thread #########################


def update_clock():
    """
    Update only LCD row 1 once per second.

    No OpenSprinkler API or MQTT request is performed.

    Clock updates pause while an error message is being displayed.
    """
    while not stop_event.is_set():
        try:
            if not error_active.is_set():
                line1 = format_clock_line()

                with lcd_lock:
                    lcd.cursor_pos = (0, 0)
                    lcd.write_string(format_lcd_line(line1))

        except Exception as e:
            print(f"Clock update failed: {e}")

        # Synchronize approximately to the start of each second.
        delay = 1.0 - (time.time() % 1.0)

        if stop_event.wait(delay):
            break


######################### Periodic Refresh Thread #########################


def periodic_refresh():
    """
    Perform a full OpenSprinkler refresh every 30 seconds.

    MQTT provides immediate updates when an event occurs; this
    periodic refresh acts as a synchronization fallback.
    """
    while not stop_event.wait(30):
        safe_update_display(wake=False)


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
    print(f"[Connected with result code {reason_code}]")

    if reason_code.is_failure:
        print(f"MQTT connection failed: {reason_code}")

        show_error(
            "MQTT broker",
            "Login failed",
            "Check username",
            "and password",
            wake=True,
        )

        return

    client.subscribe("opensprinkler/#")

    wake_backlight()

    with lcd_lock:
        lcd.cursor_pos = (0, 0)
        lcd.write_string(format_lcd_line("MQTT Connected"))

        lcd.cursor_pos = (1, 0)
        lcd.write_string(format_lcd_line("Requesting info"))

    error_active.clear()


def mqtt_message(
    client,
    userdata,
    msg,
):
    """
    Immediately refresh OpenSprinkler status after an MQTT event.
    """
    print("Msg:" + msg.topic + ": " + str(msg.payload))

    safe_update_display(wake=True)


######################### LCD Initialization #########################


def initialize_lcd():
    """
    Initialize the LCD and define custom characters.
    """
    display = i2c.CharLCD(
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

    custom_characters = (
        # 0 - Network connected
        (
            0b00000,
            0b00000,
            0b00000,
            0b00001,
            0b00001,
            0b00101,
            0b00101,
            0b10101,
        ),
        # 1 - Network disconnected
        (
            0b00000,
            0b10100,
            0b01000,
            0b10101,
            0b00001,
            0b00101,
            0b00101,
            0b10101,
        ),
        # 2 - MicroSD card
        (
            0b00000,
            0b00000,
            0b11111,
            0b10001,
            0b11111,
            0b10001,
            0b10011,
            0b11110,
        ),
        # 3 - Rain
        (
            0b00000,
            0b00000,
            0b00110,
            0b01001,
            0b11111,
            0b00000,
            0b10101,
            0b10101,
        ),
        # 4 - Connection
        (
            0b00000,
            0b00000,
            0b00111,
            0b00011,
            0b00101,
            0b01000,
            0b10000,
            0b00000,
        ),
        # 5 - Remote extension
        (
            0b00000,
            0b00000,
            0b00000,
            0b10001,
            0b01011,
            0b00101,
            0b01001,
            0b11110,
        ),
        # 6 - Flow sensor
        (
            0b00000,
            0b00000,
            0b00000,
            0b11010,
            0b10010,
            0b11010,
            0b10011,
            0b00000,
        ),
        # 7 - Program switch
        (
            0b00000,
            0b11100,
            0b10100,
            0b11100,
            0b10010,
            0b10110,
            0b00010,
            0b00111,
        ),
    )

    for index, character in enumerate(custom_characters):
        display.create_char(
            index,
            character,
        )

    display.clear()

    display.cursor_pos = (0, 0)
    display.write_string(format_lcd_line("Connecting to"))

    display.cursor_pos = (1, 0)
    display.write_string(format_lcd_line("MQTT broker..."))

    return display


######################### MQTT Setup #########################


def create_mqtt_client(ja):
    """
    Configure and return the Paho MQTT client using settings obtained
    from OpenSprinkler.
    """
    if not ja["mqtt_enabled"]:
        show_error(
            "MQTT disabled",
            "Enable MQTT in",
            "OpenSprinkler",
            "Integration",
            wake=True,
        )

        raise RuntimeError("MQTT is disabled in OpenSprinkler.")

    mqtt_address = ja["mqtt_host"]
    mqtt_port = ja["mqtt_port"]
    mqtt_user = ja["mqtt_user"]
    mqtt_password = ja["mqtt_password"]

    if not mqtt_address or not mqtt_port:
        show_error(
            "MQTT config",
            "Missing broker",
            "Check OpenSprinkler",
            "Integration",
            wake=True,
        )

        raise RuntimeError("OpenSprinkler MQTT broker configuration is incomplete.")

    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
    )

    mqtt_client.on_connect = mqtt_connect
    mqtt_client.on_message = mqtt_message

    if mqtt_user:
        mqtt_client.username_pw_set(
            mqtt_user,
            mqtt_password,
        )

    try:
        mqtt_client.connect(
            mqtt_address,
            mqtt_port,
            keepalive=60,
        )

    except (OSError, ValueError) as e:
        print(f"Unable to connect to MQTT broker " f"{mqtt_address}:{mqtt_port}: {e}")

        show_error(
            "MQTT broker",
            "Connection failed",
            "Check broker",
            "and network",
            wake=True,
        )

        raise RuntimeError("Unable to connect to MQTT broker.") from e

    return mqtt_client


######################### Program Startup Helpers #########################


def configure_runtime():
    """
    Configure locale and signal handlers.
    """
    try:
        locale.setlocale(
            locale.LC_TIME,
            date_locale,
        )

    except locale.Error as e:
        print(f"Warning: locale '{date_locale}' could not be loaded: {e}")

    signal.signal(
        signal.SIGINT,
        signal_handler,
    )

    signal.signal(
        signal.SIGTERM,
        signal_handler,
    )


def initialize_display():
    """
    Initialize the global LCD instance.

    Return True on success and False on failure.
    """
    global lcd

    try:
        lcd = initialize_lcd()
        return True

    except Exception as e:
        print(f"Unable to initialize LCD: {e}")
        return False


def load_initial_opensprinkler_data():
    """
    Retrieve the initial OpenSprinkler data.

    OpenSprinkler Pi may take several seconds after boot before its
    HTTP API is fully ready. Retry temporary connection failures
    before giving up.

    Authentication failures are not retried because they require a
    configuration change.

    Return the data dictionary on success, or None on failure.
    """
    retry_interval = 2
    max_attempts = 30

    for attempt in range(1, max_attempts + 1):
        try:
            return get_data(timeout=2)

        except OpenSprinklerAuthenticationError as e:
            show_opensprinkler_error(e)
            return None

        except OpenSprinklerConnectionError as e:
            print(
                f"OpenSprinkler not ready " f"(attempt {attempt}/{max_attempts}): {e}"
            )

            show_error(
                "OpenSprinkler",
                "Starting up...",
                f"Retry {attempt}/{max_attempts}",
                "Please wait",
                wake=True,
            )

            if attempt < max_attempts:
                time.sleep(retry_interval)

    show_error(
        "OpenSprinkler",
        "Not responding",
        "Check service",
        "and network",
        wake=True,
    )

    print("OpenSprinkler did not become available " "within the startup retry period.")

    return None


def initialize_mqtt(ja):
    """
    Create and connect the MQTT client.

    Return the client on success, or None on failure.
    """
    try:
        return create_mqtt_client(ja)

    except RuntimeError as e:
        print(e)
        return None


def start_background_threads():
    """
    Start the periodic refresh and live-clock threads.
    """
    refresh_thread = threading.Thread(
        target=periodic_refresh,
        daemon=True,
        name="periodic-refresh",
    )

    refresh_thread.start()

    clock_thread = threading.Thread(
        target=update_clock,
        daemon=True,
        name="lcd-clock",
    )

    clock_thread.start()


def run_mqtt_loop(mqtt_client):
    """
    Run the MQTT network loop until the program is stopped.
    """
    try:
        mqtt_client.loop_forever()

    except KeyboardInterrupt:
        signal_handler(
            signal.SIGINT,
            None,
        )


######################### Program Startup #########################


def main():
    """
    Initialize and run ospiLCD-mqtt.
    """
    configure_runtime()

    if not initialize_display():
        return 1

    ja = load_initial_opensprinkler_data()

    if ja is None:
        return 1

    mqtt_client = initialize_mqtt(ja)

    if mqtt_client is None:
        return 1

    start_background_threads()

    run_mqtt_loop(mqtt_client)

    return 0


if __name__ == "__main__":
    sys.exit(main())
