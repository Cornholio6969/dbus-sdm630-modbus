#!/usr/bin/env python3
"""Victron Venus OS D-Bus service for an Eastron SDM630 Modbus V3 meter."""

from gi.repository import GLib  # pyright: ignore[reportMissingImports]

import configparser
import logging
import os
import platform
import struct
import sys
from time import monotonic, sleep, time

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "ext", "velib_python"))
from vedbus import VeDbusService  # noqa: E402

try:
    from pymodbus.client.sync import ModbusSerialClient
    PYMODBUS_MAJOR = 2
except Exception:
    from pymodbus.client import ModbusSerialClient
    PYMODBUS_MAJOR = 3


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
VERSION = "0.5.0"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f'ERROR: "{CONFIG_FILE}" not found. Copy config.sample.ini to config.ini.')
        sleep(60)
        sys.exit(1)

    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return cfg


config = load_config()


def cfg_int(section, key, default):
    try:
        return int(config[section].get(key, default))
    except Exception:
        return int(default)


def cfg_float(section, key, default):
    try:
        return float(config[section].get(key, default))
    except Exception:
        return float(default)


def cfg_bool(section, key, default=False):
    try:
        return config[section].get(key, str(default)).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return default


LOG_LEVEL = config["DEFAULT"].get("logging", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)

VERBOSE_MODBUS = cfg_bool("MODBUS", "verbose_modbus", False)
logging.getLogger("pymodbus").setLevel(logging.DEBUG if VERBOSE_MODBUS else logging.WARNING)
logging.getLogger("pymodbus.transaction").setLevel(logging.DEBUG if VERBOSE_MODBUS else logging.WARNING)
logging.getLogger("pymodbus.framer.rtu_framer").setLevel(logging.DEBUG if VERBOSE_MODBUS else logging.WARNING)


DEVICE_TYPE_MAP = {
    "grid": ("grid", "Grid"),
    "genset": ("genset", "Genset"),
    "acload": ("acload", "AC Load"),
    "heatpump": ("heatpump", "Heat Pump"),
}

device_type, device_type_name = DEVICE_TYPE_MAP.get(
    config["DEFAULT"].get("device_type", "grid").lower(),
    ("grid", "Grid"),
)

TIMEOUT = cfg_int("DEFAULT", "timeout", 60)
POWER_THRESHOLD_PER_PHASE = cfg_float("DEFAULT", "power_threshold_per_phase", 23000)


def format_kwh(path, value):
    return "---" if value is None else f"{value:.4f}kWh"


def format_amp(path, value):
    return "---" if value is None else f"{value:.2f}A"


def format_watt(path, value):
    return "---" if value is None else f"{value:.0f}W"


def format_volt(path, value):
    return "---" if value is None else f"{value:.2f}V"


def format_hz(path, value):
    return "---" if value is None else f"{value:.3f}Hz"


def format_power_factor(path, value):
    return "---" if value is None else f"{value:.3f}"


def format_int(path, value):
    return f"{int(value)}"


data = {
    "connected": 0,
    "last_changed": 0,
    "last_updated": 0,

    "power": None,
    "current": None,
    "voltage": None,
    "frequency": None,
    "power_factor": None,
    "forward": None,
    "reverse": None,

    "l1_power": None,
    "l1_current": None,
    "l1_voltage": None,
    "l1_frequency": None,
    "l1_power_factor": None,
    "l1_forward": None,
    "l1_reverse": None,
    "l1_total": None,

    "l2_power": None,
    "l2_current": None,
    "l2_voltage": None,
    "l2_frequency": None,
    "l2_power_factor": None,
    "l2_forward": None,
    "l2_reverse": None,
    "l2_total": None,

    "l3_power": None,
    "l3_current": None,
    "l3_voltage": None,
    "l3_frequency": None,
    "l3_power_factor": None,
    "l3_forward": None,
    "l3_reverse": None,
    "l3_total": None,
}


def decode_float(registers, offset):
    return struct.unpack(">f", struct.pack(">HH", registers[offset], registers[offset + 1]))[0]


def add_ac_paths(paths, prefix):
    paths[f"/Ac/{prefix}/Power"] = {"initial": 0, "textformat": format_watt}
    paths[f"/Ac/{prefix}/Current"] = {"initial": 0, "textformat": format_amp}
    paths[f"/Ac/{prefix}/Voltage"] = {"initial": 0, "textformat": format_volt}
    paths[f"/Ac/{prefix}/Frequency"] = {"initial": None, "textformat": format_hz}
    paths[f"/Ac/{prefix}/PowerFactor"] = {"initial": None, "textformat": format_power_factor}
    paths[f"/Ac/{prefix}/Energy/Forward"] = {"initial": None, "textformat": format_kwh}
    paths[f"/Ac/{prefix}/Energy/Reverse"] = {"initial": None, "textformat": format_kwh}
    paths[f"/Ac/{prefix}/Energy/Total"] = {"initial": None, "textformat": format_kwh}


def build_dbus_paths():
    paths = {
        "/Ac/Power": {"initial": 0, "textformat": format_watt},
        "/Ac/Current": {"initial": 0, "textformat": format_amp},
        "/Ac/Voltage": {"initial": 0, "textformat": format_volt},
        "/Ac/Frequency": {"initial": None, "textformat": format_hz},
        "/Ac/PowerFactor": {"initial": None, "textformat": format_power_factor},
        "/Ac/Energy/Forward": {"initial": None, "textformat": format_kwh},
        "/Ac/Energy/Reverse": {"initial": None, "textformat": format_kwh},
    }

    for phase in ("L1", "L2", "L3"):
        add_ac_paths(paths, phase)

    paths["/UpdateIndex"] = {"initial": 0, "textformat": format_int}
    return paths


class SDM630Modbus:
    def __init__(self):
        self.port = config["MODBUS"].get("port", "/dev/ttyUSB1")
        self.slave_id = cfg_int("MODBUS", "slave_id", 1)
        self.baudrate = cfg_int("MODBUS", "baudrate", 9600)
        self.parity = config["MODBUS"].get("parity", "N")
        self.stopbits = cfg_int("MODBUS", "stopbits", 1)
        self.bytesize = cfg_int("MODBUS", "bytesize", 8)
        self.modbus_timeout = cfg_float("MODBUS", "modbus_timeout", 1)
        self.poll_interval_ms = cfg_int("MODBUS", "poll_interval_ms", 200)
        self.reconnect_interval_ms = cfg_int("MODBUS", "reconnect_interval_ms", 1000)
        self.invert_power = cfg_bool("MODBUS", "invert_power", False)
        self.phase_energy_poll_every = max(1, cfg_int("MODBUS", "phase_energy_poll_every", 5))

        self._poll_count = 0
        self.client = None

    def connect(self):
        self.close()

        kwargs = {
            "port": self.port,
            "baudrate": self.baudrate,
            "parity": self.parity,
            "stopbits": self.stopbits,
            "bytesize": self.bytesize,
            "timeout": self.modbus_timeout,
        }

        if PYMODBUS_MAJOR == 2:
            kwargs["method"] = "rtu"

        try:
            self.client = ModbusSerialClient(**kwargs)
            ok = self.client.connect()
            data["connected"] = 1 if ok else 0
            logging.info("Modbus connected=%s port=%s slave=%s", ok, self.port, self.slave_id)
            return ok
        except Exception as e:
            data["connected"] = 0
            logging.error("Could not open Modbus port %s: %s", self.port, e)
            self.client = None
            return False

    def close(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None

    def read_input_registers(self, address, count):
        if self.client is None:
            raise RuntimeError("Modbus client not connected")

        start = monotonic()

        try:
            try:
                res = self.client.read_input_registers(address=address, count=count, unit=self.slave_id)
            except TypeError:
                res = self.client.read_input_registers(address=address, count=count, slave=self.slave_id)

            elapsed = (monotonic() - start) * 1000

            if hasattr(res, "isError") and res.isError():
                raise RuntimeError(f"Modbus error at 0x{address:04X}: {res}")

            if not hasattr(res, "registers"):
                raise RuntimeError(f"No registers returned at 0x{address:04X}: {res}")

            if len(res.registers) != count:
                raise RuntimeError(f"Expected {count} registers at 0x{address:04X}, got {len(res.registers)}")

            logging.debug("Read 0x%04X count=%s in %.1fms", address, count, elapsed)
            return res.registers

        except Exception:
            logging.exception("Modbus read failed addr=0x%04X count=%s", address, count)
            raise

    def poll(self):
        if self.client is None:
            if not self.connect():
                return False

        try:
            self._poll_count += 1

            live = self.read_input_registers(0x0000, 80)

            def f(addr):
                return decode_float(live, addr)

            l1_v = f(0x0000)
            l2_v = f(0x0002)
            l3_v = f(0x0004)

            l1_a = f(0x0006)
            l2_a = f(0x0008)
            l3_a = f(0x000A)

            l1_w = f(0x000C)
            l2_w = f(0x000E)
            l3_w = f(0x0010)

            l1_pf = f(0x001E)
            l2_pf = f(0x0020)
            l3_pf = f(0x0022)

            total_w = f(0x0034)
            total_pf = f(0x003E)
            freq = f(0x0046)

            import_kwh = f(0x0048)
            export_kwh = f(0x004A)

            if self.invert_power:
                l1_w = -l1_w
                l2_w = -l2_w
                l3_w = -l3_w
                total_w = -total_w

            if max(abs(l1_w), abs(l2_w), abs(l3_w)) > POWER_THRESHOLD_PER_PHASE:
                raise RuntimeError(f"Power outside range: L1={l1_w} L2={l2_w} L3={l3_w}")

            data["power"] = total_w
            data["current"] = l1_a + l2_a + l3_a
            data["voltage"] = (l1_v + l2_v + l3_v) / 3.0
            data["frequency"] = freq
            data["power_factor"] = total_pf
            data["forward"] = import_kwh
            data["reverse"] = export_kwh

            data["l1_power"] = l1_w
            data["l1_current"] = l1_a
            data["l1_voltage"] = l1_v
            data["l1_frequency"] = freq
            data["l1_power_factor"] = l1_pf

            data["l2_power"] = l2_w
            data["l2_current"] = l2_a
            data["l2_voltage"] = l2_v
            data["l2_frequency"] = freq
            data["l2_power_factor"] = l2_pf

            data["l3_power"] = l3_w
            data["l3_current"] = l3_a
            data["l3_voltage"] = l3_v
            data["l3_frequency"] = freq
            data["l3_power_factor"] = l3_pf

            if self._poll_count % self.phase_energy_poll_every == 0:
                phase_energy = self.read_input_registers(0x015A, 18)

                data["l1_forward"] = decode_float(phase_energy, 0x015A - 0x015A)
                data["l2_forward"] = decode_float(phase_energy, 0x015C - 0x015A)
                data["l3_forward"] = decode_float(phase_energy, 0x015E - 0x015A)

                data["l1_reverse"] = decode_float(phase_energy, 0x0160 - 0x015A)
                data["l2_reverse"] = decode_float(phase_energy, 0x0162 - 0x015A)
                data["l3_reverse"] = decode_float(phase_energy, 0x0164 - 0x015A)

                data["l1_total"] = decode_float(phase_energy, 0x0166 - 0x015A)
                data["l2_total"] = decode_float(phase_energy, 0x0168 - 0x015A)
                data["l3_total"] = decode_float(phase_energy, 0x016A - 0x015A)

            data["connected"] = 1
            data["last_changed"] = int(time())

            logging.info(
                "SDM630 %.1fW %.2fV %.2fA %.3fHz import=%.4fkWh export=%.4fkWh",
                data["power"],
                data["voltage"],
                data["current"],
                data["frequency"],
                data["forward"],
                data["reverse"],
            )

            return True

        except Exception as e:
            logging.warning("Poll failed, reconnecting: %s", e)
            data["connected"] = 0
            self.close()
            return False


class DbusSdm630ModbusService:
    def __init__(self, servicename, deviceinstance, paths, meter, productname, customname, connection):
        self._dbusservice = VeDbusService(servicename, register=False)
        self._paths = paths
        self._meter = meter

        self._dbusservice.add_path("/Mgmt/ProcessName", __file__)
        self._dbusservice.add_path(
            "/Mgmt/ProcessVersion",
            "SDM630 Modbus V3 driver, Python " + platform.python_version(),
        )
        self._dbusservice.add_path("/Mgmt/Connection", connection)

        self._dbusservice.add_path("/DeviceInstance", deviceinstance)
        self._dbusservice.add_path("/ProductId", 0xFFFF)
        self._dbusservice.add_path("/ProductName", productname)
        self._dbusservice.add_path("/CustomName", customname)
        self._dbusservice.add_path("/FirmwareVersion", VERSION)
        self._dbusservice.add_path("/Connected", 0)
        self._dbusservice.add_path("/Latency", None)

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path,
                settings["initial"],
                gettextcallback=settings["textformat"],
                writeable=True,
                onchangecallback=self._handlechangedvalue,
            )

        self._dbusservice.register()

        GLib.timeout_add(100, self._initial_poll)
        GLib.timeout_add(1000, self._update_dbus)

    def _initial_poll(self):
        self._poll_modbus()
        return False

    def _poll_modbus(self):
        start = monotonic()

        ok = self._meter.poll()
        if ok:
            self._update_dbus(push_only=True)

        elapsed_ms = int((monotonic() - start) * 1000)
        interval_ms = self._meter.poll_interval_ms if ok else self._meter.reconnect_interval_ms
        delay = max(10, interval_ms - elapsed_ms)
        GLib.timeout_add(delay, self._poll_modbus)

        return False

    def _set(self, path, value, digits=None):
        if value is None:
            self._dbusservice[path] = None
        elif digits is None:
            self._dbusservice[path] = value
        else:
            self._dbusservice[path] = round(value, digits)

    def _update_dbus(self, push_only=False):
        now = int(time())
        age = now - data["last_changed"] if data["last_changed"] else 999999

        self._dbusservice["/Connected"] = 1 if TIMEOUT == 0 or age < TIMEOUT else 0

        if data["last_changed"] != data["last_updated"]:
            self._set("/Ac/Power", data["power"], 2)
            self._set("/Ac/Current", data["current"], 2)
            self._set("/Ac/Voltage", data["voltage"], 2)
            self._set("/Ac/Frequency", data["frequency"], 3)
            self._set("/Ac/PowerFactor", data["power_factor"], 3)
            self._set("/Ac/Energy/Forward", data["forward"], 4)
            self._set("/Ac/Energy/Reverse", data["reverse"], 4)

            for phase in ("l1", "l2", "l3"):
                prefix = phase.upper()
                self._set(f"/Ac/{prefix}/Power", data[f"{phase}_power"], 2)
                self._set(f"/Ac/{prefix}/Current", data[f"{phase}_current"], 2)
                self._set(f"/Ac/{prefix}/Voltage", data[f"{phase}_voltage"], 2)
                self._set(f"/Ac/{prefix}/Frequency", data[f"{phase}_frequency"], 3)
                self._set(f"/Ac/{prefix}/PowerFactor", data[f"{phase}_power_factor"], 3)
                self._set(f"/Ac/{prefix}/Energy/Forward", data[f"{phase}_forward"], 4)
                self._set(f"/Ac/{prefix}/Energy/Reverse", data[f"{phase}_reverse"], 4)
                self._set(f"/Ac/{prefix}/Energy/Total", data[f"{phase}_total"], 4)

            data["last_updated"] = data["last_changed"]

        if TIMEOUT != 0 and data["last_changed"] and age > TIMEOUT:
            logging.error("Driver stopped. Timeout exceeded: %s seconds", TIMEOUT)
            sys.exit(1)

        index = self._dbusservice["/UpdateIndex"] + 1
        self._dbusservice["/UpdateIndex"] = 0 if index > 255 else index

        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("External D-Bus write: %s=%s", path, value)
        return True


def main():
    from dbus.mainloop.glib import DBusGMainLoop  # pyright: ignore[reportMissingImports]

    DBusGMainLoop(set_as_default=True)

    meter = SDM630Modbus()
    meter.connect()

    device_instance = cfg_int("DEFAULT", "device_instance", 40)
    device_name = config["DEFAULT"].get("device_name", "SDM630")
    service_name = f"com.victronenergy.{device_type}.sdm630_modbus_{device_instance}"

    DbusSdm630ModbusService(
        servicename=service_name,
        deviceinstance=device_instance,
        paths=build_dbus_paths(),
        meter=meter,
        productname=f"SDM630 Modbus V3 {device_type_name}",
        customname=device_name,
        connection=f"SDM630 Modbus RTU on {config['MODBUS'].get('port', '/dev/ttyUSB1')}",
    )

    logging.info("Started D-Bus service: %s", service_name)

    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
