## What does this PR do?
<!-- Briefly describe the fix, feature, or new peripheral protocol -->

## Hardware / Protocol Evidence (if adding a device)
- **VID:PID:** `0x____:0x____`
- **Device(s) tested:** 
- **OS tested:** <!-- Linux (distro) / Windows 10/11 -->
- **Notes / Reference:** <!-- Byte layout or docs/ link -->

## Checklist
- [ ] PR targets **`develop`** (not `main`)
- [ ] `python3 -m unittest discover -s tests -v` passes
- [ ] `python3 tools/sim_lab.py --chaos` passes with 0 failures
- [ ] New protocol writes **only** battery query frames (no DPI/config/firmware commands)
- [ ] `rules/99-areyoulowbattery.rules` (if touched) uses `ATTRS{idVendor}` + `MODE="0660", TAG+="uaccess"`
