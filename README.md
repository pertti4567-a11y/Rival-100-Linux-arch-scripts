# Hotkey-työkalut (Rival 100 / Wayland / Hyprland)

Kaikki työkalut lukevat fyysistä näppäimistöä suoraan `/dev/input`-laitteista
(python-evdev), joten ne toimivat Waylandissa – `pynput` ja `xdotool` eivät
toimi Hyprlandissa.

| Tiedosto | Tehtävä |
|---|---|
| `autoclicker.py` | Autoclicker. Nappi 6 kytkee päälle/pois, napit 1/2/3 valitsevat klikattavan napin. |
| `dpiswitch.py` | DPI-vaihto: pidä nappi 6 pohjassa ja rullaa ylös/alas. |
| `forceclose.py` | Alt+F4 sulkee nopeasti valitun prosessin/ikkunan. |
| `hover_volume.py` | Komentorivityökalu: `hover_volume.py up\|down` muuttaa hiiren alla olevan ikkunan äänenvoimakkuutta. |
| `start_all.sh` | Käynnistää taustaprosessit. |
| `stop_all.sh` | Pysäyttää ne. |
| `install.sh` | Asentaa kaiken ja automaattisen käynnistyksen. |
| `uninstall.sh` | Poistaa asennuksen. |
| `udev/99-uinput.rules` | Sääntö, joka antaa `input`-ryhmälle oikeuden luoda virtuaalisen hiiren. |
| `hotkey-tools.service.in` | Malli systemd-käyttäjäpalvelusta (automaattinen käynnistys). |

---

## 1. Vaatimukset

- Arch-pohjainen Linux (Omarchy käy) tai muu jakelu, jossa on `pacman`.
- Python 3 ja `python-evdev`:
  ```bash
  sudo pacman -S --needed python-evdev
  ```
- Käyttäjän kuuluminen `input`-ryhmään (lukee `/dev/input`, kirjoittaa `/dev/uinput`):
  ```bash
  sudo usermod -aG input "$USER"
  ```
  **Kirjaudu ulos ja takaisin sisään**, muuten ryhmä ei ole voimassa.
- Ilmoituksia varten taustakäyntiin pitäisi olla ilmoitusdaemoni
  (esim. `sudo pacman -S mako`). Ilman sitä `notify-send` ei näytä mitään.
- Vain `dpiswitch.py` tarvitsee `rivalcfg`:n (asentaa oikean DPI:n hiireen
  USB:n yli). AUR: `paru -S rivalcfg` ja kerran `sudo rivalcfg --update-udev`.

Kaikki nämä tekee `install.sh` yhdellä komennolla.

---

## 2. Asennus

```bash
cd Ohjelmat/Hotkey      # USB:llä tämä kansio
./install.sh
```

`install.sh` tekee koko sarjan ja kysyy `sudo`-salasanan tarvittaessa:

1. asentaa Python 3:n, `python-evdev`:n ja `rivalcfg`:n (vain jos ne puuttuvat;
   `rivalcfg` tulee AUR:sta `yay`/`paru`-avustajalla),
2. lisää käyttäjän `input`-ryhmään,
3. asentaa `/etc/udev/rules.d/99-uinput.rules` ja päivittää udevin,
4. kopioi skriptit kansioon `~/Documents/Hotkey` (muutettavissa: `DEST=... ./install.sh`),
5. jos Omarchy on asennettuna, poistaa `SUPER + rulla` -oletuksen (työtilan vaihto)
   ja sitoo `SUPER + rulla` → `hover_volume.py up|down`
   `~/.config/hypr/bindings.lua`:ssa,
6. asentaa ja käynnistää systemd-käyttäjäpalvelun `hotkey-tools.service`.

Pelkän asennuksen voi tehdä myös käsin:

```bash
sudo pacman -S --needed python-evdev
sudo usermod -aG input "$USER"
sudo install -m 644 udev/99-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=input
mkdir -p ~/Documents/Hotkey
install -m 755 *.py start_all.sh stop_all.sh ~/Documents/Hotkey/
```

### Päivittäminen myöhemmin

Kopioi uudet tiedostot USB:ltä ja aja asennus uudelleen:

```bash
./install.sh
systemctl --user restart hotkey-tools.service
```

---

## 3. Automaattinen käynnistys (käynnistyy kun PC käynnistetään)

`install.sh` asentaa käyttäjän systemd-palvelun:

```bash
systemctl --user enable --now hotkey-tools.service   # asennus + käynnistys
systemctl --user status hotkey-tools.service         # tila
systemctl --user restart hotkey-tools.service        # uudelleenkäynnistys
systemctl --user stop hotkey-tools.service           # pysäyttää
systemctl --user disable --now hotkey-tools.service  # ei enää automaattisesti
```

Palvelu käynnistää `start_all.sh`:n kirjautumisen yhteydessä ja pysäyttää
`stop_all.sh`:n uloskirjautuessa.

### Hyprland-vaihtoehto

Jos haluat käynnistyksen Hyprlandin `exec-once`:na, lisää tiedostoon
`~/.config/hypr/autostart.lua`:

```lua
o.launch_on_start((os.getenv("HOME") or "/home/linux") .. "/Documents/Hotkey/start_all.sh")
```

Tällöin **älä pidä systemd-palvelua käytössä**, ettei työkalut käynnisty
kahdesti. Tarkista nykyinen sisältö:

```bash
grep -n "Hotkey" ~/.config/hypr/autostart.lua ~/.config/hypr/bindings.lua
```

`install.sh` poistaa Omarchyn `SUPER + rulla` -oletuksen (työtilan vaihto) ja
sitoo `SUPER + rulla` → `hover_volume.py` (`up`/`down`). Saman voi tehdä käsin
lisäämällä `~/.config/hypr/bindings.lua`:han:

```lua
hl.unbind("SUPER + mouse_down")
hl.unbind("SUPER + mouse_up")
o.bind("SUPER + mouse_up", "Window volume up", os.getenv("HOME") .. "/Documents/Hotkey/hover_volume.py up")
o.bind("SUPER + mouse_down", "Window volume down", os.getenv("HOME") .. "/Documents/Hotkey/hover_volume.py down")
```

`hover_volume.py` toimii myös suoraan komentoriviltä:

```bash
~/Documents/Hotkey/hover_volume.py up
~/Documents/Hotkey/hover_volume.py down
```

---

## 4. Käyttö

| Toiminto | Ohje |
|---|---|
| Autoclicker päälle/pois | Paina **nappia 6** kerran (sama nappi kuin DPI-nappi) |
| Valitse klikattava nappi | Paina **1**, **2** tai **3** (vaihtuu heti myös päällä ollessa) |
| Autoclicker pois | Paina **nappia 6** uudelleen |
| DPI-vaihto | Pidä **nappi 6** pohjassa + rullaa ylös/alas |
| Pikasulku | **Alt+F4** (`forceclose.py`) |
| Ikkunan äänenvoimakkuus | `SUPER + rulla ylös/alas` tai `~/.config/hypr/bindings.lua` |

Napit Rival 100:ssa (Linuxin numerointi):

| Fyysinen nappi | Koodi | Nimi |
|---|---|---|
| 1 | `0x110` | BTN_LEFT |
| 2 | `0x111` | BTN_RIGHT |
| 3 | `0x112` | BTN_MIDDLE |
| 4 | `0x113` | BTN_SIDE |
| 5 | `0x114` | BTN_EXTRA |
| 6 | `0x115` | BTN_FORWARD |

Jos haluat käyttää jotain muuta nappia toggle-nappina, muuta
`MODIFIER = "BTN_FORWARD"`-riviä tiedostossa `autoclicker.py`.

Säädettävät asetukset `autoclicker.py`:ssä: `CPS` (klikkauksia sekunnissa,
oletus 25), `MODIFIER`, `MOUSE_NAME_FILTER` (oletus `"Rival"`).

---

## 5. Käynnistä ja pysäytä käsin

```bash
~/Documents/Hotkey/start_all.sh     # käynnistää
~/Documents/Hotkey/stop_all.sh      # pysäyttää
tail -f /tmp/hotkey-tools.log       # loki
```

`start_all.sh` toimii mistä tahansa kansiosta ja lopettaa vanhat instanssit
ennen uusia, joten sitä voi käyttää myös suoraan USB:ltä.

---

## 6. Vianmääritys

**Autoclicker ei reagoi napin 6 painallukseen**

```bash
python3 -c "from evdev import list_devices,InputDevice; [print(p,InputDevice(p).name) for p in list_devices()]"
tail -20 /tmp/hotkey-tools.log
```

- Logissa pitäisi näkyä `Laite: ... Rival 100 ...`. Jos lukee
  `rival-autoclicker-virtual-mouse`, kyseessä on oma virtuaalilaite – uusin
  versio ohittaa sen automaattisesti.
- `uinput-virhe: ...` tarkoittaa, ettei `/dev/uinput` ole käytettävissä:
  tarkista `sudo usermod -aG input "$USER"` + uudelleenkirjautuminen ja
  `/etc/udev/rules.d/99-uinput.rules`.
- Ei mitään tapahtumia? `sudo evtest` tai kokeile toista nappia
  (`MODIFIER`-muuttuja).

**Ilmoituksia ei näy**

```bash
which mako dunst swaync   # pitäisi löytyä jokin
sudo pacman -S mako
```

**Hiiri toimii oikein, mutta DPI ei vaihdu**

```bash
rivalcfg list-sensor-presets
sudo rivalcfg --update-udev
```

Ilman `rivalcfg`:a `dpiswitch.py` ei pääse kirjoittamaan hiirelle, vaikka se
ei virheellä.

**Tökalut eivät käynnisty kirjautumisessa**

```bash
systemctl --user status hotkey-tools.service
systemctl --user --failed
```

---

## 7. Turvallisuus

- Skriptit eivät sisällä avaimia tai salasanoja eikä lähetä mitään verkkoon.
- `sudo` tarvitaan vain kolmeen asennusvaiheeseen: paketti, `input`-ryhmä ja
  udev-sääntö.
- `forceclose.py` tappaa prosesseja – tarkista `TARGET_PROCESS` ennen käyttöä.
- Autoclicker luoo virtuaalisen hiiren (`/dev/input/event24`), joten se näkyy
  normaalina hiirenä ja poistuu, kun ohjelma suljetaan.