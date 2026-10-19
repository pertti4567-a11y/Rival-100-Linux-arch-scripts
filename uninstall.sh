#!/usr/bin/env bash
#
# Hotkey-työkalut: poistaminen.
#
#   ./uninstall.sh              poistaa asennuksen (skriptit jätetään paikalleen)
#   PURGE=1 ./uninstall.sh      poistaa myös skriptikansion
#
# Ei koske: input-ryhmän jäsenyyttä eikä Python-paketteja (niiden poispoisto
# voi rikkoa muita asioita).

set -u

DEST="${DEST:-$HOME/Documents/Hotkey}"
PURGE="${PURGE:-0}"
SUDO=""
[[ "$(id -u)" -ne 0 ]] && SUDO="sudo"

echo "1/3 Pysäytetään työkalut"
[[ -x "$DEST/stop_all.sh" ]] && "$DEST/stop_all.sh" || true

echo "2/3 Poistetaan automaattinen käynnistys"
systemctl --user disable --now hotkey-tools.service 2>/dev/null \
  && echo "hotkey-tools.service poistettu." \
  || echo "Palvelua ei ollut käytössä."
rm -f "$HOME/.config/systemd/user/hotkey-tools.service"
systemctl --user daemon-reload 2>/dev/null

echo "3/3 Siivous"
rm -f /tmp/hotkey-tools.log /tmp/hover_volume.log /tmp/dpiswitch.log

if [[ "$PURGE" == "1" ]]; then
  rm -rf "$DEST"
  echo "Poistettu kansio: $DEST"
else
  echo "Skriptit jäivät kansioon: $DEST"
fi

cat <<EOF

Jäljelle jäi:
  - udev-sääntö /etc/udev/rules.d/99-uinput.rules
      poista:  $SUDO rm /etc/udev/rules.d/99-uinput.rules
  - input-ryhmän jäsenyys
      poista:  $SUDO gpasswd -d "$USER" input
  - itse skriptit:  rm -rf "$DEST"
EOF