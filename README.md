# ospiLCD-mqtt.py

ospiLCD-mqtt is an OpenSpinkler montior that displays the system's status on an LCD display as sprinkler events occur. The script can be run on the OpenSprinkler controller itself (if it is the Pi version) to provide a display on the device, or it can be run on a separate Rasperry Pi to provide a remote status display, as shown below.

*Example status display, run on a Raspberry Pi Zero W*
![Example status display, run from Rasbperry Pi Zero W](file:///home/bigron/git/ospiLCD-mqtt/img/ospiLCD-mqtt-RPi0w.jpg?msec=1718215499322)

**Features:**

- 16x2 and 20x4 I2C LCDs are supported (PCF8574T based, with some minor changes MCP23008 is supported too)
- The first two display lines are identical to LCD on OpenSprinkler 2.x (with icons)
- Third and fourth lines display information based on ospi status (remaining watering time, water level in %, E1 stations status)
- Efficient, LCD updates immediately when a status change occurs on the OpenSprinkler system (e.g. a station starts/ends) with no contininous polling of the API.
- LCD backlight can be configured to be on all the time, or to automatically turn on when showing a new status then turn off after a configurable timeout.
- Can be used as remote OpenSprinkler LCD display, or directly on a OpenSprinklerPi system to provide an on-system display.
- Runs well on all current Raspberry Pis (2, 3, 4, Zero W)

 ![4 line display, built into OpenSprinkler Pi, using Stanley's build](file:///home/bigron/git/ospiLCD-mqtt/img/ospilcd9sm.jpg?msec=1718215499309) This project is based on code from Stanley's excellent build at https://github.com/stanoba/ospiLCD. Please refer to his project for designs for 3D printed case, pcb designs, and other build tips. *(Shown to the right, a _4 line LCD status display, built into OpenSprinkler Pi, using Stanley's build)*

This ospiLCD-mqtt version makes two functional changes from the original ospiLCD project that are important to note up front:

- It subscribes to an MQTT server to receive immediate notifications of OpenSprinkler events, then uses the OpenSprinkler API to gather current data.
- Rather than a "one shot" script that runs from a cron job, this script runs ongoing in a service loop, responding to events as needed.

There are two general parts to setting up ospiLCD-mqtt and getting it running:

1. Setting up the Rasperry Pi with the LCD display and the software
2. Setting up MQTT notifications

The sections below walk through the steps for setting these up.

# Setup and Installation

## 1. Installing the LCD Display

Use an I2C LCD display module supported by the RPLCD library. Details about what display modules are supported, and how to wire the LCD to the Raspberry Pi are well documented in the [RPLCD library docs, here.](https://rplcd.readthedocs.io/en/stable/getting_started.html)

If you would like to install directly onto the OpenSprinkler Rasbperry Pi, follow [Stanley's instructions, here](https://github.com/stanoba/ospiLCD.)

## 2. Installing the Display Software

Starting with a recent installation of Raspbian or Raspbian Light, here are steps to install the libraries and code needed:

First, configure the Raspberry Pi to connect to your network, which needs have access to the OpenSprinkler system and the MQTT server you will be using.

Then use `apt` to install pip, smbus, and i2c tools:

```bash
$ sudo apt update
$ sudo apt upgrade -y
$ sudo apt install python-pip python-smbus i2c-tools
```

Install [RPLCD](https://pypi.python.org/pypi/RPLCD/) and paho-mqtt libraries using pip (**Note:** at this time, paho-mqtt needs to be older than 2.0, hence the "<2.0.0" for that command):

```bash
$ sudo pip3 install RPLCD
$ sudo pip3 install "paho-mqtt<2.0.0"
```

Install ospiLCD script from github:

```bash
$ cd /home/pi/
$ wget https://github.com/RonRN18/ospiLCD-mqtt/blob/master/ospiLCD-mqtt.py
$ chmod +x ospiLCD-mqtt.py
```

## 3. Setup a MQTT "broker" (server)

OpenSprinkler has built in support for MQTT, which is a lightweight messaging protocol used by many IoT devices to communicate status and updates. There are a number of popular cloud based MQTT services available that you could use, if you don't want to run your own. Or, you can easily run an MQTT server on your Raspberry Pi, or a Linux system on your network. If you would like to use a cloud based MQTT broker, skip this section and proceed to the next section.

Install the "mosquitto" MQTT broker on your Rasbperry Pi (or another Linux system on the network.)

```bash
$ sudo apt install mosquitto
```

The installation should automatically start the mosquitto MQTT broker service, as well as create service startup scripts to ensure it starts up on system boot. Quite helpful.

To double check that mosquitto process is running, you can use `ps`:

```bash
$ ps -e | grep mosquitto 
10806 ?        00:00:00 mosquitto
```

Now, you need to get the IP address of your new MQTT broker in order to tell your OpenSprinkler system where to find it. You can get this using the following command:

```bash
$ hostname -I
```

Take note of the first part of the resonse, the IPv4 address of your Raspberry Pi, so you can ou'll use this to configure your OpenSprinkler system.

## 4. Configure OpenSprinkler System to use MQTT

In the OpenSprinker UI, configure the MQTT server (broker) information. Do this by clicking on the multi square icon in the bottom right, and choosing "Edit Options", then select the "Integration" section (shown below, left). Find MQTT and click "Tap to Configure" next to it.

| 1: OpenSprinkler Edit Options, Integration | 2: MQTT Settings |
| --- | --- |
| ![Edit Options, Integration](file:///home/bigron/git/ospiLCD-mqtt/img/OS-EditOptions.png?msec=1718215499310) | ![MQTT Options](file:///home/bigron/git/ospiLCD-mqtt/img/OS-MQTT_settings.png?msec=1718215499311) |

Fill in the IP address of the MQTT server (shown above, right). If you're using the mosquitto server, the default port is 1883. If your server requires username and passowrd, enter it. The default mosquitto server described above doesn't require any -- you can leave them blank.

Click submit, and return to the main screen.

## 5. Configure ospiLCD-mqtt.py

Edit the `ospiLCD-mqtt.py` file:
 ```bash
 $ nano ospiLCD-mqtt.py
```

Find the "User Variables" section near the beginning of the file, and set these appropriately for your setup.

```python
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
```

The osAddress must be set to your OpenSprinkler IP address, and this address must be accessable to your Raspberry Pi. If you're running 'ospiLCD-mqtt.py' on the OpenSprinkler Pi, then you can set this address to "127.0.0.1" refering to itself.

The lines that start off with "LCD" will need to be altered if you are using a different LCD panel than I have used, such as a 16-character per line or 2-line display. I am using a 20-character by 4-line display. The controller of my panel is a PCF8574, purchased from [Amazon](https://www.amazon.com/gp/product/B0C1G9GBRZ).

## MD5Hash of OSPi web interface password

If you have changed the default OSPi web interface password from the default of "opendoor", you will need to change "md5hash" on line# 39. To find the md5hash, you can open `hashpass.py` with a text editor (nano, vi, vim) and change the word "opendoor" with your new password between the double-quotation marks. You will then need to make `hashpass.py` executable by typing:

```bash
$ chmod +x hashpass.py
```

Now, execute the edited hashpass.py file by typing:

```bash
$ ./hashpass.py
```

This will output the new md5hash of the new password. Replace the original md5hash with this new version on line# 39 of `ospiLCD-mqtt.py`.

## 6. Run ospiLCD-mqtt.py

Now we're all ready to to run:

```bash
$ ./ospiLCD-mqtt.py
```

## Troubleshooting

When `ospiLCD-mqtt.py` is run, the the LCD Screen should should light, briefly indicating it is subscribing to OpenSpinkler messages on the MQTT server:

```
Connecting to
MQTT broker...
```

If it cannot connect to the MQTT server, it will stay on this message indefinately. In this case, check the MQTT server settings in `ospiLCD-mqtt.py`and then try again.

If it successfully connects to the MQTT broker, it will display the following message:

```
MQTT Connected
Requesting Info
```

If it stays on this message, this means it either cannot connect to and query the OpenSprinkler system API, or the OpenSprinkler system is not able to connect to the MQTT server. In this case, double check the MQTT related parameters in your OpenSprinkler system, and then try again.

If all is successful, the above messages will only be shown briefly as it successfully subscribes to MQTT messages, queries the OpenSprinkler status, and then formats and displays the status LCD display, such as below:

![20x4 lcd status display](file:///home/bigron/git/ospiLCD-mqtt/img/ospilcd5sm.jpg?msec=1718215499314)

# Running as a Service

Obviously, once you get the script functioning properly, you do not want to log in and start a Python script every time the device is rebooted or loses power. In order to get this script to start automatically, it needs to be started as a systemd service. Again, ***make sure the script is working before creating and starting the service.***

The first step is to create the service file. I've called mine `/etc/systemd/system/ospilcd.service`. I have used **nano** as my text editor:

```bash
$ sudo nano /etc/systemd/system/ospilcd.service
```

Place the following in the file:

```bash
[Unit]
Description=OpenSprinkler Pi LCD
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=on-failure
RestartSec=1
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python /home/pi/ospiLCD-mqtt.py

[Install]
WantedBy=multi-user.target
```

This service file *assumes* that you are using the default Raspbian username of `pi` and that you placed the `ospiLCD-mqtt.py` in your home directory. If you have changed anything from my assumption, change the `User`, `WorkingDirectory`, and `ExecStart` lines accordingly.

Once you have saved and exited your text editor, you will need to do the following to enable and start the service.

```bash
$ sudo systemctl daemon-reload
$ sudo systemctl enable ospilcd.service
$ sudo systemctl start ospilcd.service
```

To verify if the service is running, you can type:

```bash
$ systemctl status ospilcd.service
● ospilcd.service - OpenSprinkler Pi LCD
     Loaded: loaded (/etc/systemd/system/ospilcd.service; enabled; vendor prese>
     Active: active (running) since Wed 2024-06-12 09:48:11 PDT; 2h 9min ago
   Main PID: 804 (python)
      Tasks: 4 (limit: 1595)
        CPU: 51.883s
     CGroup: /system.slice/ospilcd.service
             └─804 /usr/bin/python /home/bigron/ospiLCD-mqtt.py

Jun 12 11:55:09 OSPi python[804]: Msg:opensprinkler/availability: b'online'
```

As you can see, my service is currently running. If you have made any mistakes in creating the service file and you re-edit the file, upon saving and quitting your text editor, run:

```bash
$ sudo systemctl daemon-reload
$ sudo systemctl restart ospilcd.service
```

### *Notes about my script*

I know my programming skills are not the greatest but I needed to rework many things that no longer worked with Sirkus7's original version of this. I was getting rude, belittling responses when questioning "experts" in the Python forums on how to make changes. At least [ChatGPT](https://chatgpt.com/) did not give me an attitude! While there were flaws in code generated in ChatGPT, I was able to learn concepts from their examples. I realize that my code may not be as elegant as it could, but it at least is working for me.

I spoke with Ray from [OpenSprinkler](https://opensprinkler.com) about adding LCD support into the OSPi version and he mentioned that he would like to eventually have it built into the OSPi version, like it is in the microcontroller version, but there are a few hurdles that need to be made before this happens. The rest of the OpenSprinkler firmware is written in C++ as opposed to Python and if the LCD support could be built into the main OpenSprinkler firmware, that would make this project obsolete and *that* would make me very happy. At this time, with my current settings, my LCD is refreshed every 30 seconds and the whole screen flashes with each refresh. With it built into the OpenSprinkler firmware, the display should always be live and not flash.

# Helpful References

- Stanley's ospiLCD project: https://github.com/stanoba/ospiLCD
- RPLCD Library Documentation: https://rplcd.readthedocs.io/en/stable/index.html
- Open Sprinkler API Documentation: https://openthings.freshdesk.com/support/solutions/articles/5000716363-os-api-documents
