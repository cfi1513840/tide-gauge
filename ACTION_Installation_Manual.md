# ACTION Tide Station — Installation Manual

## 1. Overview

**ACTION** (Atlantic Coastal Tide Instrumentation and Observation Network)
is a multi-node coastal tide and weather monitoring system. Each node —
a self-contained, compact, solar-powered acquisition module, normally
paired with a Raspberry Pi tide station via a LoRa radio link — reads
an integrated ultrasonic distance sensor, converts that reading into a
tide level relative to Mean Lower Low Water (MLLW), and makes the
result available locally (a physical display and a station website)
and remotely (cloud-synced time-series data, SMS/email alerts).
Alternatively, sensor data can be transmitted via a cellular link to a
cloud-based network, where it is forwarded for further processing and
database storage.

The project addresses a real gap in tide data availability: Maine's
roughly 3,500 miles of tidal shoreline are served by only five active
NOAA CO-OPS stations. ACTION nodes are deployed in Belfast, Maine;
South Carolina; and at Lincoln Academy in Damariscotta, Maine, with
more planned.

### 1.1 Repository and branches

The codebase lives at
[github.com/cfi1513840/tide-gauge](https://github.com/cfi1513840/tide-gauge).

During the development phase, GitHub branches are utilized as follows:

- **`dev`** — the stable development branch. This is what runs on
  operational (production) nodes.
- **`exp`** — the active experimental branch, based on the `dev`
  branch. New work happens here first, gets tested on a staging node,
  and is merged to `dev` once proven.

The standard workflow is: develop on `exp` → validate on a dedicated
test node → roll out to operational nodes running `dev`.

### 1.2 Node roles

Every station runs one of two mutually exclusive collector modes:

- **`tide.py`** — Collector + Local Display combined. This is the
  standard mode for a station with a physical screen on-site (Tk
  display, optionally viewable remotely over VNC). It also generates
  the station's local website content and handles alert evaluation.
- **`tidemonitor.py`** — Collector only, headless. No local display.
  Used where a physical screen isn't needed or practical.

A station runs one or the other, never both — they'd conflict over
the same sqlite3/InfluxDB connections if run simultaneously.

### 1.3 Data flow, at a glance

- **Sensor input** arrives one of two ways:
  - **LoRa** — a local radio receiver, read directly over serial by
    the RPi.
  - **Blues Notecard / Notehub** — a cellular-connected sensor unit
    that posts readings to Notehub, which forwards them to the RPi
    over HTTPS. An alternate path is a direct link
    from Notehub to the InfluxDB cloud database.
- **Storage**: readings are written to a local sqlite3 database (a
  secondary diagnostic log, plus cached NOAA predictions, weather/NDBC
  data, station configuration, and alert-subscriber accounts) and to
  **InfluxDB 3 Core**, running locally on the RPi as the primary
  time-series store. A decoupled, local-first sync periodically pushes
  new local data to **InfluxDB Cloud Serverless**, so cloud
  connectivity issues never block local operation.
- **Presentation**: when the tide station configuration includes public
  website services, Apache2 is used to serve the station's website
  (tide chart, current conditions, historical plots) from the local
  Raspberry Pi, exposed to the internet through a **Cloudflare
  Tunnel** rather than an open firewall port. The same data drives the
  optional local Tk display.
- **Alerts**: registered subscribers can receive email (via Brevo)
  and/or SMS (via Twilio) notifications when the tide crosses a
  threshold, an upcoming high/low tide approaches, or wind/temperature
  conditions meet configured criteria.

Later sections in this manual cover the prerequisite external
accounts, the fresh-installation procedure, the supporting system
configuration `install.sh` doesn't automate, a checklist for
upgrading an existing station, and a record of notable issues found
and fixed along the way.

## 2. Prerequisite accounts & services

A new station is typically **joining an existing ACTION network**
rather than standing up brand-new services from scratch — the
Cloudflare account, InfluxDB Cloud organization, and alert-related
accounts (Brevo, Twilio) are usually already provisioned and shared
across the fleet. In that case, the practical task before starting
`install.sh` isn't creating new accounts; it's **obtaining access to
the existing credentials** needed to configure this station within
that shared infrastructure (API tokens, tunnel access, org/bucket
names, and so on).

The table below still applies either way — it lists what each
service is used for and when it's needed, whether you're creating an
account for the first time or requesting access to one that already
exists.

Before running `install.sh`, gather accounts and credentials for the
external services this station will actually use. Not every station
needs every service — the table below notes which are always
required, which depend on the station's configuration, and which
need no account at all.

| Service | Used for | When it's needed |
|---|---|---|
| **GitHub** | Cloning the repository | Always. The repo is public — no account is needed just to clone it, only if you intend to contribute changes back. |
| **InfluxDB Cloud Serverless** | Cloud-synced time-series storage, accessible from anywhere | Always, in the standard architecture. Org and bucket must be created ahead of time (see Section 2.6). |
| **Cloudflare** (account + Tunnel) | Exposing services to the internet without an open firewall port | Always required — every station needs it for admin/maintenance SSH and VNC access, regardless of other configuration. Also used for a **public website** (if enabled) and for a **Blues Notecard**'s inbound Notehub webhook (if used) — the same Tunnel serves all three purposes as needed. |
| **Blues Notehub** (notehub.io) | Cellular sensor connectivity — device registration, Fleet, and the HTTPS route that forwards readings to the station | Only if the station uses a Notecard sensor. Not needed for a LoRa-only station. |
| **Brevo** | Outbound email for subscriber alerts | Only if the alert feature's email notifications are enabled. |
| **Twilio** | Outbound SMS for subscriber alerts | Only if the alert feature's SMS notifications are enabled. |
| **OpenWeatherMap** | Current-conditions weather shown on the local display and website | Only if local weather display is enabled. |
| **NOAA CO-OPS** | Tide predictions | Always used, but no account or registration needed — it's a public API. |
| **NDBC** (buoy data) | Wave height/period, water temperature | Used if the station is near enough to open water for this data to exist. No account needed — public API. |

### 2.1 What to have ready before starting

For a station joining an existing ACTION network, "have ready" below
usually means access to the existing shared credentials rather than
creating a new account — check with whoever administers the network
first.

- A **GitHub** account only if you plan to contribute back (cloning
  itself needs nothing).
- Access to the network's **InfluxDB Cloud Serverless** organization
  and bucket (see Section 2.6 for the exact values this station
  expects), or a new one created if this is the first station on a
  fresh network.
- Access to the network's **Cloudflare** account and domain — needed
  on every station for admin/maintenance SSH and VNC access, in
  addition to a public website (if enabled) and a Notecard's inbound
  webhook (if used).
- If using a Notecard: access to the network's **Blues** account (or
  a new one), the physical Notecard paired to a Notecarrier, and a
  plan selected for the device.
- If alerts will be enabled: access to the network's **Brevo**
  and/or **Twilio** sending credentials.
- If local weather display will be enabled: an **OpenWeatherMap**
  API key (shared across the network or station-specific, either
  works).

No advance signup is needed for NOAA CO-OPS or NDBC — both are used
directly as public data sources.

### 2.2 VNC server: RealVNC vs. the bare TigerVNC scraper

Every station needs VNC access for admin/maintenance (Section 2's
table above), reached through the Cloudflare Tunnel rather than an
open port. Two different things can provide it, and it's easy to
assume they're independent, competing VNC servers — they aren't.

`X0tigervnc` is a single, shared TigerVNC component whose job is
capturing a real X display's content ("scraping" it, in TigerVNC's
own terminology) and speaking the RFB protocol viewers use. It can be
reached two different ways:

- **Directly**, via `x0vncserver`/`x0tigervncserver`, exposed
  straight to viewers with TigerVNC's own native, simple `VncAuth` —
  a single, shared VNC password, nothing more.
- **Wrapped by RealVNC** — when RealVNC's own service
  (`vncserver-x11-serviced` / `vncserver-x11-core`) starts, it spawns
  this exact same `X0tigervnc` component internally as a helper
  (bound to `localhost` only — never reachable directly) and layers
  its own, separate feature set on top before exposing *that* layer
  externally: `Authentication=SystemAuth` (the station's real Unix
  login, rather than one shared password) and TLS encryption
  (`Encryption=AlwaysOn` by default, which is why RealVNC connections
  prompt a viewer to verify a certificate fingerprint the first time,
  where the bare TigerVNC scraper never does).

Both approaches serve the same real display; they're two different
front ends for it, not two things that need to coexist. Whichever one
currently holds the VNC port needs to be fully stopped before the
other can bind to it — starting one while the other is still active
produces a silent bind failure, not a clean handoff.

**Standard going forward: new stations should run RealVNC with
`Authentication=SystemAuth`**, tying access to individual station
accounts rather than one password shared across everyone who's ever
needed to connect. This needs its own service enabled and configured
— it isn't something the bare TigerVNC scraper tools provide, no
matter how they're set up.

To set this up on a fresh station:

```bash
sudo systemctl enable vncserver-x11-serviced.service
sudo systemctl start vncserver-x11-serviced.service
sudo systemctl status vncserver-x11-serviced.service
```

RealVNC's own `RfbPort` defaults to `5900`; this network's existing
Cloudflare Tunnel convention (matching the older stations' VNC route)
expects `5901`. To match it, set the port from RealVNC's own GUI —
right-click its taskbar icon → Options → Connections — while
connected through whatever VNC access already works, *before*
disabling that access. Confirm the change landed in
`/root/.vnc/config.d/vncserver-x11` (`RfbPort=5901`), then only once
that's confirmed:

```bash
sudo systemctl stop x0vncserver.service      # if this station had it running
sudo systemctl disable x0vncserver.service
sudo systemctl restart vncserver-x11-serviced.service
```

Earlier stations already running the bare TigerVNC scraper
(`x0vncserver`, plain `VncAuth`) are left as-is — this standard
applies to new deployments going forward, not a retrofit of stations
already in service.

### 2.3 SSH

Every station also needs SSH access for the same admin/maintenance
purposes as VNC, reached the same way — through the Cloudflare
Tunnel, never an open port. Raspberry Pi OS ships with its SSH
server disabled by default, so this needs verifying (and enabling,
if this is a fresh station) rather than assumed.

From `sudo raspi-config`, select **Interface Options**, then **SSH**,
and confirm it's enabled. (Skip any guide that instead tells you to
select a specific numbered shortcut like "I1 SSH" — those shortcuts
get renumbered between Raspberry Pi OS releases and are a common
source of outdated instructions; the plain menu names above stay
stable.)

Access itself is controlled by `/home/tide/.ssh/authorized_keys`.
Each line in this file is one client's public key; a client whose
public key is listed there can connect without a password, and one
that isn't, can't. Setting up SSH access for a new client machine
means appending that machine's own public key as a new line in this
file — nothing else needs to change on the station's side to grant
or revoke a given client.

The corresponding client-side configuration — the `~/.ssh/config`
entry that routes an outgoing connection through this station's
Cloudflare Tunnel rather than trying to reach it directly — is
already covered in the Cloudflare tutorial (prerequisite 6), rather
than repeated here.

### 2.4 Cloudflare Tunnel

Every station is an RPi on an ordinary home or office network,
typically behind a router with no static public IP and no safe way
to forward inbound ports to it directly. A Cloudflare Tunnel solves
this the other way around: the RPi itself initiates an outbound
connection out to Cloudflare's own network, and Cloudflare routes
public requests for this station's web page, SSH, and VNC back
through that same tunnel. No inbound port ever needs to be opened on
the station's own router, and nothing about the setup depends on
that router's own configuration or NAT situation. Account, domain,
and tunnel setup are all covered in the Cloudflare tutorial
(prerequisite 6).

### 2.5 InfluxDB 3 Core (local)

`tide.py` needs fast, reliable reads and writes for its own,
moment-to-moment operation — outlier detection, the TK display, the
web page, alerting — none of which can depend on this station's
internet connection staying up. Each station therefore keeps its own,
entirely local copy of its own data, independent of anything else,
and separately syncs that data up to the shared cloud database
(Section 2.6) whenever connectivity actually allows. Installation is
covered in the InfluxDB 3 Core tutorial (prerequisite 3).

### 2.6 InfluxDB Cloud

Where each station's local database is deliberately isolated,
holding only that one station's own data, InfluxDB Cloud is the
single, shared destination every station syncs into — the only
place cross-station comparison is possible, and an off-site backup
of each station's own readings independent of that station's own
RPi and SD card. Every station shares the same organization and
bucket; credentials are normally provided by the network
administrator rather than created fresh per station. Covered in the
InfluxDB Cloud tutorial (prerequisite 16).

### 2.7 Grafana

InfluxDB 3 Core has no web interface built in. InfluxData offers a
separate web front end, InfluxDB 3 Explorer (run as a Docker
container), but this project uses Grafana instead: it is more capable
and easier to use for browsing and graphing a station's data. Grafana
is the standard way to view a station's local data on every station,
not an optional add-on. Installation and the
local datasource configuration are covered in the Grafana tutorial
(prerequisite 15).

## 3. Fresh installation procedure

This section walks through `install.sh` as it actually runs, in
order. The script is designed to be run more than once if needed —
at a couple of points it deliberately lets you stop, edit a file with
your own preferred tools, and pick back up by running the script
again. Nearly every step also checks the current state before acting,
so re-running the script against an already-configured station is
safe — most steps simply report "already in place" and move on
rather than repeating or overwriting anything. Everything below
assumes the prerequisites from Section 2 are already in hand and the
repository has been cloned to `~/bin/tidegauge`, which the script
must be run from.

### 3.1 Prerequisite confirmation

The script opens by printing its own prerequisite checklist and
asking whether everything is ready. This list overlaps with Section 2
above, plus a few purely technical items — Apache2, SQLite3, and the
Python virtual environment and its required modules are all
automatically installed if missing, rather than needing to be
confirmed here; site-specific configuration prepared with
`tide_constants.json.template` and `tide.env.template` as a guide —
and two configuration-dependent items: a LoRa sensor's receiver
plugged into the USB port named by `SERIAL_PORTS` in `tide.env`, and,
for a Notecard sensor, a route already configured in notehub.io to
deliver its data to this station.

Before answering, the prompt offers to look up further detail on any
numbered item: entering an item number displays that item's tutorial
file (`prereq_<N>_tutorial.txt`) if one exists, then asks again,
looping until Enter is pressed with nothing typed. Every item now
has one, from the basic accounts (Brevo, Twilio, OpenWeatherMap)
through to the more involved local installs (InfluxDB 3 Core,
Grafana) and the Cloudflare/InfluxDB Cloud setup that ties everything
together. As new prerequisites are added in the future, they simply
need a same-named tutorial file dropped in, with no further script
changes.

Answering "N" to the final "have all prerequisites been completed?"
question exits immediately with no changes made.

### 3.2 Apache CGI symlink fix

The script checks whether Apache's default `+SymLinksIfOwnerMatch`
setting in `serve-cgi-bin.conf` has already been changed to
`+FollowSymLinks` before doing anything else. If it has, it says so
and moves on with no prompt at all. If not, it explains why the
change is needed — the CGI scripts this station uses are root-owned
symlinks pointing at tide-owned files, and Apache's default setting
refuses to follow a symlink whose owner doesn't match its target —
and offers to make the fix and reload Apache.

### 3.3 Python virtual environment

The script checks whether the `python3-venv` package is installed —
a common gap on a fresh Raspberry Pi OS image, and `python3 -m venv`
fails outright without it — and installs it automatically if
missing. It then creates the virtual environment at
`/home/tide/.tidenv` if it doesn't already exist, and either way runs
`pip install -r requirements.txt` against it — safe to run every
time, since `pip` itself skips anything already satisfied and this
naturally picks up any dependency added to `requirements.txt` since
the venv was first created.

### 3.4 User and directory setup

The script adds the current user to the `www-data` group (and
`www-data` to the current user's group), needed so CGI scripts
running as `www-data` and `tide.py` running as the station's own user
can each access files the other needs to read or write. It sets
ownership and permissions on `/var/www` and `/var/www/html` so
`www-data` can write there.

### 3.5 `tide.env` preparation

If `tide.env` doesn't exist yet, the script copies
`tide.env.template` to a working copy, opens it in `nano`, and moves
the result into place once editing is done — the same simple flow as
before.

If `tide.env` already exists, the script instead compares it against
`tide.env.template`, reporting any parameters present in one but not
the other. If nothing's missing or obsolete, it says so and asks
whether to edit the file anyway. That matters when `tide.env` was
copied from another station: its parameter names match the template,
but its station-specific values still need changing. Answering "Y"
backs it up and opens it in `nano`, the same as below. If there's a
difference, the existing file is backed
up as `tide.env.dev` before opening directly in `nano` for the
missing lines to be added and any obsolete ones removed in place. If
a `tide.env.dev` backup from an earlier run already exists, the
script warns before overwriting it — since that's the copy that
would be needed to roll back to a previous stable version — and
skips the update entirely if the answer is no, leaving both the
existing backup and the current `tide.env` untouched.

### 3.6 systemd service

The script checks whether `/etc/systemd/system/tide.service` already
exists. If it does, it's left as-is with no further action. If not,
`tide.service.template` is copied to a working copy, opened in `nano`
for site-specific edits (paths, user, etc.), and — if confirmed —
moved into the systemd directory. Either way, the script then runs
`systemctl enable tide` (harmless to repeat if already enabled).

### 3.7 Encryption keys

If none of the four keys (`k1`, `k2`, `k3`, `ku`) exist yet in the
directory the script is run from, and there is no
`tide_constants.json` there either, the script runs `makekeys.py` to
generate a fresh set. If all four keys already exist, this step is
skipped. In any other case (some keys missing, or keys missing while
a `tide_constants.json` exists) the script stops at startup instead,
because regenerating keys over an existing encrypted
`tide_constants.json` would make it permanently undecryptable (see
3.15). The keys are never copied anywhere
else — they, like `tide_constants.json`, `tide.env`, and
`sensor_fields.json`, live exclusively in `~/bin/tidegauge`; nothing
reads them from `/var/www/html`.

Every run then sets the key files' ownership to `tide:tide` and their
permissions to 640 for `k1`–`k3` and 600 for `ku`, so existing
stations and keys copied in during an upgrade are corrected too. The
web server's `www-data` account belongs to the `tide` group, so it can
read `k1`–`k3`, which the CGI scripts need through `tidecrypto.py`.
Only `tide` itself can read `ku`, which nothing on the web side uses.

### 3.8 Handling `tide_constants.json`

If an encrypted `tide_constants.json` already exists, the script
compares its parameter names — the values are encrypted, but the
key names are read directly, needing no decryption — against
`tide_constants.json.template`, reporting anything missing or
obsolete. If the key sets match exactly, it asks whether to edit
the file anyway (for example, one copied from another station);
answering "Y" goes through the same backup, decrypt, edit and
re-encrypt steps described next. If
they differ, the existing file is backed up as
`tide_constants.json.dev` (protected by the same overwrite warning
described in 3.5), then decrypted to a clear-text scratch file for
editing in `nano`, guided by the report just shown, before being
re-encrypted and moved into place. The scratch file is removed
afterward; no clear-text copy is left behind.

If `tide_constants.json` doesn't exist yet, and a clear-text
`tide_constants.tmp` is already sitting in the directory (from having
edited it separately, or copied one over from another machine), its
content is shown and the script asks whether to encrypt it as-is.
Otherwise, the script offers to exit immediately so `tide_constants.tmp`
can be prepared with any editor at leisure — running the script again
later picks up right where this left off — or, answering "N," opens
a fresh working copy in `nano` directly. Either way, once editing is
done the file is encrypted via `encrypt_constants.py` and moved into
place as `tide_constants.json`.

### 3.9 `tides.db` and station sensor configuration

If `tides.db` doesn't already exist in the HTML directory, the
starter database (`sqltides.db`) is copied into place with
group-writable permissions (`tide.py` needs to keep writing new
readings to it). Since this is a genuinely fresh database, the script
then runs an interactive wizard (`configure_iparams.py`) that asks,
for each of up to three sensors, whether it's installed, and if so
its link type (`lora` or `note`) and calibration value — resetting
any sensor marked as not installed to disabled with no stale
calibration or type left over from the starter file. If more than one
sensor is installed, it also asks which one should serve as the
primary station display; with only one installed, that one is
selected automatically. If `tides.db` already exists, none of this
runs — the existing configuration is left alone.

### 3.10 `sensor_fields.json`

If `sensor_fields.json` doesn't exist yet, it's copied directly from
`sensor_fields.json.template` — no editing is needed, since (unlike
`tide.env` and `tide_constants.json`) this file is purely structural
and holds no site-specific data. If it already exists, it's compared
against the template the same way as the other two config files; if
the parameter names match, nothing happens. If they don't, the
existing file is backed up as `sensor_fields.json.dev` (with the same
overwrite protection) and then simply replaced outright with the
current template — there's nothing site-specific to preserve, so no
editing step is needed here the way there is for `tide.env` or
`tide_constants.json`.

### 3.11 `webimage.png` and `webinfo.txt`

If these don't already exist in the HTML directory, a generic
placeholder image and a generic placeholder description are copied
in from their respective templates, each with a note that they're
meant to be replaced with something specific to this station when
convenient — a station photo, and a short description of the site.
If either already exists, it's left untouched.

### 3.12 Mailspool directories and symlinks

The script checks for the mailspool directories the alert-portal CGI
scripts and `tide.py`'s outbound mail processing both depend on
(`mailspool` and `mailspool/failed` under the HTML directory),
creating them with the correct ownership and permissions if they're
missing, and correcting the permissions either way if they already
exist.

It then checks three symlinks: `tidecrypto.py` and `tideplot.py` (as
`tideplot.cgi`) into the CGI directory, and `tide.env` into the HTML
directory. Each is checked before being touched — a correct existing
symlink is left alone, a symlink pointing at the wrong target is
corrected, and a real file sitting where a symlink is expected is
only ever replaced if its content exactly matches the intended
target (otherwise it's left alone with a note to check it manually,
never overwritten blindly).

The `tide.env` symlink specifically exists because several CGI
scripts (`alertform.cgi` among them) load their configuration from an
explicit, hardcoded `/var/www/html/tide.env` path rather than
searching for it the way `tide.py` does. The symlink means there's
still only one real `tide.env`, living in `~/bin/tidegauge` as
described in 3.5 — the CGI scripts simply reach it via a second path,
with no separate copy to drift out of sync.

### 3.13 Final file deployment

The script copies every git-tracked `.cgi`, `.html`, and `.pdf` file
to its destination (CGI files to the CGI directory at `755`, the
others to the HTML directory at `644` — world-readable, matching
what a web server needs to serve static content, regardless of which
user happens to own the copy).

Note that `tide.html` — the tide and weather display page — is not
part of this deployment at all, and shouldn't be confused with
`index.html` (the site's actual home page, which *is* deployed here
under its own name like any other tracked file). `tide.html` is
generated entirely by `tide.py` itself at runtime (via `tidehtml.py`)
and regenerated continuously as the station runs; `install.sh` never
creates, copies, or touches it.

### 3.14 `tideplot.py` cron entry

Finally, the script offers to add the crontab entry that keeps
`tideplot.html` regenerated every 20 minutes (`1,21,41 * * * *`),
running through the virtual environment's own Python interpreter.
This check is idempotent — it looks for the exact line already being
present before adding it, so re-running the script on an
already-configured station won't create a duplicate entry.

### 3.15 Upgrading an existing station to a new code branch

Moving a *live, currently-running* station onto new code (a branch
merge, a version bump) is a different problem from a fresh install —
the running station has to keep working, undisturbed, for as long as
it takes to prepare and validate the new one, with a clean way back
if anything goes wrong.

**The strategy: a separate directory, not the live one.** Clone the
target branch into a new directory alongside the existing
installation (`~/bin/tidegauge-new`, say, next to the live
`~/bin/tidegauge`) — never into the live directory itself, and never
by pulling new commits into it while it's still the one actually
running. Copy `tide_constants.json`, `tide.env`, and
`sensor_fields.json` from the live directory into the new one, along
with the four encryption key files (`k1`, `k2`, `k3`, `ku`) and the
cloud sync watermark (`.cloud_sync_watermark`), then run `install.sh`
there:

```bash
cd ~/bin/tidegauge
cp -p tide_constants.json tide.env sensor_fields.json \
      k1 k2 k3 ku .cloud_sync_watermark ../tidegauge-new/
```

(`cp -p` keeps each file's owner and permissions, which matters for
the key files.)

This lets `install.sh`'s drift-check reconcile the *copies* against
the new branch's templates, while the live files — and the live
`tide.py` reading them — stay completely untouched throughout. A
crash or unplanned restart of the live process during this whole
preparation phase is harmless, since nothing it depends on has
changed.

**`install.sh` checks for these files before it does anything.**
It works only on the files in the directory it is run from, never
on the live copies, because that directory is what becomes
`/home/tide/bin/tidegauge/` after the rename. If it is run anywhere
other than `/home/tide/bin/tidegauge/` on a station that already has
an installation there, and any of `tide_constants.json`, `tide.env`,
`sensor_fields.json`, `k1`, `k2`, `k3` or `ku` is missing, it stops
immediately and prints the `cp -p` command for the missing files.

The key files matter most. Without them, `tide.py` can't decrypt
`tide_constants.json` or any subscriber's stored email address or
phone number, and a brand-new key set from `makekeys.py` never
could. So even in its own directory, `install.sh` refuses to run
`makekeys.py` when a `tide_constants.json` is present but the keys
aren't, or when only some of the keys are present. If that happens
after a cutover, copy the original keys back from `tidegauge-save`
with `cp -p` and run `install.sh` again.

The watermark matters less. Without it, the first cloud sync after
cutover starts again from the beginning and re-sends the station's
entire local history to InfluxDB Cloud. That's harmless, since
identical points simply overwrite themselves, but slow. `install.sh`
prints a reminder if it wasn't copied, but carries on.

**Why the new directory can be prepared, but not run, in place.** `tidehelper.py`
loads `tide_constants.json` (and `tidecrypto.py` loads the Fernet
key, `ku`, plus `k1`/`k2`/`k3`) from a path hardcoded directly into
the source as the literal string `/home/tide/bin/tidegauge/` — not
derived from wherever the script actually runs from. This means
`tide.py` itself will *always* read whatever is at that exact path,
no matter which directory it was launched from. (The install-time
tools are different: `install.sh`, `decrypt_constants.py` and
`encrypt_constants.py` all use the files in their own directory, so
they can prepare the new directory without touching the live one.)

The practical result: testing the new branch's `tide.py` against its
own, newly-edited config requires that config to actually be reachable
at the literal `/home/tide/bin/tidegauge/` path — a same-machine test
directory under a different name can prepare everything safely, but
can't be *run* from in place and have it take effect.

**The clean way to cut over, once the new directory is fully
prepared and validated:** rename directories rather than copy files
into place.

```bash
# Confirm nothing is currently running from the old directory
ps -eo pid,lstart,cmd | grep tide.py

cd ~/bin
mv tidegauge tidegauge-save
mv tidegauge-new tidegauge

cd tidegauge
~/.tidenv/bin/python3 tide.py
```

Because the rename makes the new code and config the *actual*
contents of `/home/tide/bin/tidegauge/`, every hardcoded path
resolves correctly with nothing left to edit by hand. The revert, if
needed, is the same operation in reverse:

```bash
cd ~/bin
mv tidegauge tidegauge-new
mv tidegauge-save tidegauge
```

**One thing the rename doesn't fix on its own: stale symlinks.**
`install.sh`'s symlink step (`tidecrypto.py`, `tideplot.py`/
`tideplot.cgi`, `tide.env`) bakes in the *absolute path as it existed
at the moment `install.sh` ran*. If that was the temporary,
pre-rename directory name, the symlinks now point at a path that no
longer exists — surfacing later as a CGI script failing outright with
`No module named 'tidecrypto'`. The fix is simply re-running
`install.sh` once more, from the final, now-stable path, so it
recreates each symlink pointing at the location that's actually
correct:

```bash
cd /home/tide/bin/tidegauge
./install.sh
```

Note the plain `./install.sh` — **never run the whole script with a
blanket `sudo`.** It's designed to run as the regular `tide` user,
escalating individual commands via its own ~30 embedded `sudo` calls
only where actually needed. Run as `sudo ./install.sh` instead, at
least one of those steps (adding `tide` to the `www-data` group)
depends on `$USER` resolving to `tide` — under a blanket `sudo` it
may well resolve to `root` instead, silently doing something
pointless rather than what it's meant to.

Before starting the new process for real, confirm the old one is
genuinely stopped — not just that its terminal window closed. A dead
session doesn't reliably kill a process it started if it was ever
backgrounded; verify with `ps -eo pid,lstart,cmd | grep tide.py`
(and, for anything with its own listening port, such as InfluxDB 3
Core, `sudo ss -tlnp | grep <port>`) before assuming it's actually
gone.


## 4. Known issues and troubleshooting notes

Standing, reusable gotchas worth knowing before they cost you
debugging time — not a changelog of every bug fixed during
development, just the ones likely to recur on a future station.

### 4.1 InfluxDB 3 Core installation

- **The quick-installer's own symlink step can fail** (most likely a
  `$EUID`/POSIX `sh` incompatibility, the same class of bug seen in
  other installer scripts shaped this way) — regardless of what it
  reports, confirm the binary actually landed where it should, and
  if not, copy it manually rather than trust the symlink:
  ```bash
  sudo cp ~/.influxdb/influxdb3 /usr/local/bin/influxdb3
  sudo chmod +x /usr/local/bin/influxdb3
  ```
- Its own printed instruction — "Run `source '/home/tide/.bashrc'`"
  — must actually be *sourced*, not executed directly
  (`source /home/tide/.bashrc`); running it as a plain command fails
  with "Permission denied," since it's not meant to be its own
  executable.
- The interactive installer leaves a **temporary, foreground
  instance running**, using its own defaults (`--node-id=node0`,
  `--http-bind=0.0.0.0:8181`, data in `~/.influxdb/`) — none of
  which match this project's template. This must be fully stopped
  before the real systemd service can bind the port, and **a dead
  terminal session does not reliably kill it** — always verify
  directly rather than assume:
  ```bash
  sudo ss -tlnp | grep 8181
  ```
- `--plugin-dir` requires its target directory to already exist —
  InfluxDB 3 Core does not create it automatically, and the service
  fails to start without it:
  ```bash
  mkdir -p /home/tide/influxdb3/plugins
  ```
- `--node-id` in the copied service file must be changed from the
  template's placeholder station name to the actual one — easy to
  miss, buried inside a long `ExecStart` line.
- Moving the installer's default data location
  (`~/.influxdb/data`, hidden and dot-prefixed) to the project's own
  convention (`~/influxdb3/data`) also avoids confusing it with any
  InfluxDB V2 install already present on the same machine.

### 4.2 Grafana and the InfluxDB 3 datasource

- `localhost` can resolve to IPv6 (`::1`) first on modern systems,
  while `influxdb3` only ever binds IPv4 (`127.0.0.1`, per this
  project's service file). A datasource URL of `http://localhost:8181`
  can therefore fail with a misleading "connection refused" even
  though the server is healthy — use the explicit IPv4 address,
  `http://127.0.0.1:8181`, instead.
- SQL/Flight SQL over plain HTTP (no TLS) needs **"Insecure
  Connection"**, found specifically under **Advanced Database
  Settings**. This is a genuinely separate setting from "Skip TLS
  Verify" (in the general TLS/SSL Settings section) — that one still
  performs a TLS handshake, just without validating the certificate,
  which does nothing here since the server isn't using TLS at all.
  The symptom without the correct toggle:
  `tls: first record does not look like a TLS handshake`.
- Getting the SQL/InfluxQL product selector to even appear in the
  datasource setup may require enabling a feature toggle —
  `newInfluxDSConfigPageDesign` under `[feature_toggles]` in
  `grafana.ini` — depending on the installed Grafana version. Newer
  versions may bundle this by default.
- InfluxDB 3 Core is schema-on-write: a table with no data ever
  written to it doesn't formally exist yet. Querying it by name
  before any writes have happened can fail with "table not found"
  even though the connection itself is completely healthy. Confirm
  connectivity first with something schema-independent — Grafana's
  own Save & Test, or a bare `SHOW TABLES` — before treating a
  table-specific query failure as a connection problem.

### 4.3 Email (Brevo/SMTP)

Brevo is the only email service the code supports; there is no
longer any fallback to another SMTP provider. Older stations may
still have `EMAIL_SERVICE` in `tide.env`, and `CONTACT_EMAIL`,
`EMAIL_USERNAME`, `EMAIL_PASSWORD`, `SMTP_SERVER` and `SMTP_PORT` in
`tide_constants.json`. Nothing reads them any more, and `install.sh`
reports them as obsolete; they can be deleted when it offers the edit.

`BREVO_SMTP_SERVER` lives in `tide_constants.json`; `SMTP_PORT`
lives separately, in `tide.env`. A missing or blank `SMTP_PORT`
makes Python's `smtplib` silently fall back to its own default, port
25 — which is almost universally blocked outbound as a standard
anti-spam measure. The result is a consistent connection *timeout*
that looks exactly like a credentials or server-address problem, but
isn't. Check `tide.env` for `SMTP_PORT=587` before suspecting
anything in `tide_constants.json`.

### 4.4 Diagnosing CGI failures

A generic Apache "Internal Server Error" page gives no detail
whatsoever in the browser — the actual Python traceback only ever
appears in the server's own error log:

```bash
sudo tail -50 /var/log/apache2/error.log
```

Common causes worth checking first: the `tide.env` symlink into the
web root (several CGI scripts hardcode that exact path rather than
searching from their own working directory), mailspool directory
permissions, and the CGI file's own executable bit.

### 4.5 Editing JSON configuration files

JSON supports no comments at all, in any form — adding a
comment-like line to `tide_constants.json` or `sensor_fields.json`
breaks parsing outright, and `tide.py` won't start. To temporarily
disable a value while keeping it around for easy restoration, rename
the key rather than try to comment it out:

```json
"_DISABLED_BREVO_SMTP_SERVER": "smtp-relay.brevo.com"
```

### 4.6 Local vs. cloud InfluxDB credentials

The InfluxDB **Cloud** token is deliberately the *same* value shared
across every station — all stations write to one org/bucket, and are
distinguished from each other by their own station tags within it,
not by separate cloud accounts. The **local** InfluxDB 3 Core admin
token is the opposite: necessarily unique per station, since each
runs its own independent local database with its own independent
authentication. Easy to reach for the wrong one when editing
`tide_constants.json`.

`influxdb3 create token --admin` prints the plaintext token exactly
once — copy it immediately; it's hashed server-side right after,
with no way to recover the original value later.
