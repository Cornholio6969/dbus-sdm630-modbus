# Contributing

Thanks for improving this driver.

## Local Checks

Run the syntax check before opening a pull request:

```sh
python3 -m py_compile dbus-sdm630-modbus.py tools/scan_modbus.py tools/read_l1_voltage.py
sh -n install.sh uninstall.sh restart.sh service/run service/log/run
```

When changing Modbus register handling, test on real hardware and include:

- SDM630 model/version.
- Venus OS version.
- pymodbus version, if known.
- Serial adapter path and meter communication settings.

## Configuration

Do not commit `config.ini`; it contains local serial settings. Update `config.sample.ini` and the README when adding or changing configuration options.
