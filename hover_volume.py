#!/usr/bin/env python3
"""hover_volume.py - adjust the volume of only the audio stream that belongs to
the window currently under the mouse cursor. Global system volume is never
touched.

    hover_volume.py up      # +10%
    hover_volume.py down    # -10%

Override the step with HOVER_VOLUME_STEP, e.g. HOVER_VOLUME_STEP=2.

Requires: hyprctl, pactl, ps (standard on Omarchy).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

STEP = os.environ.get("HOVER_VOLUME_STEP", "10")
DEBUG_LOG = os.environ.get("HOVER_VOLUME_DEBUG_LOG", "/tmp/hover_volume.log")


def debug_log(msg):
    if not os.environ.get("HOVER_VOLUME_DEBUG"):
        return
    with open(DEBUG_LOG, "a") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%H:%M:%S.%f")[:-3], msg))


def run(cmd):
    """Run cmd, return stdout ('' on any failure)."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        ).stdout
    except Exception:
        return ""


def run_ok(cmd):
    """Run cmd, return True iff exit status is 0."""
    try:
        return subprocess.run(
            cmd, capture_output=True, timeout=10
        ).returncode == 0
    except Exception:
        return False


def osd(icon, caption, value):
    """App name rides in the OSD `caption` field (line above the bar)."""
    if shutil.which("omarchy-shell") is None:
        return
    payload = json.dumps({
        "icon": icon, "message": "", "caption": caption,
        "value": str(value), "progressText": "%s%%" % value,
        "max": "100", "duration": "",
    })
    run(["omarchy-shell", "-q", "osd", "show", payload])


def fail(msg):
    if shutil.which("omarchy-osd") is not None:
        run(["omarchy-osd", "-i", "volume-muted", "-m", msg])
    sys.exit(1)


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\.(exe|x86_64|x86-64|bin|appimage)$", "", s)
    return re.sub(r"-bin$", "", s)


def inside(hay, tok):
    return len(tok) > 1 and tok in hay


def subtree_pids(root):
    """Whole process subtree of root (children, grandchildren, ...)."""
    parent = {}
    for line in run(["ps", "-eo", "pid=,ppid="]).splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            parent[int(parts[0])] = parts[1]
    keep = {root}
    changed = True
    while changed:
        changed = False
        for child, ppid in parent.items():
            if child not in keep and ppid.isdigit() and int(ppid) in keep:
                keep.add(child)
                changed = True
    return sorted(keep)


def main(arg):
    if arg == "up":
        delta = "+%s%%" % STEP
    elif arg == "down":
        delta = "-%s%%" % STEP
    else:
        print("Usage: %s <up|down>" % os.path.basename(sys.argv[0]),
              file=sys.stderr)
        return 1

    # --- 1. Where is the pointer? -------------------------------------------
    # Global layout space; negatives are valid (monitor left of / above 0,0).
    # Fractional values (HiDPI scaling) are truncated like the old bash did.
    try:
        pos = json.loads(run(["hyprctl", "-j", "cursorpos"]) or "{}")
        cx, cy = int(float(pos["x"])), int(float(pos["y"]))
    except Exception:
        return 0  # no cursor info (e.g. no compositor) -> stay silent
    debug_log("cursor %d,%d" % (cx, cy))

    # --- 2. Which monitor is the pointer on? --------------------------------
    monitor_id = None
    try:
        for m in json.loads(run(["hyprctl", "-j", "monitors"]) or "[]"):
            if (cx >= m["x"] and cx < m["x"] + m["width"]
                    and cy >= m["y"] and cy < m["y"] + m["height"]):
                monitor_id = m["id"]
                name = m.get("name", "?")
                ws = (m.get("activeWorkspace") or {}).get("name", "?")
                debug_log("monitor %s %s ws=%s" % (monitor_id, name, ws))
                break
    except Exception:
        pass
    if monitor_id is None:
        debug_log("no monitor at cursor")
        return 0

    # --- 3. Which window is under the pointer? ------------------------------
    # hyprctl lists windows bottom-to-top, so the last match wins (z-order).
    pid = None
    klass = ""
    try:
        clients = json.loads(run(["hyprctl", "-j", "clients"]) or "[]")
        debug_log("clients: " + " ".join(
            "%s@mon%s/ws%s/at%s" % (c.get("class"), c.get("monitor"),
                                    (c.get("workspace") or {}).get("id"),
                                    c.get("at")) for c in clients))
        for c in clients:
            at, size = c.get("at"), c.get("size")
            if not (c.get("mapped") and c.get("visible")):
                continue
            if c.get("hidden") is True or c.get("monitor") != monitor_id:
                continue
            if not (at and size and cx >= at[0] and cx < at[0] + size[0]
                    and cy >= at[1] and cy < at[1] + size[1]):
                continue
            pid, klass = c.get("pid"), c.get("class") or ""
    except Exception:
        pass
    debug_log("hit: pid=%s class=%s" % (pid or "none", klass or "none"))
    if not isinstance(pid, int):
        return 0  # pointer over desktop, bar, or a layer surface

    # --- 4. Map that window to a PipeWire/PulseAudio sink-input --------------
    # Apps often hand audio to a child process (Steam games, Chromium
    # helpers), so the whole process subtree counts as the same application.
    pids = set(subtree_pids(pid))
    # Binary-name fallback: actual comm names of the subtree (e.g. "firefox",
    # "WebKitWebProcess").
    comms = set()
    try:
        out = subprocess.run(["ps", "-o", "comm=", "-p", ",".join(
            str(p) for p in pids)], capture_output=True, text=True,
            timeout=5).stdout
        comms = {norm(w) for line in out.splitlines()
                 for w in line.split() if norm(w)}
    except Exception:
        pass
    norm_class = norm(klass)
    class_toks = norm_class.split()

    try:
        default_sink = run(["pactl", "get-default-sink"]).strip()
        sinks = json.loads(run(["pactl", "-f", "json", "list", "sinks"])
                           or "[]")
        default_sink_index = next(
            (s.get("index", -1) for s in sinks
             if s.get("name") == default_sink), -1)
    except Exception:
        default_sink_index = -1

    # Match order: exact PID in the subtree (4), then binary name (3), then
    # application name (2). Ties go to an actively playing stream on the
    # default sink.
    def score(si):
        props = si.get("properties") or {}
        try:
            direct = int(str(props.get("application.process.id", "")))
            direct = direct if direct in pids else None
        except Exception:
            direct = None
        b = norm(props.get("application.process.binary", ""))
        app = norm(props.get("application.name", ""))
        bybinary = any(inside(b, t) for t in comms)
        byname = any(inside(app, t) or inside(norm_class, app)
                     for t in class_toks)
        if direct is not None:
            return 4
        if bybinary:
            return 3
        if byname:
            return 2
        return 0

    best = None
    try:
        inputs = json.loads(run(["pactl", "-f", "json", "list",
                                         "sink-inputs"]) or "[]")
        ranked = []
        for si in inputs:
            s = score(si)
            if s > 0:
                vol = si.get("volume") or {}
                first = next(iter(vol.values()),
                             {}) if isinstance(vol, dict) else {}
                pct = (first.get("value_percent", "0%")
                       if isinstance(first, dict) else "0%")
                ranked.append((s, 0 if si.get("corked") else 1,
                               1 if si.get("sink") == default_sink_index
                               else 0, si.get("index", 1 << 30), pct))
        ranked.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3]))
        if ranked:
            best = (ranked[0][3], ranked[0][4])
    except Exception:
        pass

    if best is None:
        debug_log("stream: sink-input=none")
        fail("No audio stream for %s" % klass)
    sink_input, volume_before = best
    debug_log("stream: sink-input=%s before=%s" % (sink_input, volume_before))

    # --- 5. Move just that stream -------------------------------------------
    run(["pactl", "set-sink-input-mute", str(sink_input), "0"])
    if not run_ok(["pactl", "set-sink-input-volume", str(sink_input),
                   delta]):
        fail("Could not set volume for %s" % klass)

    # Read the result back for the OSD; this pactl build has no
    # get-sink-input-volume.
    volume_after = volume_before
    try:
        inputs = json.loads(run(["pactl", "-f", "json", "list",
                                         "sink-inputs"]) or "[]")
        for si in inputs:
            if si.get("index") == sink_input:
                vol = si.get("volume") or {}
                first = next(iter(vol.values()),
                             {}) if isinstance(vol, dict) else {}
                if isinstance(first, dict) and "value_percent" in first:
                    volume_after = first["value_percent"]
                break
    except Exception:
        pass
    percent = int(re.sub(r"\D", "", volume_after or "") or 0)

    # omarchy-osd renders EITHER a progress bar OR a message, never both, so
    # the app name rides in the OSD's `caption` field (line above the bar).
    if delta.startswith("+") and percent == 0:
        osd("volume-muted", klass, 0)
    else:
        osd("volume-high", klass, percent)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
