#!/usr/bin/env bash
#
# Hotkey-työkalut: asennus.
#
#   ./install.sh                 asenna oletuksilla
#   DEST=~/Hotkey ./install.sh   asenna toiseen kansioon
#   AUTOSTART=0 ./install.sh     älä asenna automaattista käynnistystä
#
# Asentaa: riippuvuudet, input-ryhmän, udev-säännön /dev/uinput:lle,
# skriptit kotikansioon ja systemd-käyttäjäpalvelun (automaattinen käynnistys).
# Omarchyssa vapauttaa lisäksi SUPER + rulla -oletuksen hover_volume.py:lle.

set -u

SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${DEST:-$HOME/Documents/Hotkey}"
AUTOSTART="${AUTOSTART:-1}"
UNIT="$HOME/.config/systemd/user/hotkey-tools.service"
SUDO=""
[[ "$(id -u)" -ne 0 ]] && SUDO="sudo"

step() { printf '\n== %s ==\n' "$1"; }

step "1/5 Riippuvuudet (python, python-evdev)"
# Jos python3 puuttuu kokonaan (esim. tuore asennus), asennetaan se ensin.
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 puuttuu -> asennetaan."
  if command -v pacman >/dev/null; then
    $SUDO pacman -S --needed --noconfirm python
  else
    echo "VIRHE: python3 puuttuu eikä pacman ole käytettävissä."
    echo "      Asenna python3 paketinhallinnasta ja aja skripti uudelleen."
  fi
fi

if command -v python3 >/dev/null 2>&1 && python3 -c "import evdev" 2>/dev/null; then
  echo "python-evdev on jo asennettu."
elif command -v pacman >/dev/null; then
  $SUDO pacman -S --needed --noconfirm python-evdev
else
  echo "VIRHE: python-evdev puuttuu eikä pacman ole käytettävissä."
  echo "      Asenna se paketinhallinnasta ja aja skripti uudelleen."
fi

# rivalcfg tarvitaan vain dpiswitch.py:tä varten (DPI:n asetus hiireen).
if ! command -v rivalcfg >/dev/null; then
  echo "rivalcfg puuttuu -> asennetaan."
  if pacman -Si rivalcfg >/dev/null 2>&1; then
    $SUDO pacman -S --needed --noconfirm rivalcfg
  elif command -v yay >/dev/null; then
    yay -S --needed --noconfirm rivalcfg
  elif command -v paru >/dev/null; then
    paru -S --needed --noconfirm rivalcfg
  else
    echo "VIRHE: rivalcfg ei ole repoissa eikä AUR-avustajaa (yay/paru) löydy."
    echo "      Asenna se käsin: yay -S rivalcfg"
  fi
fi

if command -v rivalcfg >/dev/null; then
  echo "rivalcfg löytyi."
  $SUDO rivalcfg --update-udev >/dev/null 2>&1 \
    && echo "rivalcfg-udev päivitetty." \
    || echo "HUOM: rivalcfg --update-udev epäonnistui (DPI-vaihto ei ehkä toimi)."
else
  echo "HUOM: rivalcfg puuttuu -> dpiswitch.py ei voi asettaa DPI:tä."
  echo "      Asenna: yay -S rivalcfg"
fi

step "2/5 Käyttäjä input-ryhmään (lukee /dev/input ja kirjoittaa /dev/uinput)"
if getent group input | grep -qE "(^|,)$USER(,|$)"; then
  echo "$USER on jo input-ryhmässä."
else
  $SUDO usermod -aG input "$USER"
  echo "Lisätty. Ryhmä tulee voimaan vasta kirjautumisen jälkeen (ks. README)."
fi

step "3/5 udev-sääntö /dev/uinput:lle"
if [[ -f "$SRC/udev/99-uinput.rules" ]]; then
  $SUDO install -m 644 "$SRC/udev/99-uinput.rules" /etc/udev/rules.d/99-uinput.rules
  $SUDO udevadm control --reload-rules
  $SUDO udevadm trigger --subsystem-match=input
  echo "Asennettu: /etc/udev/rules.d/99-uinput.rules"
else
  echo "VIRHE: $SRC/udev/99-uinput.rules puuttuu."
fi

step "4/5 Skriptit -> $DEST"
mkdir -p "$DEST"
install -m 755 "$SRC"/*.py "$DEST"/ 2>/dev/null
install -m 755 "$SRC"/start_all.sh "$SRC"/stop_all.sh "$DEST"/ 2>/dev/null
install -m 644 "$SRC"/README.md "$DEST"/ 2>/dev/null
rm -rf "$DEST/__pycache__"
# USB/exFAT ei säilytä suoritusbittejä, joten varmistetaan.
chmod 755 "$DEST"/*.py "$DEST"/*.sh 2>/dev/null
ls -1 "$DEST"

# Varmista, että asennuslähteellä (esim. USB, Ohjelmat/Hotkey) on kaikki
# oikeat .py-tiedostot. Jos jokin puuttuu, kopioidaan se takaisin samaan
# paikkaan asennettujen tiedostojen joukosta.
if [[ "$SRC" != "$DEST" ]]; then
  for f in "$DEST"/*.py; do
    [[ -f "$f" ]] || continue
    b="$(basename "$f")"
    if [[ ! -f "$SRC/$b" ]]; then
      install -m 755 "$f" "$SRC/$b" && echo "kopioitu asennuslähteelle: $b"
    fi
  done
fi

step "5/6 Omarchy: SUPER + rulla -> hover_volume.py"
BINDINGS="$HOME/.config/hypr/bindings.lua"
if [[ -d /usr/share/omarchy ]] || command -v omarchy >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/hypr"
  touch "$BINDINGS"
  # Poista edellinen hallittu lohko, jotta DEST voidaan päivittää.
  if grep -qF -- '-- >>> hotkey-tools' "$BINDINGS"; then
    tmp="$(mktemp)"
    awk '
      /^-- >>> hotkey-tools/ { skip = 1; next }
      /^-- <<< hotkey-tools/ { skip = 0; next }
      !skip { print }
    ' "$BINDINGS" > "$tmp"
    mv "$tmp" "$BINDINGS"
  fi
  {
    echo ""
    echo "-- >>> hotkey-tools (hover_volume.py: SUPER + rulla)"
    echo 'hl.unbind("SUPER + mouse_down")'
    echo 'hl.unbind("SUPER + mouse_up")'
    printf 'o.bind("SUPER + mouse_up", "Window volume up", "%s/hover_volume.py up")\n' "$DEST"
    printf 'o.bind("SUPER + mouse_down", "Window volume down", "%s/hover_volume.py down")\n' "$DEST"
    echo "-- <<< hotkey-tools"
  } >> "$BINDINGS"
  echo "SUPER + rulla -> $DEST/hover_volume.py (Omarchy-oletus poistettu)."
  if command -v hyprctl >/dev/null 2>&1 \
     && [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    hyprctl reload >/dev/null 2>&1
    hyprctl configerrors 2>/dev/null | head -5
  fi
else
  echo "Ei Omarchy-asennusta -> SUPER + rulla -oletusta ei kosketa."
fi

if [[ "$AUTOSTART" == "1" ]]; then
  step "6/6 Automaattinen käynnistys (systemd --user)"
  mkdir -p "$HOME/.config/systemd/user"
  sed "s|@@DEST@@|$DEST|g" "$SRC/hotkey-tools.service.in" > "$UNIT"
  systemctl --user daemon-reload
  systemctl --user enable hotkey-tools.service
  systemctl --user restart hotkey-tools.service
  systemctl --user --no-pager status hotkey-tools.service | head -5
  cat <<EOF

HUOM: jos ~/.config/hypr/autostart.lua käynnistää samat skriptit, kommentoi ne
siitä pois, ettei kahta instanssia ole rinnakkain:

    o.launch_on_start("python3 -u $DEST/dpiswitch.py")     -- pois
    o.launch_on_start("python3 -u $DEST/forceclose.py")    -- pois
    o.launch_on_start("python3 -u $DEST/autoclicker.py")  -- pois

Hallinta:
    systemctl --user restart|stop|start hotkey-tools.service
    systemctl --user disable hotkey-tools.service   (poistaa automaattisen käynnistyksen)
EOF
else
  step "6/6 Automaattinen käynnistys ohitettu (AUTOSTART=0)"
fi

cat <<EOF

Valmis.

Käynnistä nyt:            $DEST/start_all.sh
Pysäytä:                  $DEST/stop_all.sh
Loki:                     /tmp/hotkey-tools.log

Nappi 6 (BTN_FORWARD) = autoclicker päälle/pois
Napit 1/2/3            = valitse autoclickattava nappi
Nappi 6 + rulla        = DPI-vaihto
Alt+F4                 = pakkosulje (dpiswitch/forceclose)
EOF