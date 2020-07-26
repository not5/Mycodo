---
layout: default
---

Mycodo is open source software for the Raspberry Pi that couples inputs and outputs in interesting ways to sense and manipulate the environment.

## Features

*   **[Inputs](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#input)** that record measurements from a number of places, including sensors, GPIO pin states, analog-to-digital converters, etc. (or write your own custom input module).
*   **[Outputs](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#output)** that perform actions such as switching GPIO pins high/low, generating PWM signals, executing Linux shell commands and Python code, etc. (or write your own custom output module).
*   **[Web Interface](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#web-interface)** for securely accessing the system using a web browser on your local network or anywhere in the world with an internet connection.
*   **[Dashboards](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#dashboard)** that display configurable widgets, including interactive live and historical graphs, gauges, output state indicators, text measurements.
*   **[Proportional Integral Derivative (PID) controllers](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#pid-controller)** that regulate environmental conditions with feedback loops utilizing Inputs and Outputs.
*   **[Setpoint Tracking](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#methods)** for changing a PID controller setpoint over time, for use with things like reptile terrariums, reflow ovens, thermal cyclers, sous-vide cooking, and more.
*   **[Conditional Statements](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#conditional)** that react to input measurements, manipulate outputs, and execute actions based on user-generated code. This is a very powerful feature that enables custom user-created [conditions](https://en.wikipedia.org/wiki/Conditional_(computer_programming))) for Inputs, Outputs, Actions, and other parts of the system.
*   **[Triggers](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#trigger)** that can trigger actions at periodic intervals (daily, duration, sunrise/sunset, etc.).
*   **[Alerts](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#alerts)** to notify via email when measurements reach or exceed user-specified thresholds.
*   **[Notes](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#notes)** to keep track of events, alerts, and other important points in time.
*   **[Camera](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#camera)** for remote live stream, image capture, or time-lapse photography.
*   **[Energy Usage Statistics](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#energy-usage)** to calculate and track power consumption and cost over time.
*   **[Upgrade System](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#upgrading)** to easily upgrade the Mycodo system to the latest release or restore to a previously-backed up version.
*   **[Translation](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst#translations)** to several languages, including English, Chinese, Dutch, German, French, Italian, Norwegian, Portuguese, Russian, Serbian, Spanish, and Swedish.

## Uses

See the [README](https://github.com/kizniche/Mycodo#uses) for more information.

## Get Mycodo

### Prerequisites

*   [Raspberry Pi](https://www.raspberrypi.org/) single-board computer (any version: Zero, 1, 2, 3, or 4)
*   [Raspbian OS](https://www.raspberrypi.org/downloads/raspbian/) flashed to a micro SD card
*   An active internet connection

### Install

Once you have the Raspberry Pi booted into Raspbian with an internet connection, run the following command in a terminal to initiate the Mycodo install:

```bash
curl -L https://kizniche.github.io/Mycodo/install | bash
```

If the install is successful, open a web browser to the Raspberry Pi's IP address and you will be greeted with a screen to create an Admin user and password.

```
https://127.0.0.1/
```

## Support

*   [Mycodo on GitHub](https://github.com/kizniche/Mycodo)
*   [Mycodo Manual](https://github.com/kizniche/Mycodo/blob/master/mycodo-manual.rst)
*   [Mycodo API](https://kizniche.github.io/Mycodo/mycodo-api.html)
*   [Mycodo Support](https://play.google.com/store/apps/details?id=com.mycodo.mycododocs) (Android App)

## Screenshots

![Mycodo 5.7.2 Dashboard](https://kylegabriel.com/screenshots/screenshot_mycodo_dashbaord_v5.7.2.png)

---

![Mycodo 3.6.0 Dashboard](https://kylegabriel.com/screenshots/screenshot_mycodo_dashboard_v3.6.0.png)

---

![Mycodo 5.2.0 Dashboard](https://kylegabriel.com/screenshots/screenshot_mycodo_dashboard_v5.2.0.png)

---

![Mycodo 5.5.0 Data Page](https://kylegabriel.com/screenshots/screenshot_mycodo_data_v5.5.0.png)

---

![Live Page](https://kylegabriel.com/projects/wp-content/uploads/sites/3/2017/03/screenshot-192.168.0.7-2017-03-01-18-17-14-live.png)
