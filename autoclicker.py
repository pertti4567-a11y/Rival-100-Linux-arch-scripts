#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import threading
import time
from evdev import InputDevice, UInput, ecodes, list_devices

DEVICE_PATH = ""
MOUSE_NAME_FILTER = "Rival"

# Nappi 6 = BTN_FORWARD (0x115) Rival 100:ssa, eli sama fyysinen nappi jota
# dpiswitch.py käyttää DPI-nappina. Numerointi:
#   0x110 BTN_LEFT (1) | 0x111 BTN_RIGHT (2) | 0x112 BTN_MIDDLE (3)
#   0x113 BTN_SIDE (4) | 0x114 BTN_EXTRA (5) | 0x115 BTN_FORWARD (6)
# Tätä painetaan kerran = kytkee autoclickerin päälle/pois (toggle).
MODIFIER = "BTN_FORWARD"

# Oma uinput-hiiri täyttäisi myös MOUSE_NAME_FILTER-säännön, joten se ohitetaan.
VIRTUAL_NAME_FILTER = "autoclicker-virtual"

CPS = 25
INTERVAL = 1.0 / CPS
HOLD = 0.02

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


def btn_name(code):
    name = REVERSE.get(code)
    if isinstance(name, tuple):
        return name[0]
    return str(name or hex(code))


MODIFIER_CODE = resolve_code(MODIFIER)
PRIMARY = (ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE)

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
            if (
                ecodes.BTN_LEFT in keys
                and ecodes.REL_WHEEL in rel
                and MOUSE_NAME_FILTER.lower() in dev.name.lower()
                and VIRTUAL_NAME_FILTER.lower() not in dev.name.lower()
            ):
                return dev
        except OSError:
            ACCESS_DENIED["yes"] = True
    return None


UI = {"dev": None}


def create_injector():
    try:
        return UInput(
            events={
                ecodes.EV_KEY: [
                    ecodes.BTN_LEFT,
                    ecodes.BTN_RIGHT,
                    ecodes.BTN_MIDDLE,
                    ecodes.BTN_SIDE,
                    ecodes.BTN_EXTRA,
                    ecodes.BTN_FORWARD,
                ],
                ecodes.EV_REL: [
                    ecodes.REL_X,
                    ecodes.REL_Y,
                    ecodes.REL_WHEEL,
                    ecodes.REL_WHEEL_HI_RES,
                ],
                ecodes.EV_MSC: [ecodes.MSC_SCAN],
            },
            name="rival-autoclicker-virtual-mouse",
            vendor=0x1038,
            product=0x1702,
            version=0x0111,
            bustype=ecodes.BUS_USB,
            input_props=[ecodes.INPUT_PROP_POINTER],
        )
    except Exception as e:
        print(f"uinput-virhe: {e}")
        return None


def inject_click(btn):
    ui = UI["dev"]
    scan = {
        ecodes.BTN_LEFT: 0x70001,
        ecodes.BTN_RIGHT: 0x70002,
        ecodes.BTN_MIDDLE: 0x70003,
    }.get(btn, 0x70001)
    ui.write(ecodes.EV_MSC, ecodes.MSC_SCAN, scan)
    ui.write(ecodes.EV_KEY, btn, 1)
    ui.syn()
    if HOLD > 0:
        time.sleep(HOLD)
    ui.write(ecodes.EV_MSC, ecodes.MSC_SCAN, scan)
    ui.write(ecodes.EV_KEY, btn, 0)
    ui.syn()


lock = threading.Lock()
active = False
selected = {"code": ecodes.BTN_LEFT}
current_btn = {"code": ecodes.BTN_LEFT}
run_event = threading.Event()
stop_event = threading.Event()
mod_down_state = {"down": False}


def worker():
    gap = max(0.0, INTERVAL - HOLD)
    while not stop_event.is_set():
        if not run_event.is_set():
            time.sleep(0.05)
            continue
        inject_click(current_btn["code"])
        time.sleep(gap)


def notify(summary, body):
    subprocess.run(
        ["notify-send", "-t", "1200", "-u", "low", "-a", "autoclicker",
         summary, body],
        capture_output=True,
    )


def sync_run():
    if active:
        run_event.set()
    else:
        run_event.clear()


def _mod_down():
    return mod_down_state["down"]


def handle_key(code, value):
    """Toggle: BTN_FORWARD + hiiren nappi (1/2/3) kytkee autoclickin päälle/pois."""
    global active
    with lock:
        if code == MODIFIER_CODE:
            mod_down_state["down"] = (value == 1 or value == 2)
            return
        if code in PRIMARY:
            if value == 1 and mod_down_state["down"]:
                selected["code"] = code
                if active and current_btn["code"] == code:
                    active = False
                    notify("Autoclick pois", f"{btn_name(code)}")
                    sync_run()
                else:
                    active = True
                    current_btn["code"] = code
                    notify("Autoclick päälle", f"{btn_name(code)} ({CPS} CPS)")
                    sync_run()
            return


def main():
    dev = find_mouse()
    if dev is None:
        if ACCESS_DENIED["yes"]:
            print("Laite on olemassa, mutta /dev/input ei ole luettavissa.")
            print("  sudo usermod -aG input $USER   -> kirjaudu ulos ja takaisin sisään")
        else:
            print("Hiirtä ei löytynyt.")
        return

    UI["dev"] = create_injector()
    if UI["dev"] is None:
        return

    print(f"Laite: {dev.name}  ({dev.path})")
    print(f"Toggle: {MODIFIER} ({MODIFIER_CODE:#x})  |  {CPS} CPS")
    print(
        "TOGGLE: BTN_FORWARD + BTN_LEFT -> kytkee autoclick BTN_LEFT päälle/pois. "
        "Sama BTN_RIGHT/MIDDLE. Pelkkä BTN_FORWARD ei tee mitään. "
        "Ctrl+C lopettaa.",
        flush=True,
    )

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        for ev in dev.read_loop():
            if ev.type == ecodes.EV_KEY:
                handle_key(ev.code, ev.value)
    except OSError:
        pass
    finally:
        stop_event.set()
        if UI["dev"]:
            UI["dev"].close()


if __name__ == "__main__":
    main()
