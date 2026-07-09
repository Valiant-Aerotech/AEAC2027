#!/usr/bin/env bash
# Unified Pi companion entry: first-time setup, session checks, orbit, or mission.
#
# Usage:
#   bash hardware/vion/rpi/pi_field_ready.sh --first-time
#   bash hardware/vion/rpi/pi_field_ready.sh --check [--gcs-ip <IP>]
#   bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <IP> [--laps 1]
#   bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <IP> [--max-targets 1]
#
# Legacy wrappers first_connect.sh and session_start.sh delegate here.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

FIRST_TIME=0
DO_CHECK=0
EXPLICIT_CHECK=0
DO_ORBIT=0
DO_MISSION=0
SKIP_MAVLINK=0
SKIP_CHECK=0
GCS_IP=""
LAPS=1
MAX_TARGETS=1
DRONE="vivi"
PROFILE_ORBIT="vivi_orbit"
PROFILE_MISSION="vivi_outdoor_mission"
CONNECTION=""
CHECK_PROFILE="vivi"

usage() {
  cat <<'EOF'
Pi companion: setup, preflight check, orbit, or CV mission.

  --first-time          Once after fresh Raspberry Pi OS: apt, venv, UART/model checks
  --check               RGB + MAVLink + safety.lua preflight (default when no flight mode)
  --orbit               Run field orbit (GUIDED trigger -> laps -> LOITER)
  --mission             Run outdoor CV mission (vivi_outdoor_mission profile)

Flight options:
  --gcs-ip <IP>         Laptop IP for UDP monitor / telemetry mirror
  --laps <N>            Orbit lap count (default: 1)
  --max-targets <N>     Mission target count (default: 1)
  --drone <id>          Config id (default: vivi)
  --connection <path>   MAVLink device override (e.g. /dev/ttyAMA0)
  --skip-mavlink        Check camera only (FC powered off)
  --skip-check          Launch flight without sensor preflight (dev only)
  -h, --help            Show this help

Examples:
  bash hardware/vion/rpi/pi_field_ready.sh --first-time
  bash hardware/vion/rpi/pi_field_ready.sh --check
  bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip 192.168.1.42 --laps 1
  bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip 192.168.1.42 --max-targets 1
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --first-time) FIRST_TIME=1; shift ;;
    --check) DO_CHECK=1; EXPLICIT_CHECK=1; shift ;;
    --orbit) DO_ORBIT=1; shift ;;
    --mission) DO_MISSION=1; shift ;;
    --gcs-ip) GCS_IP="${2:?--gcs-ip requires an IP}"; shift 2 ;;
    --laps) LAPS="${2:?--laps requires a number}"; shift 2 ;;
    --max-targets) MAX_TARGETS="${2:?--max-targets requires a number}"; shift 2 ;;
    --drone) DRONE="${2:?--drone requires an id}"; shift 2 ;;
    --connection) CONNECTION="${2:?--connection requires a path}"; shift 2 ;;
    --skip-mavlink) SKIP_MAVLINK=1; shift ;;
    --skip-check) SKIP_CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ $DO_ORBIT -eq 1 && $DO_MISSION -eq 1 ]]; then
  echo "ERROR: --orbit and --mission are mutually exclusive" >&2
  exit 2
fi

FLIGHT=0
if [[ $DO_ORBIT -eq 1 || $DO_MISSION -eq 1 ]]; then
  FLIGHT=1
fi

# Decide whether to run preflight check.
if [[ $FLIGHT -eq 1 ]]; then
  if [[ $SKIP_CHECK -eq 0 ]]; then
    DO_CHECK=1
  else
    DO_CHECK=0
  fi
elif [[ $FIRST_TIME -eq 1 ]]; then
  DO_CHECK=$EXPLICIT_CHECK
elif [[ $EXPLICIT_CHECK -eq 1 ]]; then
  DO_CHECK=1
else
  # No args: session check + print ready commands.
  DO_CHECK=1
fi

check_uart_config() {
  local uart_ok=0
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -f "$cfg" ]] && grep -q "^enable_uart=1" "$cfg" 2>/dev/null; then
      uart_ok=1
      echo "  OK: enable_uart=1 in $cfg"
    fi
  done
  if [[ $uart_ok -eq 0 ]]; then
    echo "  WARN: enable_uart=1 not found."
    echo "  Run: sudo raspi-config -> Interface Options -> Serial Port -> hardware Yes, login No"
    echo "  Then reboot before MAVLink tests."
    return 1
  fi
  return 0
}

check_deploy_files() {
  local missing=0
  if [[ -f models/dry.onnx || -f models/best.onnx ]]; then
    echo "  OK: YOLO model present"
  else
    echo "  WARN: models/dry.onnx and models/best.onnx missing"
    echo "  From laptop: .\\tools\\deploy\\deploy_to_pi.ps1 -PiHost <user>@<pi-ip>"
    missing=1
  fi
  if [[ -f config/rpas_calibration.yaml || -f config/vion_calibration.yaml ]]; then
    echo "  OK: calibration yaml present"
  else
    echo "  WARN: config/rpas_calibration.yaml missing (setup may create from example)"
    missing=1
  fi
  return $missing
}

run_first_time() {
  echo "=== Pi first-time setup ==="
  echo ""

  echo "1. System packages..."
  local missing_apt=()
  for pkg in git python3-venv python3-picamera2; do
    if ! dpkg -s "$pkg" &>/dev/null; then
      missing_apt+=("$pkg")
    fi
  done
  if [[ ${#missing_apt[@]} -gt 0 ]]; then
    echo "   Installing: ${missing_apt[*]}"
    sudo apt update
    sudo apt install -y "${missing_apt[@]}"
  else
    echo "   OK: git, python3-venv, python3-picamera2"
  fi

  echo ""
  echo "2. Serial permissions (MAVLink)..."
  if groups "$USER" | grep -q '\bdialout\b'; then
    echo "   OK: $USER in dialout group"
  else
    echo "   Adding $USER to dialout (log out and SSH back in before MAVLink tests)..."
    sudo usermod -aG dialout "$USER"
  fi

  echo ""
  echo "3. Python venv and package..."
  bash "$SCRIPT_DIR/setup.sh"

  echo ""
  echo "4. UART for Pixhawk TELEM..."
  check_uart_config || true

  echo ""
  echo "5. Deploy artifacts..."
  check_deploy_files || true

  echo ""
  echo "6. MAVLink device..."
  if [[ -e /dev/ttyAMA0 ]]; then
    echo "   OK: /dev/ttyAMA0"
  elif compgen -G "/dev/ttyUSB*" >/dev/null; then
    echo "   Found USB serial (use --connection if not default):"
    ls /dev/ttyUSB* 2>/dev/null || true
  else
    echo "   WARN: no /dev/ttyAMA0 or /dev/ttyUSB* (FC off or UART not enabled?)"
  fi

  if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
    source .venv/bin/activate
    if ! python -c "import ArducamDepthCamera" 2>/dev/null; then
      echo ""
      echo "   INFO: ArducamDepthCamera not installed (optional ToF)"
      echo "   Run: bash hardware/vion/rpi/install_arducam_tof.sh"
    fi
  fi

  echo ""
  echo "First-time setup complete."
  echo "Next: deploy from laptop, configure FC in Mission Planner, then:"
  echo "  bash hardware/vion/rpi/pi_field_ready.sh --check"
  echo "  bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <LAPTOP_IP> --laps 1"
}

activate_venv() {
  if [[ ! -d .venv ]]; then
    echo "ERROR: .venv missing. Run first:" >&2
    echo "  bash hardware/vion/rpi/pi_field_ready.sh --first-time" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
}

run_check() {
  echo "=== Pi session preflight ==="
  local check_args=(--profile "$CHECK_PROFILE" --once)
  if [[ $SKIP_MAVLINK -eq 1 ]]; then
    check_args+=(--skip-mavlink)
  fi
  python hardware/vion/rpi/check_sensors.py "${check_args[@]}"
}

run_orbit() {
  echo "=== Starting field orbit (profile=$PROFILE_ORBIT, drone=$DRONE, laps=$LAPS) ==="
  local args=(--profile "$PROFILE_ORBIT" --drone "$DRONE" --laps "$LAPS")
  [[ -n "$GCS_IP" ]] && args+=(--gcs-ip "$GCS_IP")
  [[ -n "$CONNECTION" ]] && args+=(--connection "$CONNECTION")
  if [[ -z "$GCS_IP" ]]; then
    echo "WARN: --gcs-ip not set; GCS monitor will not receive UDP telemetry"
  fi
  python hardware/vion/rpi/run_field_orbit.py "${args[@]}"
}

run_mission() {
  echo "=== Starting outdoor mission (profile=$PROFILE_MISSION, drone=$DRONE) ==="
  local args=(--profile "$PROFILE_MISSION" --drone "$DRONE" --max-targets "$MAX_TARGETS")
  [[ -n "$GCS_IP" ]] && args+=(--gcs-ip "$GCS_IP")
  [[ -n "$CONNECTION" ]] && args+=(--connection "$CONNECTION")
  if [[ -z "$GCS_IP" ]]; then
    echo "WARN: --gcs-ip not set; GCS monitor will not receive UDP telemetry"
  fi
  python hardware/vion/rpi/run_mission.py "${args[@]}"
}

print_ready() {
  cat <<EOF

Pi companion checks passed.

Field commands (start BEFORE arming):
  bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <LAPTOP_IP> --laps 1
  bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <LAPTOP_IP> --max-targets 1

Laptop (separate terminal):
  python tools/valiant.py gcs monitor
  python tools/valiant.py gcs verify-safety

Guide: docs/runbooks/pi-fresh-install.md
EOF
}

# --- main ---

if [[ $FIRST_TIME -eq 1 ]]; then
  run_first_time
fi

if [[ $DO_CHECK -eq 1 || $DO_ORBIT -eq 1 || $DO_MISSION -eq 1 ]]; then
  activate_venv
fi

if [[ $DO_CHECK -eq 1 && $SKIP_CHECK -eq 0 ]]; then
  run_check
fi

if [[ $DO_ORBIT -eq 1 ]]; then
  run_orbit
elif [[ $DO_MISSION -eq 1 ]]; then
  run_mission
elif [[ $FIRST_TIME -eq 0 && $DO_CHECK -eq 1 ]]; then
  print_ready
fi
