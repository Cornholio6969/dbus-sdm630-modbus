# dbus-sdm630-modbus

Victron Venus OS D-Bus service for an Eastron SDM630 Modbus V3 three-phase meter over Modbus RTU.

It publishes the SDM630 as a Victron grid/genset/AC-load style meter so systems such as a MultiPlus-II can use the live power, voltage, current, frequency, power factor, and import/export energy values.

## Features

- Reads SDM630 Modbus RTU input registers directly over RS485.
- Publishes a `com.victronenergy.grid.*`, `genset`, `acload`, or `heatpump` D-Bus service.
- Supports total and per-phase power, current, voltage, frequency, power factor, and kWh values.
- Works with both pymodbus 2.x and 3.x import/call styles.
- Includes a Venus OS `runit` service folder and install/uninstall scripts.
- Keeps local `config.ini` out of git.

## Hardware

- Victron GX device or Venus OS system.
- Eastron SDM630 Modbus V3 meter.
- USB RS485 adapter.
- Correct A/B RS485 wiring between adapter and meter.

Typical SDM630 defaults are slave address `1`, baud `9600`, parity `N`, 8 data bits, and 1 stop bit.

## Install On Venus OS

Copy the repository to your GX device, then run:

```sh
cd /data/etc/dbus-sdm630-modbus
./install.sh
```

If you run `install.sh` from another directory, it copies the project into `/data/etc/dbus-sdm630-modbus` and re-runs itself there.

The installer:

- creates `config.ini` from `config.sample.ini` if needed,
- sets executable permissions,
- links the runit service into `/service/dbus-sdm630-modbus`,
- adds the installer to `/data/rc.local` so it survives Venus OS firmware updates,
- starts or restarts the service.

## Configure

Edit:

```sh
nano /data/etc/dbus-sdm630-modbus/config.ini
```

Important settings:

```ini
[DEFAULT]
device_name = SDM630 Modbus Grid
device_type = grid
device_instance = 40

[MODBUS]
port = /dev/ttyUSB0
slave_id = 1
baudrate = 9600
parity = N
stopbits = 1
bytesize = 8
invert_power = false
```

Use `invert_power = true` if import/export direction is backwards for your installation.

## Service Commands

```sh
svstat /service/dbus-sdm630-modbus
svc -t /service/dbus-sdm630-modbus
tail -f /var/log/dbus-sdm630-modbus/current
```

The helper also works when run from the installed directory:

```sh
./restart.sh
```

## Diagnostics

Find a responding Modbus slave:

```sh
python3 tools/scan_modbus.py --port /dev/ttyUSB0
```

Read L1 voltage:

```sh
python3 tools/read_l1_voltage.py --port /dev/ttyUSB0 --slave-id 1
```

If the driver cannot read the meter, check:

- RS485 A/B wiring and termination.
- The serial adapter path in `config.ini`.
- SDM630 baud/parity/slave address.
- Whether another process is using the USB serial port.
- Logs in `/var/log/dbus-sdm630-modbus/current`.

## D-Bus Paths

The service publishes:

- `/Ac/Power`, `/Ac/Current`, `/Ac/Voltage`, `/Ac/Frequency`, `/Ac/PowerFactor`
- `/Ac/Energy/Forward`, `/Ac/Energy/Reverse`
- `/Ac/L1/*`, `/Ac/L2/*`, `/Ac/L3/*` phase values
- `/Connected`, `/UpdateIndex`, and standard Victron management paths

## Repository Notes

`config.ini` is intentionally ignored because it contains machine-specific serial settings. Publish `config.sample.ini`, not your live config.

The `ext/velib_python` files are vendored Victron helper modules used by many Venus OS D-Bus drivers.

## License

This project is MIT licensed. Vendored Victron helper files keep their original MIT license in `ext/velib_python/LICENSE`.
