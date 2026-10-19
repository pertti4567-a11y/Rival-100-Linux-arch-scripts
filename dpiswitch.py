#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DPI-vaihto Rival 100:lle - rullalla (Wayland/Hyprland).

Käyttää rivalcfg:a (https://github.com/flozz/rivalcfg), joka asettaa OIKEAN
sensorin DPI:n SteelSeries Rival 100:lle (1038:1702) suoraan USB:n yli.

Toiminta:
    Pidä DPI-painiketta (0x115 / BTN_FORWARD) pohjassa ja pyöritä rullaa:
        - rulla ylös  => seuraava DPI-taso (250 -> 500 -> ... -> 4000)
        - rulla alas  => edellinen DPI-taso
    Jokainen vaihto näyttää ilmoituksen ja kirjoittaa /tmp/dpiswitch.log.

Rival 100:ssa on kaksi ensisäätöpaikkaa (-s ja -S), joita fyysinen DPI-nappi
vuorottelee. Skripti asettaa MOLÄMMÄT samaan arvoon, jotta DPI-napin oma
vaihto ei hyppää eri arvon.

Edellytykset (asennettu jo):
    - rivalcfg  (AUR) + udev-säännöt:  pkexec rivalcfg --update-udev
    - yleisten skriptien tapaan: python-evdev, input-ryhmä
"""

import subprocess
import threading
from evdev import InputDevice, ecodes, list_devices

# ---------------------------------------------------------------------------
# SÄÄDÄ TÄSTÄ
# ---------------------------------------------------------------------------

# Laite: "" = etsi automaattisesti nimellä MOUSE_NAME_FILTER, tai tarkka polku.
DEVICE_PATH = ""
MOUSE_NAME_FILTER = "Rival"

# DPI-painikkeen koodi (Rival 100: BTN_FORWARD = 0x115, todettu käytännössä).
# Tämä on "modifier": pidä se pohjassa ja rullaa vaihtaaksesi tasoa.
DPI_BUTTON = "BTN_FORWARD"

# DPI-tasot, jotka rulla kiertää (ylös = suurempi, alas = pienempi).
# Nämä ovat Rival 100:n aidot tuetut arvot.
DPI_LEVELS = [250, 500, 1000, 1250, 1500, 1750, 2000, 4000]

# DPI, joka palautetaan ohjelman lopussa (ja joka valitaan käynnistyksessä).
DEFAULT_DPI = 1000

# ---------------------------------------------------------------------------
# Koodi (ei tarvitse muuttaa)
# ---------------------------------------------------------------------------

REVERSE = ecodes.bytype[ecodes.EV_KEY]


def resolve_code(spec):
    if isinstance(spec, int):
        return spec
    s = str(spec).strip()
    if s.startswith("0x"):
        return int(s, 16)
    if s.isdigit():
        return int(s)
    upper = s.upper()
    for code, name in REVERSE.items():
        names = name if isinstance(name, tuple) else (name,)
        if any(n == upper for n in names):
            return code
    raise ValueError(f"Tuntematon napin tunniste: {spec}")


DPI_CODE = resolve_code(DPI_BUTTON)
ACCESS_DENIED = {"yes": False}


def find_mouse():
    if DEVICE_PATH:
        try:
            return InputDevice(DEVICE_PATH)
        except OSError:
            ACCESS_DENIED["yes"] = True
            return None
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            keys = caps.get(ecodes.EV_KEY, [])
            rel = caps.get(ecodes.EV_REL, [])
            if (ecodes.BTN_LEFT in keys and ecodes.REL_WHEEL in rel
                    and MOUSE_NAME_FILTER.lower() in dev.name.lower()):
                return dev
        except OSError:
            ACCESS_DENIED["yes"] = True
    return None


lock = threading.Lock()
level = DPI_LEVELS.index(DEFAULT_DPI) if DEFAULT_DPI in DPI_LEVELS else -1


def set_dpi(dpi):
    """Asettaa oikean DPI:n rivalcfglla (molemmat esiasetukset) + ilmoitus."""
    proc = subprocess.run(
        ["rivalcfg", "-s", str(dpi), "-S", str(dpi)],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        subprocess.run(
            ["notify-send", "-t", "1200", "-u", "low", "-a", "DPI-vaihto",
             f"DPI {dpi}", "rivalcfg asetti oikean sensorin DPI:n"],
            capture_output=True,
        )
        print(f"[dpi] asetettu: {dpi} DPI", flush=True)
    else:
        error = (proc.stderr or proc.stdout or "").strip()
        print(f"[dpi] rivalcfg VIRHE: {error}", flush=True)
        subprocess.run(
            ["notify-send", "-t", "2000", "-u", "critical", "-a", "DPI-vaihto",
             "Virhe", error[:80]],
            capture_output=True,
        )


def step(direction):
    """Siirry tasoa ylös (+1) tai alas (-1)."""
    global level
    with lock:
        n = len(DPI_LEVELS)
        level = (level + (1 if direction > 0 else -1)) % n
        dpi = DPI_LEVELS[level]
    set_dpi(dpi)


def main():
    dev = find_mouse()
    if dev is None:
        if ACCESS_DENIED["yes"]:
            print("Laite on olemassa, mutta /dev/input ei ole luettavissa.")
            print("  sudo usermod -aG input $USER   -> kirjaudu ulos ja takaisin sisään")
        else:
            print("Hiirtä ei löytynyt. Näytä polku kohdassa DEVICE_PATH:")
            for path in list_devices():
                try:
                    d = InputDevice(path)
                    print(f"  {d.path}  {d.name}")
                except OSError:
                    pass
        return

    print(f"Laite: {dev.name}  ({dev.path})")
    print(f"DPI-painike: {DPI_BUTTON} ({DPI_CODE:#x})  |  tasot: {DPI_LEVELS}")
    print("Pidä DPI-painike pohjassa + rullaa (ylös=isompi, alas=pienempi). Ctrl+C lopettaa.")

    modifier_held = False
    try:
        for ev in dev.read_loop():
            if ev.type == ecodes.EV_KEY and ev.code == DPI_CODE:
                modifier_held = ev.value >= 1  # 1=alas, 0=ylös
            elif (ev.type == ecodes.EV_REL and ev.code == ecodes.REL_WHEEL
                  and ev.value != 0 and modifier_held):
                step(ev.value)
    except OSError as e:
        print(f"Virhe: {e}")
        print("Tarkista: olet ryhmässä 'input'?")
    finally:
        set_dpi(DEFAULT_DPI)


if __name__ == "__main__":
    main()