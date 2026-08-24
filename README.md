# ospiLCD-mqtt


`ospiLCD-mqtt` displays the current status of an
[OpenSprinkler](https://opensprinkler.com/) controller on an I2C character LCD
connected to a Raspberry Pi.

This project is based on the original `ospiLCD` project and later MQTT-enabled
versions of it, but has been updated for current Raspberry Pi OS, Python, and
OpenSprinkler installations.

The display can run directly on an OpenSprinkler Pi (OSPi), or on another
Raspberry Pi that can reach the OpenSprinkler controller over the network.

Two display layouts are available:

- **Classic mode** preserves the compact controller-oriented status display
  inherited from earlier versions of `ospiLCD`.
- **Named mode** provides a more human-readable display using the station names
  configured in OpenSprinkler.

---

# What this version does

The original `ospiLCD` implementation was essentially a "one shot" script that
was periodically started by cron.

`ospiLCD-mqtt` instead runs continuously as a systemd service and combines
event-driven OpenSprinkler updates with locally maintained LCD information.

It uses several different update mechanisms:

1. **Local display information is updated without polling OpenSprinkler.**

   The clock is maintained locally from the Raspberry Pi's system clock.

   In named display mode, the remaining watering time is also maintained
   locally between controller updates.

   Long station names are scrolled locally when necessary.

2. **MQTT events trigger immediate controller updates.**

   When OpenSprinkler reports an event such as a station starting or stopping,
   `ospiLCD-mqtt` immediately retrieves the current controller state from the
   OpenSprinkler API and updates the LCD.

3. **A full status refresh occurs every 30 seconds.**

   This provides a synchronization fallback if an MQTT message is missed or an
   event is not configured for MQTT notification.

This provides a responsive display without continuously polling OpenSprinkler
for information that can be maintained locally.

---

# Display modes

## Named mode

Named mode is intended to provide useful information at a glance without
requiring the user to remember which controller output corresponds to a
particular irrigation area.

A typical idle display on a 20x4 LCD looks similar to:

```text
09:01:05 Sun 08-23
System idle
Water level: 129%
OSPi.example.tld
```

When a station is running:

```text
09:00:05 Sun 08-23
Backyard/Garden
Remaining: 1:00
OSPi.example.tld
```

The first row displays the local date and time.

The second row displays the OpenSprinkler station name while watering is
active. When no station is active, it displays `System idle`.

The third row displays a live remaining-time countdown while watering is
active. When idle, it displays the current OpenSprinkler water level.

The fourth row can contain user-defined text such as a hostname. If no footer
is configured, the Raspberry Pi's IPv4 address is displayed instead.

### Long station names

Station names are obtained directly from OpenSprinkler's configured station
names.

Names that fit within the configured LCD width remain stationary.

Names longer than the LCD width automatically scroll so the entire name can be
read. The beginning and end of the name are held briefly rather than using a
continuously moving marquee.

For example, on a 20-column LCD:

```text
Backyard - Strawberr
ackyard - Strawberri
ckyard - Strawberries
```

No fixed station-name length is assumed by the LCD code. Scrolling is based on
the configured LCD width and the length of the station name returned by
OpenSprinkler.

### Live countdown

When a station begins running, `ospiLCD-mqtt` obtains its remaining run time
from OpenSprinkler and establishes a local countdown.

The countdown then updates locally without making an OpenSprinkler API request
every second.

Periodic API refreshes and MQTT-triggered updates resynchronize the countdown
with the controller.

## Classic mode

Classic mode retains the compact status layout derived from the earlier
`ospiLCD` projects.

A typical idle display may look similar to:

```text
09:01:05 Sun 08-23
MC:________
Water level:129%
192.168.1.100
```

A running station may appear as:

```text
09:00:05 Sun 08-23
MC:1_______
Water level:129%
Rt:0:01:00 h:m:s
```

This mode also retains support for the compact master-station, expansion-board,
sensor, remote-extension, and network indicators used by the earlier display
design.

---

## Behavior notes and limitations

The named display is designed primarily for a 20x4 character LCD. Smaller
displays may operate, but not all information rows will be visible.

Named mode currently displays the first active station reported by
OpenSprinkler. Installations that intentionally run multiple stations
simultaneously may therefore see only one active station name and its
remaining time.

Station-name scrolling and the live remaining-time countdown are maintained
locally by the Raspberry Pi between OpenSprinkler updates. These local display
updates do not generate additional MQTT traffic or OpenSprinkler API requests.

OpenSprinkler remains the authoritative source of controller state. MQTT events
and the periodic 30-second refresh resynchronize the LCD with the controller.

# Requirements

## Hardware

- Raspberry Pi
- OpenSprinkler or OpenSprinkler Pi controller
- HD44780-compatible character LCD
- I2C LCD backpack, typically PCF8574
- Appropriate wiring between the Raspberry Pi and LCD

A 20-column by 4-row LCD is recommended and is the configuration primarily
used by this project.

## 3D-Printed Case

A custom 3D-printed enclosure for the OSPi and 20x4 LCD is included with this
project.

The [`Case`](Case/) directory contains:

- Ready-to-print STL files for the top and bottom of the enclosure
- Parametric OpenSCAD source files
- Supporting OpenSCAD modules and SVG artwork
- Photographs of the completed enclosure
- Additional construction and printing information

The enclosure was designed so that the OSPi remains mounted and connected to
the field wiring when the cover is removed. Threaded heat-set inserts are used
for frequently removed screws rather than threading directly into the printed
plastic.

The current enclosure was designed around an older OSPi v1.52 and the Raspberry
Pi hardware used in the original installation. Users with newer OSPi or
Raspberry Pi hardware should verify board dimensions and connector locations
before printing.

See the [`Case`](Case/) directory for the design files and additional
information.

## Software

The installer is intended for Raspberry Pi OS and installs the required system
packages automatically.

Python dependencies are installed into a project-specific virtual environment
from `requirements.txt`.

---

# 1. Enable I2C

On Raspberry Pi OS, run:

```bash
sudo raspi-config
```

Select:

```text
Interface Options
    -> I2C
        -> Enable
```

Reboot if requested.

After rebooting, verify that the I2C interface exists:

```bash
ls /dev/i2c-1
```

You should see:

```text
/dev/i2c-1
```

You can scan the I2C bus with:

```bash
i2cdetect -y 1
```

A typical LCD backpack may appear at address `0x27`, although other addresses
such as `0x3f` are also common.

Example:

```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- 27 -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

In this example, the LCD address is:

```text
0x27
```

Use the address reported by your own hardware.

---

# 2. Clone and install ospiLCD-mqtt

Clone the repository:

```bash
git clone https://github.com/RonRN18/ospiLCD-mqtt.git
cd ospiLCD-mqtt
```

If you specifically want to test the `named-display` development branch:

```bash
git switch named-display
```

Run the installer as your **normal user**:

```bash
./install.sh
```

Do **not** run the entire installer with `sudo`.

The installer will request `sudo` only for operations that require root
privileges.

## What the installer does

`install.sh`:

- Installs required Raspberry Pi OS packages.
- Verifies that `/dev/i2c-1` exists.
- Ensures that the current user has access to the I2C interface.
- Creates a Python virtual environment in `.venv`.
- Installs the Python packages listed in `requirements.txt`.
- Performs a Python syntax check.
- Creates `ospilcd.ini` from `ospilcd.ini.example` if needed.
- Preserves an existing `ospilcd.ini`.
- Creates a systemd service using the actual username and project directory.

The installer does **not** automatically start or enable the service. This
allows the configuration and LCD to be tested first.

---

# 3. Configure OpenSprinkler API access

`ospiLCD-mqtt` obtains controller information from the OpenSprinkler JSON API.

Configuration is stored in:

```text
ospilcd.ini
```

This file is intentionally excluded from Git so that local settings and
credentials are not committed to the repository.

An example configuration is provided as:

```text
ospilcd.ini.example
```

The OpenSprinkler section looks similar to:

```ini
[OpenSprinkler]

address = 127.0.0.1
port = 8080

# MD5 hash of the OpenSprinkler password.
password_hash = a6d82bced638de3def1e9bbb4983225c
```

If `ospiLCD-mqtt` is running on the same Raspberry Pi as OpenSprinkler,
`127.0.0.1` is normally appropriate.

If OpenSprinkler is running on another device, use its hostname or IP address
instead.

## OpenSprinkler password hash

The OpenSprinkler API expects the MD5 hash of the controller password rather
than the plain-text password.

The example hash:

```text
a6d82bced638de3def1e9bbb4983225c
```

corresponds to OpenSprinkler's default password:

```text
opendoor
```

If you have changed the OpenSprinkler password, generate the appropriate hash
using:

```bash
python hashpass.py
```

Enter your OpenSprinkler password when prompted and place the resulting hash in
`ospilcd.ini`.

The password itself is not echoed while being entered and is not stored by
`hashpass.py`.

Do not place the plain-text OpenSprinkler password in `ospilcd.ini`.

---

# 4. Configure the LCD

The LCD section of `ospilcd.ini` contains settings similar to:

```ini
[LCD]

i2c_expander = PCF8574
i2c_address = 0x27
columns = 20
rows = 4
backlight_timeout = 60
```

Set `i2c_address` to the address reported by:

```bash
i2cdetect -y 1
```

The default configuration assumes a 20x4 LCD.

## Backlight timeout

`backlight_timeout` specifies how many seconds the LCD backlight remains on
after activity when automatic backlight shutoff is enabled.

For example:

```ini
backlight_timeout = 60
```

sets the timeout to approximately 60 seconds.

Whether the backlight is actually turned off after that interval is controlled
by `auto_backlight_off` in the `[Display]` section.

---

# 5. Configure display behavior

The `[Display]` section controls the display layout, footer, and automatic
backlight behavior.

Example:

```ini
[Display]

mode = named
footer = OSPi.example.tld
auto_backlight_off = false
```

## Display mode

Use:

```ini
mode = classic
```

for the original compact controller-status layout.

Use:

```ini
mode = named
```

for the human-readable station-name layout.

## Footer

The optional `footer` value specifies fixed text for LCD row 4.

For example:

```ini
footer = OSPi.example.tld
```

If `footer` is left blank:

```ini
footer =
```

the Raspberry Pi's detected IPv4 address is displayed instead.

Footer text longer than the configured LCD width is truncated.

## Automatic backlight shutoff

To turn the backlight off after the configured `backlight_timeout`:

```ini
auto_backlight_off = true
```

To leave the LCD backlight on continuously while the application is running:

```ini
auto_backlight_off = false
```

Some common HD44780 I2C backpacks provide only backlight on/off control rather
than true brightness control. For those displays, automatic backlight shutoff
means the backlight turns completely off; it is not gradually dimmed.

Activity such as an MQTT-triggered controller change wakes the backlight when
automatic shutoff is enabled.

Periodic synchronization and local clock/countdown updates do not continually
wake it.

---

# 6. Regional settings

The display uses the Raspberry Pi's local clock.

The regional section can specify the locale used for date formatting:

```ini
[Regional]

locale = en_US.UTF-8
```

Make sure the Raspberry Pi itself has the correct timezone configured.

You can check the current system time with:

```bash
date
```

---

# 7. Configure MQTT in OpenSprinkler

MQTT is used as an **event notification mechanism**.

The LCD does not depend on MQTT messages for the actual controller state.

Instead, an MQTT event tells `ospiLCD-mqtt`:

> Something changed. Ask OpenSprinkler for its current state now.

`ospiLCD-mqtt` then retrieves the current state through the OpenSprinkler API.

This avoids duplicating controller-state logic in the MQTT message handler and
provides an authoritative current state after each event.

Configure MQTT using the OpenSprinkler web interface.

Enter:

- MQTT broker hostname or IP address
- MQTT broker port
- MQTT username, if required
- MQTT password, if required

The OpenSprinkler MQTT publish topic is normally:

```text
opensprinkler
```

and the command subscription topic is normally:

```text
opensprinkler/command
```

`ospiLCD-mqtt` reads the MQTT broker configuration directly from
OpenSprinkler's API. The MQTT password therefore does not need to be duplicated
in `ospilcd.ini`.

---

# 8. Enable OpenSprinkler Notification Events

**This step is important.**

Configuring the MQTT broker establishes the MQTT connection, but OpenSprinkler
must also be told which events it should publish.

In the OpenSprinkler web interface:

1. Open **Edit Options**.
2. Select **Notifications**.
3. Enable the events that should generate notifications.

At minimum, enabling:

- **Station Start**
- **Station Finish**

is recommended for `ospiLCD-mqtt`.

Other notification events may also be enabled if desired.

If no Notification Events are selected, MQTT may still appear to be working.

For example, you may receive:

```text
opensprinkler/availability online
```

but starting or stopping a station will not produce an immediate notification.

The LCD will eventually notice the change during its 30-second synchronization
refresh, but the update will not be immediate.

---

# 9. Test ospiLCD-mqtt interactively

Before enabling the systemd service, run the program manually.

If the service is already running, stop it first:

```bash
sudo systemctl stop ospilcd
```

Then, from the project directory:

```bash
source .venv/bin/activate
python ospiLCD-mqtt.py
```

A successful named-mode connection may produce terminal output similar to:

```text
[Connected with result code Success]
Msg:opensprinkler/availability: b'online'
09:33:28 Sun 08-23
System idle
Water level: 129%
OSPi.example.tld
```

The exact values will depend on your controller and configuration.

The physical LCD contains locally updated information that is not continuously
printed to the terminal.

For example:

- the clock changes locally;
- the named-mode remaining-time countdown changes locally;
- long station names scroll locally.

The full controller state is refreshed approximately every 30 seconds.

Press:

```text
Ctrl+C
```

to stop the interactive test.

The program should exit cleanly.

---

# 10. Test MQTT station notifications

Start a station manually from the OpenSprinkler interface.

If MQTT notifications are configured correctly, `ospiLCD-mqtt` should
immediately receive an event similar to:

```text
Msg:opensprinkler/station/1: b'{"state":1,"duration":60}'
```

In named mode, the display should immediately change to something similar to:

```text
09:33:50 Sun 08-23
Backyard/Garden
Remaining: 1:00
OSPi.example.tld
```

The countdown on the physical LCD should then decrease locally each second.

A later synchronization may produce terminal output such as:

```text
09:33:58 Sun 08-23
Backyard/Garden
Remaining: 0:52
OSPi.example.tld
```

The absence of terminal output every second is normal. The live countdown does
not require an API request or terminal message every second.

When the station finishes, the MQTT station-finish message should trigger an
immediate return to the idle display:

```text
09:34:50 Sun 08-23
System idle
Water level: 129%
OSPi.example.tld
```

The 30-second refresh continues to operate as a fallback even when MQTT is
working correctly.

---

# 11. Start the systemd service

Once interactive testing is successful:

```bash
sudo systemctl start ospilcd
```

Check its status:

```bash
systemctl status ospilcd --no-pager
```

A working service should show:

```text
Active: active (running)
```

View recent log messages with:

```bash
journalctl -u ospilcd -n 50 --no-pager
```

To follow the log live:

```bash
journalctl -u ospilcd -f
```

If everything is working correctly, enable automatic startup at boot:

```bash
sudo systemctl enable ospilcd
```

You can also enable and start it in one command:

```bash
sudo systemctl enable --now ospilcd
```

---

# 12. Startup behavior

On an OSPi installation, OpenSprinkler and `ospiLCD-mqtt` may start at nearly
the same time during boot.

The OpenSprinkler process may be running before its HTTP API is completely
ready.

`ospiLCD-mqtt` handles this automatically.

During initial startup, temporary OpenSprinkler connection failures are retried
rather than immediately causing the application to fail.

You may therefore see log messages such as:

```text
OpenSprinkler not ready (attempt 1/30)
OpenSprinkler not ready (attempt 2/30)
```

This is normal during startup.

An invalid OpenSprinkler password is handled differently. Authentication
failures are not repeatedly retried because they require a configuration
change.

If OpenSprinkler and `ospiLCD-mqtt` are running on the same Raspberry Pi, the
installed systemd service can also be ordered after the OpenSprinkler service.
The application's own retry handling remains useful because a started process
does not necessarily mean that the HTTP API is ready to answer requests.

---

# 13. How updates work

The normal controller-update flow is:

```text
OpenSprinkler event
        |
        | MQTT
        v
     MQTT broker
        |
        v
  ospiLCD-mqtt
        |
        | OpenSprinkler JSON API
        v
 Current controller state
        |
        v
       LCD
```

MQTT provides the notification that something changed.

The OpenSprinkler API provides the current authoritative state.

Between controller updates, several display functions are maintained locally:

```text
Raspberry Pi system clock
        |
        +----> LCD clock

Active-station run time
        |
        +----> local countdown ----> LCD remaining time

OpenSprinkler station name
        |
        +----> local scroller -----> LCD station name
```

Separately:

```text
MQTT event
    -> query OpenSprinkler
    -> synchronize display state

Every 30 seconds
    -> query OpenSprinkler
    -> synchronize display state
```

This design provides immediate event-driven updates, locally responsive display
behavior, and a periodic synchronization fallback without unnecessary
continuous API polling.

---

# 14. Updating ospiLCD-mqtt

Because local configuration is stored in the Git-ignored `ospilcd.ini`, normal
Git updates should not overwrite your controller-specific settings.

From the project directory:

```bash
git pull
```

If `requirements.txt` changed, update the virtual environment:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Then restart the service:

```bash
sudo systemctl restart ospilcd
```

Check its status:

```bash
systemctl status ospilcd --no-pager
```

---

# Troubleshooting

## LCD does not appear

Verify that I2C is enabled:

```bash
ls /dev/i2c-1
```

Then scan the bus:

```bash
i2cdetect -y 1
```

Verify that the detected address matches:

```ini
i2c_address =
```

in `ospilcd.ini`.

Also verify that the user running `ospilcd` has permission to access the I2C
device.

---

## Backlight turns completely off

Many common HD44780 I2C backpacks provide only backlight on/off control.

If:

```ini
auto_backlight_off = true
```

the backlight may therefore become completely dark when the timeout expires
rather than becoming partially dimmer.

If you want the backlight continuously illuminated, use:

```ini
auto_backlight_off = false
```

---

## Named display does not appear

Verify:

```ini
[Display]
mode = named
```

in `ospilcd.ini`.

The default/example configuration may use classic mode for compatibility with
the earlier display layout.

Restart the application after changing the configuration.

---

## Long station name is truncated in terminal output

The physical LCD and terminal output do not necessarily show every local
display update.

Long-name scrolling is performed locally by the live display thread.

The full OpenSprinkler refresh may initially print the station name to the
terminal while the LCD subsequently scrolls it without generating additional
terminal messages.

---

## Countdown does not print every second in the terminal

This is expected.

The named-mode countdown is maintained locally on the Raspberry Pi between
OpenSprinkler synchronization events.

The LCD can therefore show:

```text
Remaining: 0:59
Remaining: 0:58
Remaining: 0:57
```

without making three additional API requests or printing three additional
status blocks to the terminal.

---

## OpenSprinkler authentication failed

If the display or log reports:

```text
OpenSprinkler API authentication failed.
```

verify the `password_hash` value in:

```text
ospilcd.ini
```

Generate a new hash if necessary:

```bash
python hashpass.py
```

---

## OpenSprinkler is temporarily unavailable at boot

Temporary connection failures immediately after boot are expected on some OSPi
systems.

`ospiLCD-mqtt` automatically retries the OpenSprinkler API during startup.

Check the journal:

```bash
journalctl -u ospilcd -n 50 --no-pager
```

Repeated startup messages followed by a successful MQTT connection are normal.

---

## MQTT does not connect

Verify the MQTT configuration in the OpenSprinkler web interface.

Check:

- Broker hostname or IP address
- Port
- Username
- Password

Remember that the MQTT credentials used by `ospiLCD-mqtt` come from
OpenSprinkler's configuration.

If the MQTT password was changed on the broker, it must also be updated in
OpenSprinkler.

---

## MQTT connects, but station changes are not immediate

First verify that OpenSprinkler Notification Events are enabled.

At minimum, enable:

- Station Start
- Station Finish

If the Mosquitto command-line clients are installed, MQTT traffic can be
observed directly:

```bash
mosquitto_sub \
  -h MQTT_BROKER \
  -p 1883 \
  -u MQTT_USERNAME \
  -P 'MQTT_PASSWORD' \
  -t 'opensprinkler/#' \
  -v
```

A correctly configured station start/finish should produce messages similar to:

```text
opensprinkler/station/1 {"state":1,"duration":60}
opensprinkler/station/1 {"state":0,"duration":60}
```

If you receive only:

```text
opensprinkler/availability online
```

verify the Notification Events configuration in OpenSprinkler.

Do not put a real MQTT password in documentation, screenshots, or files
committed to the repository.

---

## View service logs

Recent messages:

```bash
journalctl -u ospilcd -n 50 --no-pager
```

Messages from the current boot:

```bash
journalctl -b -u ospilcd --no-pager
```

Follow messages live:

```bash
journalctl -u ospilcd -f
```

On systems whose clock is corrected after boot, monotonic timestamps can make
startup troubleshooting easier:

```bash
journalctl -b -u ospilcd -o short-monotonic --no-pager
```

---

# Files

Important files in this project include:

```text
ospiLCD-mqtt.py
    Main application.

ospilcd.ini.example
    Example configuration tracked by Git.

ospilcd.ini
    Local configuration. Not tracked by Git.

hashpass.py
    Utility for interactively generating the OpenSprinkler password MD5 hash.

requirements.txt
    Python dependencies installed into the virtual environment.

install.sh
    Installation helper that prepares the Python environment and systemd
    service.

Case/
    3D-printable enclosure files, source models, artwork, and documentation.

.gitattributes
    Repository line-ending configuration.

.gitignore
    Prevents local configuration, virtual environments, and other local files
    from being committed.
```

---

# Security notes

`ospilcd.ini` is intentionally excluded from Git.

Do not commit:

- OpenSprinkler credentials
- MQTT passwords
- private network credentials
- other installation-specific secrets

`hashpass.py` prompts for the OpenSprinkler password rather than requiring the
password to be written into the Python source file.

The generated MD5 value is the value required by the OpenSprinkler API. It
should not be treated as a modern password-storage mechanism or as a substitute
for protecting access to the controller and its configuration.

When posting logs or screenshots publicly, review them for passwords and other
sensitive information before sharing them.

---

# Project History and Credits

This project builds upon the work of earlier OpenSprinkler LCD projects.

It began with **Stanley's original `ospiLCD` project**, which provided an LCD
status display for OpenSprinkler Pi and includes useful information about LCD
hardware, wiring, PCB designs, and 3D-printed enclosures:

https://github.com/stanoba/ospiLCD

The project was subsequently adapted by **sirkus7 as `ospiLCD-mqtt`**, changing
the original periodically executed design into a continuously running
application using MQTT notifications:

https://github.com/sirkus7/ospiLCD-mqtt

This repository is a continuation of that work. It retains the basic purpose
and portions of the design of those earlier projects while modernizing and
substantially refactoring the software for current Raspberry Pi OS, Python,
OpenSprinkler, MQTT, and systemd environments.

Among the changes in the current version are:

- Python 3 modernization and refactoring.
- Current Eclipse Paho MQTT API support.
- Separation of local configuration from program code.
- Interactive password-hash generation without storing the plain-text
  OpenSprinkler password in the utility source.
- Python virtual-environment and dependency management.
- Portable systemd installation without assuming a `pi` username or fixed
  installation directory.
- Event-driven OpenSprinkler updates with periodic synchronization.
- Locally maintained clock information without continuous API polling.
- Selectable classic and named display layouts.
- Human-readable OpenSprinkler station names.
- Automatic scrolling of station names longer than the LCD width.
- Locally maintained active-station countdown in named mode.
- Configurable LCD footer.
- Configurable automatic backlight shutoff.
- OpenSprinkler startup retry and authentication/error handling.
- Installation and troubleshooting improvements.

The **classic display mode** intentionally retains concepts and behavior derived
from the earlier projects. The newer **named display mode** builds on that work
while providing a different, more human-readable presentation of the same
OpenSprinkler controller state.

Thanks to the original contributors whose work made this version possible, as
well as the developers of **OpenSprinkler**, **RPLCD**, and **Eclipse Paho
MQTT**.

---

# License

See the repository for applicable licensing information from this project and
the projects from which it was derived.