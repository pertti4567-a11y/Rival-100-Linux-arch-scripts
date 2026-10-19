#!/usr/bin/env bash
# Pysäyttää Hotkey-tyäkalut (kaikki Hotkey-kansioiden python-prosessit).

set -u

pids=""
for pid in $(pgrep -f "Hotkey/.*\.py" 2>/dev/null); do
  case "$(cat "/proc/$pid/comm" 2>/dev/null)" in
    python3*) pids="$pids $pid" ;;
  esac
done

if [[ -z "${pids// /}" ]]; then
  echo "Ei käynnissä olevia Hotkey-prosesseja."
  exit 0
fi

# dpiswitch.py palauttaa oman finally-lohkonsa kautta DPI:n oletusarvoon.
echo "Pysäytetään:$pids"
kill $pids 2>/dev/null

for _ in 1 2 3 4 5 6 7 8 9 10; do
  alive=""
  for pid in $pids; do
    [[ -d "/proc/$pid" ]] && alive="$alive $pid"
  done
  [[ -z "${alive// /}" ]] && break
  sleep 0.2
done

for pid in $pids; do
  [[ -d "/proc/$pid" ]] && kill -9 "$pid" 2>/dev/null
done

echo "Pysäytetty."