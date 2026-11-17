# Contributing to AreYouLowBattery

Thank you for helping improve **AreYouLowBattery**! To keep users' hardware, OS security, and competitive gaming latency safe, all Pull Requests must follow these guidelines.

## 🛡️ Security & Hardware Safety Rules

1. **Target the `main` branch via Pull Request** — Work in a short-lived feature/fix branch (`feat/...`, `fix/...`, `docs/...`) or fork and open a PR targeting `main`. Direct pushes to `main` are disabled; releases are triggered explicitly via `v*` version tags.
2. **Protocol Handlers (`areyoulowbattery/handlers/`)**:
   - **Battery telemetry only:** Handlers may only send documented, hardware-confirmed battery status query frames. Never send DPI, lighting, macro, button-remapping, reset, or firmware-update frames.
   - **Never fabricate values:** Reject out-of-range percentages (`> 100` or `< 0`). If a device is asleep or silent, return cached data (with `"Cached (...)"` details) or `None`.
   - **No network or subprocess calls** inside protocol handlers.
   - **Handle OS errors gracefully:** Wrap transport reads/writes cleanly so a locked Windows HID collection never crashes the polling loop.
3. **udev Rules (`rules/99-areyoulowbattery.rules`)**:
   - Always scope rules to a specific `ATTRS{idVendor}=="..."`.
   - Always use `MODE="0660", TAG+="uaccess"` (world-writable `MODE="0666"` is strictly forbidden).
4. **No `shell=True`**: Never use `shell=True` in `subprocess` calls or pass interpolated strings to `pkexec`.

## 🧪 Testing Requirements

Before opening a PR, verify locally:

```bash
# Run full unit test suite
python3 -m unittest discover -s tests -v

# Run fault-injection chaos simulator across all protocol handlers
python3 tools/sim_lab.py --chaos

# If you changed UI code, regenerate and inspect offscreen screenshots
python3 tools/visual_audit.py
```

New protocol handlers must include:
- Unit tests using `FakeTransport` with real captured byte frames.
- A matching YAML profile in `profiles/` and an entry in `VENDOR_PROTOCOL_MAP` / `PROTOCOL_LABELS`.
- Brief protocol documentation in `docs/` (byte layout + evidence).
