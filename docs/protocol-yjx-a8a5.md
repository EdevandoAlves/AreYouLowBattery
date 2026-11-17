# YJX-CHIP 2.4 GHz receiver battery protocol (`a8a5:2255`)

Reverse-engineering notes for the vendor battery telemetry of YJX-CHIP
("a8a5") 2.4 GHz receivers, as used by the Smailwolf RS7, EWEADN G5 and
MCHOSE G7 wireless mice (the receiver VID:PID is shared between brands).

Evidence: live hidraw capture and a single documented status-read probe on a
Smailwolf RS7 receiver (2026-11-17, Linux 7.2.15, `captures/capture_a8a5_2255_*.jsonl`
and `captures/probe_a8a5_2255_*.jsonl`), cross-checked against two independent
open source implementations (see References). DPI, polling rate, button mapping
and firmware were never read or written during this work.

## Interface layout

| USB interface | hidraw | Collection | Role |
|---|---|---|---|
| 0 | hidraw0 | mouse (report `0x02`) + vendor `0xFFA5:0x88` (1-byte input report `0x09`) | motion; kernel maps the mouse report on data-capable links |
| 1 | hidraw1 | keyboard/consumer + vendor `0xFF05:0x02` (report `0x0a`, 63 B in) and `0xFF06:0x02` (report `0x0b`, 63 B in/out) | keys/media; dead vendor collections observed |
| 2 | hidraw2 | vendor `0xFF01:0x10`, 64-byte input + 64-byte output, **no report IDs** | **command channel (battery, config)** |

A passive 190 s capture saw only motion reports on interface 0 and heartbeat
frames (below) on interface 2 — battery is **not** pushed proactively on this
firmware generation other than through the heartbeat.

## Command channel (interface 2)

65-byte hidraw transfers (leading `0x00` = unnumbered report, 64-byte payload):

    request   00 55 <cmd> A5 0B <param> 01 01 01 00 ...
    reply     AA <cmd> ...            (headers observed: AA 30, AA FA AE)

### Battery query (implemented by `yjx_v1`)

    write  00 55 30 a5 0b 2e 01 01 01 <56 zero bytes>
    read   aa 30 a5 0b 0a 01 01 01 3e 00 ...   ->  byte 8 = 0x3e = 62 (%),
                                                   byte 9 = 0 = not charging

Second reply layout, measured on an MCHOSE G7 (`a8a5:2255`, same chip):

    aa 30 a5 3c 0a 01 01 01 2e 01 ...   ->  46 %, byte 9 = 1 = charging

Validation rules implemented: reply must start with `AA 30`; level byte 8 is
rejected when > 100 (never clamped, never invented); a sleeping mouse answers
nothing — the handler keeps the last cached value (`Cached (...)` detail) and
returns no fabricated percentage.

### Heartbeat push (passive, ~every 67 s)

    aa fa ae 49 38 01 01 01 d0 3e ...

Observed twice during the capture. Byte 9 matched the queried battery level
(62 %) in the single simultaneous sample; treated as a secondary read-only
source, disabled by default (`enable_passive_listen: false`) until confirmed
across charge states.

## Safety notes

* Frames documented as writes for this chip (configuration
  `01 55 0f ae 0a 30 ...`, button-table reset, macro write) are **never sent**
  by the handler; the only output the protocol code produces is the battery
  query above.
* `0xA8A5` is a chip-maker vendor id shared across brands: gate any new command
  on VID **and** PID, and prefer capturing your own device before writing.

## References

* `NB-Group/g5moused` (EWEADN G5, same receiver): motion frame `0x02` on
  interface 0; command-channel frame shape and `cmd 0x48` battery variant.
* `HeyOkay/HaloBattery` `providers/mchose.py` (MCHOSE G7, same VID:PID):
  the `AA 30` battery exchange measured on hardware (issue #8), and the
  PID-gating precedent from review issue #62.
