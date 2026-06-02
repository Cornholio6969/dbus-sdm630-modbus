#!/usr/bin/env python3

import argparse
import struct
import subprocess
import time

try:
    from pymodbus.client.sync import ModbusSerialClient
    PYMODBUS_MAJOR = 2
except Exception:
    from pymodbus.client import ModbusSerialClient
    PYMODBUS_MAJOR = 3


def parse_args():
    parser = argparse.ArgumentParser(description="Read SDM630 L1 voltage over Modbus RTU.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial adapter path.")
    parser.add_argument("--slave-id", type=int, default=1)
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--parity", default="N")
    parser.add_argument("--stopbits", type=int, default=1)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--watch-port", action="store_true", help="Show processes using the port after an error.")
    return parser.parse_args()


def monitor_port(port, duration=5):
    print(f"\nWatching {port} for {duration} seconds...\n")

    end = time.time() + duration
    seen = set()

    while time.time() < end:
        try:
            result = subprocess.run(
                ["fuser", port],
                capture_output=True,
                text=True,
                check=False,
            )

            pids = result.stdout.strip().split()

            for pid in pids:
                if pid in seen:
                    continue

                seen.add(pid)

                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmdline = (
                            f.read()
                            .replace(b"\x00", b" ")
                            .decode(errors="ignore")
                            .strip()
                        )

                    print(f"PID {pid}: {cmdline}")

                except Exception as e:
                    print(f"PID {pid}: <failed to read cmdline> ({e})")

        except Exception as e:
            print("Error checking port users:", e)

        time.sleep(0.05)

    if not seen:
        print("No processes detected using the port.")


def read_l1_voltage(client, slave_id):
    try:
        result = client.read_input_registers(address=0, count=2, unit=slave_id)
    except TypeError:
        result = client.read_input_registers(address=0, count=2, slave=slave_id)

    print("Raw response:", result)

    if result.isError():
        raise RuntimeError(f"Modbus error: {result}")

    print("Registers:", result.registers)
    return struct.unpack(">f", struct.pack(">HH", result.registers[0], result.registers[1]))[0]


def main():
    args = parse_args()
    kwargs = {
        "port": args.port,
        "baudrate": args.baudrate,
        "parity": args.parity,
        "stopbits": args.stopbits,
        "bytesize": args.bytesize,
        "timeout": args.timeout,
    }

    if PYMODBUS_MAJOR == 2:
        kwargs["method"] = "rtu"

    client = ModbusSerialClient(**kwargs)
    print(f"Connecting to {args.port}...")

    if not client.connect():
        print("FAILED TO CONNECT")
        raise SystemExit(1)

    try:
        print("Connected")
        print("Reading L1 Voltage (0x0000)...")
        voltage = read_l1_voltage(client, args.slave_id)
        print()
        print("SUCCESS")
        print(f"L1 Voltage = {voltage:.2f} V")
    except Exception as err:
        print("\nEXCEPTION:", err)
        if args.watch_port:
            monitor_port(args.port)
        raise
    finally:
        client.close()
        print("Disconnected")


if __name__ == "__main__":
    main()
