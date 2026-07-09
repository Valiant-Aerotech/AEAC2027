# Vivi — Pi to Kakute H7 wiring

Physical UART connection between the **Raspberry Pi companion** and **Holybro Kakute H7** (ArduPilot). Props off and FC unpowered while soldering.

**Related docs:**

- [mission-planner/001-kakute-h7.md](mission-planner/001-kakute-h7.md) — FC parameters (SERIAL, GUIDED, gimbal)
- [../vion/mission-planner/002-pi-telem-params.md](../vion/mission-planner/002-pi-telem-params.md) — `SERIALx_PROTOCOL` / `BAUD`
- [../../docs/runbooks/pi-fresh-install.md](../../docs/runbooks/pi-fresh-install.md) — full Pi OS setup
- [../../docs/runbooks/vivi-outdoor-field-day.md](../../docs/runbooks/vivi-outdoor-field-day.md) — field flight day

---

## Dual MAVLink links (critical)

Use **two separate** physical paths. Never put the GCS telemetry radio and the Pi on the same FC serial port.

| Link | Physical | Software |
|------|----------|----------|
| **GCS** | USB or TELEM radio → laptop | Mission Planner @ 57600 (`config/rpas.yaml` COM port) |
| **Pi companion** | Pi GPIO UART → dedicated FC UART | `/dev/ttyAMA0` @ 57600 (`config/vion.yaml` `mavlink.rpi_connection`) |
| **Monitor (optional)** | Pi WiFi → laptop UDP | `python tools\valiant.py gcs monitor` |

---

## Pi 40-pin header → Kakute UART

Both sides use **3.3 V TTL**. Do **not** connect Pi 5 V (pins 2/4) to the FC UART.

| Pi pin | Pi signal | Connect to FC | Notes |
|--------|-----------|---------------|-------|
| **8** | GPIO14 / TXD | **RX** on chosen UART | Pi TX → FC RX |
| **10** | GPIO15 / RXD | **TX** on chosen UART | FC TX → Pi RX |
| **6** | GND | **GND** | Common ground required |

**Always cross TX and RX:** Pi transmit goes to FC receive, and vice versa.

```text
  Raspberry Pi                    Kakute H7 (one UART)
  Pin 8  TX  ------------------>  RX
  Pin 10 RX  <------------------  TX
  Pin 6  GND -------------------  GND
```

---

## Which Kakute UART to use

The Kakute H7 has multiple UART pads/connectors (e.g. UART1–UART6 depending on board revision). Pick **one spare port** that is **not** used by:

- GCS telemetry radio
- GPS (HERE4)
- RC receiver (if on a UART)

Common approach: solder to **RX/TX/GND pads** for an unused UART (check your board silkscreen or Holybro pinout for your revision), or use a 4-pin TELEM/GPS connector only if that port is free.

After wiring and power-on:

1. Connect Mission Planner via **GCS radio only**
2. Power Pi and FC
3. In Mission Planner → **Status** or MAVLink inspector, identify which `SERIALx` port receives traffic from the Pi
4. Set on **that port only**:
   - `SERIALx_PROTOCOL = 2` (MAVLink2)
   - `SERIALx_BAUD = 57` (57600)
5. **Write params** → reboot FC

Details: [001-kakute-h7.md](mission-planner/001-kakute-h7.md)

---

## Pi OS UART enable

On the Pi (once per SD card):

```bash
sudo raspi-config
```

→ Interface Options → Serial Port → login shell **No**, hardware **Yes** → reboot.

Verify:

```bash
grep enable_uart /boot/firmware/config.txt   # or /boot/config.txt
# expect: enable_uart=1

sudo usermod -aG dialout $USER   # then log out and SSH back in
ls -l /dev/ttyAMA0
```

---

## Bench verification (props off)

**Pi:**

```bash
cd ~/AEAC2027
bash hardware/vion/rpi/pi_field_ready.sh --check
```

Expect: `[OK] RGB frame`, `[OK] MAVLink heartbeat`, safety.lua OK.

**Laptop:**

```powershell
python tools\valiant.py gcs verify-safety
```

### MAVLink troubleshooting

| Symptom | Check |
|---------|--------|
| No heartbeat on Pi | TX/RX swapped? GND connected? `enable_uart=1`? User in `dialout`? |
| Heartbeat on wrong port in MP | Pi wired to same port as GCS radio — move to separate UART |
| Garbled / no data | Baud mismatch — FC must be 57600 (`SERIALx_BAUD=57`) |
| Permission denied | `sudo usermod -aG dialout $USER`, re-login |

---

## Power and safety

- Share a common ground between Pi, FC, and battery ground (via FC power wiring as designed)
- Do not power the Pi UART pins above 3.3 V
- Complete wiring with **props removed**; verify bench checks before first armed flight
- Load [`../vion/lua/safety.lua`](../vion/lua/safety.lua) and run `gcs verify-safety` before props-on flight
