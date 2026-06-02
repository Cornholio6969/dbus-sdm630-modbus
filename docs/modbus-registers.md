# SDM630 Registers Used

The driver reads SDM630 input registers as big-endian 32-bit floats.

## Live Values

Base read: address `0x0000`, count `80`.

| Register | Value |
| --- | --- |
| `0x0000` | L1 voltage |
| `0x0002` | L2 voltage |
| `0x0004` | L3 voltage |
| `0x0006` | L1 current |
| `0x0008` | L2 current |
| `0x000A` | L3 current |
| `0x000C` | L1 power |
| `0x000E` | L2 power |
| `0x0010` | L3 power |
| `0x001E` | L1 power factor |
| `0x0020` | L2 power factor |
| `0x0022` | L3 power factor |
| `0x0034` | Total power |
| `0x003E` | Total power factor |
| `0x0046` | Frequency |
| `0x0048` | Import kWh |
| `0x004A` | Export kWh |

## Per-Phase Energy

Base read: address `0x015A`, count `18`.

| Register | Value |
| --- | --- |
| `0x015A` | L1 import kWh |
| `0x015C` | L2 import kWh |
| `0x015E` | L3 import kWh |
| `0x0160` | L1 export kWh |
| `0x0162` | L2 export kWh |
| `0x0164` | L3 export kWh |
| `0x0166` | L1 total kWh |
| `0x0168` | L2 total kWh |
| `0x016A` | L3 total kWh |
