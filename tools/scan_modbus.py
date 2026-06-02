#!/usr/bin/env python3
"""Scan for SDM630 Modbus RTU slave IDs."""

import argparse

try:
    from pymodbus.client.sync import ModbusSerialClient
    PYMODBUS_MAJOR = 2
except Exception:
    from pymodbus.client import ModbusSerialClient
    PYMODBUS_MAJOR = 3


def parse_args():
    parser = argparse.ArgumentParser(description="Scan Modbus RTU slaves by reading L1 voltage.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial adapter path.")
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--parity", default="N")
    parser.add_argument("--stopbits", type=int, default=1)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--start", type=int, default=1, help="First slave ID to test.")
    parser.add_argument("--end", type=int, default=10, help="Last slave ID to test, inclusive.")
    return parser.parse_args()


def read_input_registers(client, slave_id):
    try:
        return client.read_input_registers(address=0, count=2, unit=slave_id)
    except TypeError:
        return client.read_input_registers(address=0, count=2, slave=slave_id)


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
    connected = client.connect()
    print(f"Connect {args.port}: {connected}")

    if not connected:
        raise SystemExit(1)

    try:
        for slave_id in range(args.start, args.end + 1):
            try:
                result = read_input_registers(client, slave_id)
                if hasattr(result, "isError") and not result.isError():
                    print(f"FOUND SLAVE {slave_id}: {result.registers}")
            except Exception:
                pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
