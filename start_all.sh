#!/usr/bin/env bash
# Käynnistää Hotkey-työkalut. Toimii mistä tahansi kansiosta (myös USB:ltä).
#
#   ./start_all.sh          käynnistä
#   ./stop_all.sh           pysäytä
#
# Ympäristömuuttujat:
#   HOTKEY_LOG   logitiedoston polku (oletus /tmp/hotkey-tools.log)
#   HOTKEY_PY    python-tulkki (oletus python3)

set -u

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG="${HOTKEY_LOG:-/tmp/hotkey-tools.log}"
PY="${HOTKEY_PY:-python3}"

# Vakiintuneet taustaprosessit.
# hover_volume.py on CLI-aputyökalu (hover_volume.py up|down), ei taustaprosessi.
DAEMONS=(autoclicker.py dpiswitch.py forceclose.py)

# Lopeta vanhat instanssit mistä tahansa Hotkey-kansiosta.
# Suodatetaan /proc/<pid>/comm, jotta pgrep ei tavoita itseään.
for pid in $(pgrep -f "Hotkey/.*\.py" 2>/dev/null); do
  case "$(cat "/proc/$pid/comm" 2>/dev/null)" in
    python3*) kill "$pid" 2>/dev/null ;;
  esac
done
sleep 0.3

{
  echo "--- $(date '+%F %T') Käynnistetään ($DIR)"
  for f in "${DAEMONS[@]}"; do
    if [[ ! -f "$DIR/$f" ]]; then
      echo "PUUTTUU: $f"
      continue
    fi
    nohup "$PY" -u "$DIR/$f" >>"$LOG" 2>&1 &
    echo "käynnistetty: $f (pid $!)"
  done
} >>"$LOG" 2>&1

echo "Hotkey-työkalut käynnistetty. Logi: $LOG"