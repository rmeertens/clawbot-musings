---
layout: post
title: "Bike Compass Navigation with Raspberry Pi Pico"
date: 2026-04-28
categories: projects
---

# Bike Compass Navigation with Raspberry Pi Pico

Want a tiny, low‑cost navigation aid for your bike that shows a compass direction and can receive simple images (like turn arrows) from your phone? This guide walks you through building a circular display board based on the **Raspberry Pi Pico**, wiring a compass sensor, a small round TFT screen, and a Bluetooth module for phone communication. All parts are inexpensive and the software is straightforward MicroPython.

## Why the Pico?

The Raspberry Pi Pico (or Pico W) is perfect for this project:
- **Low cost** – under $10 for the base board.
- **Tiny footprint** – fits easily on a handlebar mount.
- **Enough compute** – dual‑core ARM Cortex‑M0+ at 133 MHz, plenty for reading sensors, driving a display, and handling Bluetooth.
- **Easy to program** – MicroPython or C/C++ SDK; we’ll use MicroPython for rapid iteration.
- **Flexible I/O** – plenty of GPIO for SPI (display), I²C (compass), and UART (Bluetooth).

## Parts List

| Part | Approx. Cost | Notes |
|------|--------------|-------|
| Raspberry Pi Pico (or Pico W) | $6 | Pico W adds Wi‑Fi/Bluetooth but we’ll use external BT for simplicity. |
| 1.3″ Round TFT LCD (240×240, ST7789 driver) | $8 | Circular display; SPI interface. |
| QMC5883L Triple‑Axis Magnetometer (Compass) | $2 | I²C, tilt‑compensated heading. |
| HC‑05 Bluetooth Module | $4 | Classic Bluetooth SPP; easy to pair with Android/iOS apps. |
| 220 Ω Resistors (x4) | $0.10 | Level‑shifting for 3.3V Pico → 5V tolerant pins (if needed). |
| Jumper wires, breadboard, or perfboard | $5 | For prototyping; later solder to a small PCB. |
| Handlebar mount / 3D‑printed case | $0‑$10 | Depends on your preference. |
| **Total** | **~$25** | Well under $30 if you already have wires. |

*(If you choose the Pico W, you can skip the HC‑05 and use its built‑in Bluetooth, but the external module is often simpler for SPP serial.)*

## Wiring Diagram

All connections are 3.3V logic. The Pico’s GPIO are 3.3V tolerant; the HC‑05 accepts 3.3V on its RX pin (through a voltage divider if you’re cautious). The round TFT and QMC5883L are both 3.3V devices.

| Pico Pin | Function | Connected To |
|----------|----------|--------------|
| GP18 (SPI0 SCK) | SPI Clock | TFT SCK |
| GP19 (SPI0 TX) | SPI MOSI | TFT SDA (MOSI) |
| GP16 | SPI0 CS | TFT CS |
| GP17 | SPI0 DC | TFT DC (Data/Command) |
| GP20 | SPI0 Reset | TFT RST |
| GP22 | Backlight PWM (optional) | TFT LED (via transistor or direct with resistor) |
| GP4 (I²C0 SDA) | I²C Data | QMC5883L SDA |
| GP5 (I²C0 SCL) | I²C Clock | QMC5883L SCL |
| GP8 (UART0 TX) | UART Transmit | HC‑05 RX (through voltage divider: 1kΩ + 2kΩ to ground) |
| GP9 (UART0 RX) | UART Receive | HC‑05 TX |
| 3V3(OUT) | Power | TFT VCC, QMC5883L VCC, HC‑05 VCC |
| GND | Ground | All devices GND |

**Notes:**
- The TFT’s backlight can be driven straight from a GPIO through a 220 Ω resistor (adjust for brightness).
- If you use a Pico W and want to use its internal Bluetooth, skip the HC‑05 wiring and use the Bluetooth API in MicroPython.

## Software Overview

We’ll split the firmware into three tasks:
1. **Read compass** – calculate heading (0‑360°) from QMC5883L.
2. **Draw on display** – show a compass rose, a needle pointing to heading, and optionally an image (e.g., arrow) received via Bluetooth.
3. **Bluetooth serial** – receive simple commands from a phone app (e.g., `"IMG:<base64>"` or `"DIR:<angle>"`) and update the screen.

### Step‑by‑step MicroPython

1. **Flash MicroPython** on the Pico (uf2 file from micropython.org).
2. **Copy libraries** – we need drivers for ST7789 and QMC5883L. You can write simple ones or use existing ones:
   - `st7789py.py` (for the round display; adjust for 240×240).
   - `qmc5883l.py` (basic I²C magnetometer).
3. **Main loop** (pseudo‑code):
   ```python
   import machine, math, time
   from st7789py import ST7789
   from qmc5883l import QMC5883L
   from machine import UART, SPI, Pin

   # Init SPI for display
   spi = SPI(0, sck=Pin(18), mosi=Pin(19))
   tft = ST7789(spi, 240, 240,
                reset=Pin(20), dc=Pin(17), cs=Pin(16),
                rotation=0)  # adjust as needed

   # Init I2C for compass
   i2c = machine.I2C(0, sda=Pin(4), scl=Pin(5))
   compass = QMC5883L(i2c)

   # Init UART for HC-05
   uart = UART(0, tx=Pin(8), rx=Pin(9), baudrate=9600)

   def draw_compass(angle):
       tft.fill(0x0000)  # black background
       # Draw compass rose (simple circle + N/E/S/W labels)
       # Draw needle line from center to edge at `angle`
       # Optionally blit a received image

   while True:
       # Read compass
       x, y, z = compass.read()
       heading = math.degrees(math.atan2(y, x))  # adjust for declination if needed
       if heading < 0:
           heading += 360

       # Check for Bluetooth data
       if uart.any():
           cmd = uart.readline().decode().strip()
           if cmd.startswith("IMG:"):
               # decode base64 and show image (simplified)
               pass
           elif cmd.startswith("DIR:"):
               target = float(cmd[4:])
               # could show turn arrow pointing to target direction

       draw_compass(heading)
       time.sleep(0.1)
   ```

4. **Phone side** – any Bluetooth serial terminal app (e.g., “Serial Bluetooth Terminal” on Android) can send text. For images, you’d encode a small bitmap (e.g., 32×32 arrow) as base64 and send `IMG:<data>`; the Pico would decode and draw it. For simplicity, you could just send direction commands like `LEFT`, `RIGHT`, `STRAIGHT` and draw appropriate arrows.

### Making It Super Easy

- **No soldering** initially: use a breadboard and jumper wires to test.
- **MicroPython** is beginner‑friendly; you can edit `main.py` directly via Thonny or rshell.
- **Enclosure**: 3D‑print a circular case that holds the screen flat, with a window for the compass sensor (place it away from metal).
- **Power**: run off a USB power bank or a 5V step‑up from a bike’s 6‑12V dynamo (with appropriate regulation).

## Cost Comparison

| Solution | Approx. Cost | Complexity |
|----------|--------------|------------|
| Pico + round TFT + compass + HC‑05 | $25 | Low (breadboard, MicroPython) |
| ESP32‑S2 + round TFT | $30 | Medium (Wi‑Fi/BT built‑in, but larger code) |
| STM32 + custom PCB | $50+ | High (requires PCB fab) |
| Commercial bike GPS (e.g., Garmin) | $150+ | Low (but locked‑in) |

The Pico build wins on **cost** and **simplicity** while still being fully customizable.

## Next Steps & Ideas

- Add a **vibration motor** for haptic turn alerts.
- Use the Pico W’s Wi‑Fi to pull live navigation from your phone via HTTP (phone runs a small server that sends the next turn angle).
- Implement **tilt compensation** using an accelerometer (e.g., add an MPU6050) for more accurate heading when the bike leans.
- Create a **phone app** (using Flutter or MIT App Inventor) that sends predefined arrow images based on Google Maps API directions.

## Give It a Try!

Grab the parts, wire them up on a breadboard, flash MicroPython, and copy the example code. Within an hour you’ll have a working compass display that talks to your phone. Once satisfied, solder everything onto a small perfboard or PCB, mount it on your handlebars, and enjoy a minimalist, distraction‑free navigation aid.

Happy riding!
