This repository contains instructions and code for building and deploying a coastal tide gauge. The tide gauge is typically installed at a coastal location that provides an unobstructed vertical view to the water under all tidal conditions. The distance to the suface of the water is measured by an ultrasonic sensor and reported to a Heltec CubeCell LoRa module, where it is processed and forwarded to a remote Heltec WiFi LoRa ESP32(V3) receiver in text-formatted packets. The receiver outputs the packets to a Raspberry Pi 4 microcomputer, where it is processed and stored for distribution. The Arduino sketches (.ino) are loaded into the respective Heltec devices to transmit and receive measurement packets.
<!---
cfi1513840/cfi1513840 is a ✨ special ✨ repository because its `README.md` (this file) appears on your GitHub profile.
You can click the Preview link to take a look at your changes.
--->
