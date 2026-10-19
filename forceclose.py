#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taustakuuntelija: Alt+F4 => pakkosulje prosessi - WAYLAND/Hyprland-versio.

Miksi ei pynput?
    Sama syy kuin muissa: pynput = X11-only. Tämä lukee Fyysistä näppäimistöä
    /dev/inputista (python-evdev) ja toimii Waylandissa.

Toiminta:
    Pyörii taustalla. Kun painetaan Alt+F4:
        - TARGET_PROCESS-tila:  kill -9 prosessille (pkill -9 -f NIMI)
        - ACTIVE_WINDOW-tila:   kill -9 Hyprlandin tarkennetun ikkunan PID:lle

SÄÄDÄ TÄSTÄ:
    TARGET_PROCESS = "autoclicker.py"  # yksilöivä osa prosessin komentorivistä
    ACTIVE_WINDOW  = False             # True = sulje tarkennettu ikkuna

Valmistelut (kuten muissakin skripteissä):
    sudo pacman -S --needed python-evdev
    sudo usermod -aG input $USER          # + kirjaudu uudelleen sisään

Vinkki: jos haluat, että tavallinen ikkuna EI sulkeudu Alt+F4:llä samalla,
poista/ohita Hyprlandin oma Alt+F4-sidonta (hyprctl binds | grep -i f4).
"""

import subprocess
import threading
from evdev import InputDevice, ecodes, list_devices

# ---------------------------------------------------------------------------
# SÄÄDÄ TÄSTÄ
# ---------------------------------------------------------------------------

# Prosessi, joka suljetaan (pkill -9 -f etsii komentorivistä).
# Käytössä vain jos ACTIVE_WINDOW = False. Tarkista osumat:  pgrep -laf autoclicker.py
TARGET_PROCESS = "autoclicker.py"   # <-- vaihda tarvittaessa

# True = sulje aktiivinen ikkuna (sen PID) Hyprlandissa Alt+F4:llä.
# Oletus True: näin Alt+F4 ei vahingossa tapa autoclickeriä/palveluita.
ACTIVE_WINDOW = True

# Näppäimistön nimikiller: "" = etsi automaattisesti, tai polku
# (tämä kone: "AT Translated Set 2 keyboard" = event3).
KEYBOARD_NAME_FILTER = "keyboard"

# ---------------------------------------------------------------------------
# Koodi (ei tarvitse muuttaa)
# ---------------------------------------------------------------------------

pressed = set()          # parhaillaan alas painetut koodit (jaettu säikeille)
pressed_lock = threading.Lock()

ALT_KEYS = {ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT}


def force_close():
    if ACTIVE_WINDOW:
        try:
            import json
            raw = subprocess.run(
                ["hyprctl", "-j", "activewindow"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            pid = int(json.loads(raw).get("pid") or 0)
            if pid:
                subprocess.run(["kill", "-9", str(pid)], check=True)
                print(f"[forceclose] Suljettu aktiivinen ikkuna, pid={pid}", flush=True)
                subprocess.run(["notify-send", "-t", "1500", "-u", "low",
                                "Alt+F4", f"Pakko suljettu ikkuna (pid {pid})"],
                               capture_output=True)
            else:
                print("[forceclose] Ei aktiivista ikkunaa (pid puuttuu)", flush=True)
        except Exception as e:
            print(f"[forceclose] Virhe: {e}", flush=True)
    else:
        subprocess.run(["pkill", "-9", "-f", TARGET_PROCESS])
        print(f"[forceclose] Pakkosuljettu prosessi: {TARGET_PROCESS}", flush=True)
        subprocess.run(["notify-send", "-t", "1500", "-u", "low",
                        "Alt+F4", f"Pakko suljettu {TARGET_PROCESS}"],
                       capture_output=True)


def reader(dev):
    """Lukee yhtä näppäimistölaitetta ja etsii Alt+F4:ää."""
    try:
        for ev in dev.read_loop():
            if ev.type != ecodes.EV_KEY:
                continue
            with pressed_lock:
                if ev.value >= 1:
                    pressed.add(ev.code)
                else:
                    pressed.discard(ev.code)
                alt = pressed & ALT_KEYS
                f4 = ev.code == ecodes.KEY_F4 and ev.value >= 1
            if f4 and alt:
                force_close()
    except OSError as e:
        print(f"[forceclose] {dev.path}: {e} (olet ryhmässä 'input'?)")


ACCESS_DENIED = {"yes": False}


def find_keyboards():
    devs = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            keys = caps.get(ecodes.EV_KEY, [])
            if ecodes.KEY_F4 in keys and not dev.name.lower().startswith("rival"):
                if not KEYBOARD_NAME_FILTER or KEYBOARD_NAME_FILTER.lower() in dev.name.lower():
                    devs.append(dev)
        except OSError:
            ACCESS_DENIED["yes"] = True
    return devs


def main():
    devs = find_keyboards()
    if not devs:
        if ACCESS_DENIED["yes"]:
            print("Näppäimistö on olemassa, mutta /dev/input ei ole luettavissa.")
            print("  sudo usermod -aG input $USER")
            print("  -> kirjaudu ulos ja takaisin sisään (ryhmä astuu voimaan vasta sitten)")
            print("  Väliaikainen testi root-syttä:  sudo python3 ~/Documents/Hotkey/forceclose.py")
        else:
            print("Näppäimistöä ei löytynyt. Näytä polku kohtaan KEYBOARD_NAME_FILTER.")
        return
    mode = "AKTIIVISEN IKKUNAN sulku" if ACTIVE_WINDOW else f"prosessin '{TARGET_PROCESS}' sulku"
    print(f"[forceclose] Alt+F4 => {mode}. Ctrl+C lopettaa.")
    threads = [threading.Thread(target=reader, args=(d,), daemon=True) for d in devs]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nLopetettu.")


if __name__ == "__main__":
    main()