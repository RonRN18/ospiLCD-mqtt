#!/usr/bin/env python

# Use this snippet of code to generate the md5hash value for your OpenSprinkler password
# If you have changed the OSPi web interface password, replace "opendoor" (the default password)
# with the new password. Place all of this text between the triple double-quote marks into a new
# file, such as "hashpass.py" and once written, make it executable  (chmod +x hashpass.py) and 
# then execute it (i.e. "./hashpass.py". The hash is an encoded, fixed length equivelant of a
# password that is extremely difficult, if not impossible to reverse. You will replace the current
# string of characters in the "ospiLCD-mqtt.py" line that starts off with "md5hash = ".

import hashlib

m=hashlib.md5(b"opendoor") 
print(m.hexdigest())
