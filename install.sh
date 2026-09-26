#!/bin/bash
# install.sh works entirely on the files in the directory it is run
# from (workdir): the encryption keys, tide_constants.json, tide.env
# and sensor_fields.json. During an upgrade that is the new directory
# (e.g. ~/bin/tidegauge-new), which is later renamed to
# /home/tide/bin/tidegauge -- so any file missing from workdir now
# would also be missing after the rename. livedir is only consulted to
# detect that this is an upgrade of an existing station.
workdir="$(pwd -P)"
livedir=/home/tide/bin/tidegauge
livedir_real="$(readlink -f "$livedir" 2>/dev/null)"

# Upgrade check: running somewhere other than the live directory on a
# station that already has an installation. Every per-station file
# must have been copied into workdir first (Installation Manual, 3.15).
if [ "$workdir" != "$livedir_real" ] && test -e "${livedir}/tide_constants.json"; then
  missingfiles=""
  for f in tide_constants.json tide.env sensor_fields.json k1 k2 k3 ku; do
    if ! test -e "${workdir}/$f"; then
      missingfiles="$missingfiles $f"
    fi
  done
  if [ -n "$missingfiles" ]; then
    echo -e "\e[31mStopping: this looks like an upgrade (an existing installation"
    echo "  was found at ${livedir}), but these per-station files are"
    echo "  missing from ${workdir}:"
    echo
    echo "   ${missingfiles}"
    echo
    echo "  They would also be missing after this directory is renamed into"
    echo "  place. Copy them from the existing installation, keeping their"
    echo "  permissions, then run install.sh again:"
    echo
    echo "    cd ${livedir}"
    echo "    cp -p${missingfiles} ${workdir}/"
    echo -e "\e[0m"
    exit 1
  fi
  if ! test -e "${workdir}/.cloud_sync_watermark" && test -e "${livedir}/.cloud_sync_watermark"; then
    echo -e "\e[33mNote: .cloud_sync_watermark was not copied from ${livedir}."
    echo "  Without it, the first cloud sync after cutover re-sends this"
    echo "  station's entire local history to InfluxDB Cloud (harmless, but"
    echo "  slow). To avoid that:  cp -p ${livedir}/.cloud_sync_watermark ${workdir}/"
    echo -e "\e[0m"
  fi
fi

keycount=0
missingkeys=""
for k in k1 k2 k3 ku; do
  if test -e "${workdir}/$k"; then
    keycount=$((keycount + 1))
  else
    missingkeys="$missingkeys $k"
  fi
done
if [ $keycount -eq 4 ]; then
  keyfound=1
else
  keyfound=0
fi
if test -e "${workdir}/tide_constants.json"; then
  jsonfound=1
else
  jsonfound=0
fi

# Guard against silently regenerating encryption keys over existing
# encrypted data. makekeys.py (run further below when keyfound=0)
# creates a brand-new k1/k2/k3/ku set, which can never decrypt a
# tide_constants.json, or subscriber data in tides.db, that was
# encrypted with the original keys. So: if the full key set isn't in
# workdir but a tide_constants.json is, stop before changing anything.
# Also stop on a partial key set, which means some keys have been lost
# rather than never created.
if [ $keycount -lt 4 ]; then
  if [ $jsonfound -eq 1 ] || [ $keycount -gt 0 ]; then
    echo -e "\e[31mStopping: the encryption key file(s)${missingkeys} are missing"
    echo "  from ${workdir}, but existing encrypted data was found"
    if [ $keycount -gt 0 ]; then
      echo "  (a partial key set is present)."
    else
      echo "  (a tide_constants.json already exists)."
    fi
    echo
    echo "  Generating new keys here would make that data permanently"
    echo "  unreadable, so install.sh will not run makekeys.py."
    echo
    echo "  Copy the key files from the installation they belong with"
    echo "  (e.g. ~/bin/tidegauge-save after an upgrade), keeping their"
    echo "  permissions, then run install.sh again:"
    echo
    echo "    cp -p ~/bin/tidegauge-save/{k1,k2,k3,ku} ${workdir}/"
    echo
    echo "  If this really is a fresh install and the existing"
    echo "  tide_constants.json is a leftover, remove it first."
    echo -e "\e[0m"
    exit 1
  fi
fi
echo "Prerequisites for tide station installation:"
echo
echo " 1.  A phone number and email address to be used for receiving administrative alerts."
echo " 2.  A mail server account and address to be used for the issuance of tide station alerts."
echo " 3.  InfluxDB 3 Core installed locally, with a database named TideData."
echo " 4.  A TWILIO SMS account for the issuance of tide station alert messages."
echo " 5.  An OpenWeatherMap API key."
echo " 6.  A Cloudflare.com account with a domain to be used for the tide station web server."
echo " 7.  Cloudflared client application installed using the cloudflare.com wizard."
echo " 8.  Cloudflare.com tunnel and domain settings configured using the cloudflare.com wizard." 
echo " 9.  Apache2 installed and configured with CGI scripts enabled."
echo " 10. SQLite3 installed."
echo " 11. All necessary python modules installed."
echo " 12. Site specific configuration defined (see tide_constants.json.template and"
echo "     tide.env.template for examples and guidance on how to prepare these files."
echo " 13. If a LoRa-linked sensor is defined, the LoRa receiver must be plugged into"
echo "     the USB port specified by SERIAL_PORTS in tide.env."
echo " 14. If a Notecard-linked sensor is defined, a route must be configured in"
echo "     notehub.io to deliver its data to this station."
echo " 15. Grafana must be installed and configured, to provide access to"
echo "     this station's local InfluxDB database. install.sh does not set"
echo "     it up."
echo " 16. An InfluxDB Cloud account, for this station's cloud sync, with"
echo "     Organization: TideGauge, Bucket: TideData -- unlike the local"
echo "     database (item 3), InfluxDB Cloud genuinely needs both."
echo
while true; do
  read -p "Enter a prerequisite item number for further instruction, or press Enter to continue: " itemnum
  if [ -z "$itemnum" ]; then
    break
  fi
  tutorial="prereq_${itemnum}_tutorial.txt"
  if test -e "$tutorial"; then
    less "$tutorial"
  else
    echo "No additional tutorial available for item $itemnum yet."
  fi
  echo
done
read -p "Have all prerequisite steps been completed? Y/N: " answ
if [ $answ == "N" ] || [ $answ == "n" ]; then
  exit
fi
apvar=$(dpkg -l | grep apache2)
if [ -z "$apvar" ]; then
   echo -e "\e[0mApache2 is not yet installed -- installing it now."
   sudo apt-get update
   sudo apt-get install -y apache2
fi
sqlvar=$(dpkg -l | grep 'sqlite3 ')
if [ -z "$sqlvar" ]; then
   echo -e "\e[0mSQLite3 is not yet installed -- installing it now."
   sudo apt-get update
   sudo apt-get install -y sqlite3
fi
echo
if grep -q "+FollowSymLinks" /etc/apache2/conf-available/serve-cgi-bin.conf; then
  echo -e "\e[0mApache's cgi-bin configuration is already set to +FollowSymLinks; nothing to do."
else
  echo -e "\e[0mApache's default cgi-bin configuration uses +SymLinksIfOwnerMatch,"
  echo "  which refuses to follow a CGI symlink whose owner doesn't match its"
  echo "  target -- exactly the case for the root-owned CGI symlinks used"
  echo "  throughout this setup, which point to tide-owned files. Changing"
  echo "  this to +FollowSymLinks in serve-cgi-bin.conf resolves it."
  echo -e "\e[31m"
  read -p "Do you want to apply this Apache config fix now? Y/N: " answ
  if [ $answ == "Y" ] || [ $answ == "y" ]; then
    sudo sed -i 's/+SymLinksIfOwnerMatch/+FollowSymLinks/' /etc/apache2/conf-available/serve-cgi-bin.conf
    sudo systemctl reload apache2
    echo -e "\e[0mUpdated serve-cgi-bin.conf and reloaded Apache."
  fi
fi
echo
check_backup_safe() {
  local backup_file="$1"
  if test -e "$backup_file"; then
    echo -e "\e[31mWARNING: $backup_file already exists. This is your backup from"
    echo "  the last time this file was edited, and may be needed to roll back"
    echo "  to a previous stable version if this update doesn't go well."
    echo "  Overwriting it now would permanently lose that rollback copy."
    read -p "Overwrite the existing $backup_file anyway? Y/N: " answ
    if [ "$answ" != "Y" ] && [ "$answ" != "y" ]; then
      return 1
    fi
  fi
  return 0
}
# Decrypt the existing tide_constants.json to a clear-text scratch copy,
# edit it in nano, re-encrypt, and move it into place. The encrypted
# original is backed up first as tide_constants.json.dev.
edit_existing_constants() {
  if check_backup_safe tide_constants.json.dev; then
    cp -v tide_constants.json tide_constants.json.dev
    /usr/bin/python decrypt_constants.py tide_constants.json
    nano tide_constants_decrypted.tmp
    /usr/bin/python encrypt_constants.py tide_constants_decrypted.tmp
    echo "encrypting and writing updated constants file to ${workdir}/tide_constants.json"
    mv -v tide_constants.tmp tide_constants.json
    rm -f tide_constants_decrypted.tmp
  else
    echo -e "\e[0mSkipping the tide_constants.json update -- resolve the"
    echo "  existing backup situation, then run install.sh again."
  fi
}
pyvenv=$(dpkg -l | grep python3-venv)
if [ -z "$pyvenv" ]; then
   echo -e "\e[0mpython3-venv is not yet installed -- installing it now."
   sudo apt-get update
   sudo apt-get install -y python3-venv
fi
if [ -d /home/tide/.tidenv ]; then
  echo -e "\e[0mPython virtual environment already exists at /home/tide/.tidenv."
else
  echo -e "\e[0mCreating the Python virtual environment at /home/tide/.tidenv..."
  python3 -m venv /home/tide/.tidenv
fi
echo -e "\e[0mInstalling/updating required Python packages..."
/home/tide/.tidenv/bin/pip install -r requirements.txt
echo
echo -e "\e[0mSetting up tide gauge environment for ${USER}"
echo
echo "Adding ${USER} to the www-data group and vice-versa"
sudo usermod -a -G "www-data" "$USER"
sudo usermod -a -G "$USER" "www-data"
echo
echo "Changing ownership and permission for HTML directory to www-data"
echo
sudo chown www-data /var/www
sudo chgrp www-data /var/www
sudo chown www-data /var/www/html
sudo chgrp www-data /var/www/html
sudo chmod 770 /var/www
sudo chmod 770 /var/www/html
if test -e tide.env; then
  echo -e "\e[0mChecking the existing tide.env against tide.env.template for"
  echo "  missing or obsolete parameters..."
  /usr/bin/python check_config_drift.py tide.env tide.env.template env | tee /tmp/tide_env_drift_report.txt
  drift_status=${PIPESTATUS[0]}
  if [ $drift_status -eq 0 ]; then
    echo -e "\e[0mtide.env is up to date with the template."
    echo "  (If it was copied from another station, its station-specific"
    echo "  values may still need changing.)"
    read -p "Would you like to edit tide.env anyway? Y/N: " answ
    if [ "$answ" == "Y" ] || [ "$answ" == "y" ]; then
      if check_backup_safe tide.env.dev; then
        cp -v tide.env tide.env.dev
        nano tide.env
      fi
    fi
  else
    echo
    echo -e "\e[0mThe existing tide.env needs updating, per the report above."
    echo "  It will now open in nano so you can add any missing parameters"
    echo "  and remove any obsolete ones. The current file will be backed up"
    echo "  first as tide.env.dev, in case anything needs to be reverted."
    echo "  The report above is also saved to /tmp/tide_env_drift_report.txt"
    echo "  -- nano will replace this screen, so open a second terminal or"
    echo "  SSH session and 'cat' or 'less' that file if you'd like to keep"
    echo "  it visible for reference while editing."
    echo -e "\e[31m"
    read -p "Hit return to continue: " go
    if check_backup_safe tide.env.dev; then
      cp -v tide.env tide.env.dev
      nano tide.env
    else
      echo -e "\e[0mSkipping the tide.env update -- resolve the existing backup"
      echo "  situation, then run install.sh again."
    fi
  fi
else
  echo "To prepare for installation, the environment variable file must be"
  echo "  edited to include all installation-specific parameters."
  echo -e "\e[31m"
  read -p "Hit return to continue: " go
  cp -v tide.env.template tide_env.tmp
  nano tide_env.tmp
  mv -v tide_env.tmp tide.env
fi
echo
if test -e /etc/systemd/system/tide.service; then
  echo -e "\e[0mtide.service already exists; leaving it as-is."
else
  echo -e "\e[0mThe installation proceeds with the generation of a systemd"
  echo "  service file for starting the tide.py process at boot time."
  echo "  Encryption keys are then generated and a clear-text version of the"
  echo "  the constants file is prepared, which is used for generation of the"
  echo "  encrypted tide_constants.json file."
  echo
  echo "Please provide edits to local parameters for the systemd service file"
  read -p "Hit return to continue: " answ
  cp -v tide.service.template tide.service.tmp
  nano tide.service.tmp
  echo
  read -p "Do you want move the edited service file to the systemd directory? Y/N: " answ
  if [ $answ == "Y" ] || [ $answ == "y" ]; then
    sudo mv -v tide.service.tmp /etc/systemd/system/tide.service
  fi
fi
sudo systemctl enable tide
if [ $keyfound -eq 0 ]; then
  python makekeys.py
fi
# Key file permissions, enforced on every run so existing stations
# (and keys copied in during an upgrade) are brought into line too.
# k1/k2/k3 are read by the CGI scripts through tidecrypto.py, running
# as www-data, which is a member of the tide group -- so owner
# read/write plus group read (640). ku is only ever read by tide.py and
# the install-time scripts, running as tide -- so owner only (600).
if test -e k1 && test -e k2 && test -e k3 && test -e ku; then
  echo -e "\e[0mSetting encryption key file permissions (k1-k3: 640, ku: 600)"
  sudo chown tide:tide k1 k2 k3 ku
  sudo chmod 640 k1 k2 k3
  sudo chmod 600 ku
fi
echo
grep "HTML_DIRECTORY" tide.env > grep.tmp
vari="$(cat grep.tmp)"
eval htmldir=${vari#*=}
grep "CGI_DIRECTORY" tide.env > grep.tmp
vari="$(cat grep.tmp)"
eval cgidir=${vari#*=}
echo "HTML files will be copied to ${htmldir}"
echo "CGI files will be copied to $cgidir"
echo
if [ $jsonfound == 1 ]; then
  echo -e "\e[0mChecking the existing ${workdir}/tide_constants.json"
  echo "  against tide_constants.json.template for missing or obsolete"
  echo "  parameters..."
  /usr/bin/python check_config_drift.py tide_constants.json tide_constants.json.template json | tee /tmp/tide_constants_drift_report.txt
  drift_status=${PIPESTATUS[0]}
  if [ $drift_status -eq 0 ]; then
    echo -e "\e[0mtide_constants.json is up to date with the template."
    echo "  (If it was copied from another station, its station-specific"
    echo "  values may still need changing.)"
    read -p "Would you like to edit tide_constants.json anyway? Y/N: " answ
    if [ "$answ" == "Y" ] || [ "$answ" == "y" ]; then
      edit_existing_constants
    fi
  else
    echo
    echo -e "\e[31mThe existing tide_constants.json needs updating, per the report"
    echo "  above. Since it's encrypted, this requires decrypting it to a"
    echo "  clear-text scratch copy for editing, then re-encrypting. The"
    echo "  original encrypted file will be backed up first as"
    echo "  tide_constants.json.dev, in case anything needs to be reverted."
    echo "  The report above is also saved to"
    echo "  /tmp/tide_constants_drift_report.txt -- nano will replace this"
    echo "  screen, so open a second terminal or SSH session and 'cat' or"
    echo "  'less' that file if you'd like to keep it visible for reference"
    echo "  while editing."
    echo -e "\e[31m"
    read -p "Hit return to continue: " go
    edit_existing_constants
  fi
else
  if test -e tide_constants.tmp; then
    echo "A clear text version of the tide_constants.tmp file already exists."
    echo -e "\e[31m"
    cat tide_constants.tmp
    read -p "Do you want to use it to create the encrypted constants file? Y/N: " answ
    if [ $answ == "Y" ] || [ $answ == "y" ]; then
      /usr/bin/python encrypt_constants.py tide_constants.tmp
      echo "encrypting and writing new constants file to ${workdir}/tide_constants.json"
      mv -v tide_constants.tmp tide_constants.json
    fi  
  else
    echo -e "\e[0mIf you would like to use your choice of an editor to prepare the"
    echo "  constants file, you can exit this session and edit the file"
    echo "  tide_constants.tmp at your leisure. When editing is complete,"
    echo "  run the install script again to complete the setup process."
    echo -e "\e[31m" 
    read -p "Would you like to exit now to edit the tide_constants.tmp file? Y/N: " answ
    if [ $answ == "Y" ] || [ $answ == "y" ]; then
      cp -v tide_constants.json.template tide_constants.tmp
      exit
    fi
    echo
    echo -e "\e[0mThe constants file will be edited using the nano editor in"
    echo "  clear text format to include all parameters associated with this"
    echo "  tide station implementation. When editing is complete and the file has"
    echo "  been saved, it will be encrypted and saved as"
    echo "  ${workdir}/tide_constants.json."
    echo "  Note that no clear text versions of the edited file will be saved."
    echo -e "\e[31m" 
    read -p "Hit return to continue: " go
    cp -v tide_constants.json.template tide_constants.tmp
    nano tide_constants.tmp
    # encrypt_constants.py writes its encrypted output to
    # tide_constants.tmp, replacing the clear-text copy just edited
    /usr/bin/python encrypt_constants.py tide_constants.tmp
    echo "encrypting and writing new constants file to ${workdir}/tide_constants.json"
    mv -v tide_constants.tmp tide_constants.json
    echo -e "\e[0m "
  fi
fi
if test -e ${htmldir}tides.db; then
  echo -e "\e[0mSqlite3 database file already exists; leaving it as-is."
else
  sudo cp -v sqltides.db ${htmldir}tides.db
  sudo chown www-data ${htmldir}tides.db
  sudo chgrp www-data ${htmldir}tides.db
  sudo chmod 660 ${htmldir}tides.db
  echo
  echo -e "\e[0mThis is a freshly-installed database. Before running tide.py, the"
  echo "  iparams table needs the station's sensors configured (which are"
  echo "  installed, their link type and calibration, and which one serves"
  echo "  as the primary station display)."
  echo -e "\e[31m"
  /usr/bin/python configure_iparams.py ${htmldir}tides.db
fi
if test -e sensor_fields.json; then
  echo -e "\e[0mChecking the existing sensor_fields.json against"
  echo "  sensor_fields.json.template for missing or obsolete parameters..."
  /usr/bin/python check_config_drift.py sensor_fields.json sensor_fields.json.template json
  if [ $? -eq 0 ]; then
    echo -e "\e[0msensor_fields.json is up to date -- nothing to do."
  else
    echo
    echo -e "\e[0mThe existing sensor_fields.json differs from the template, per"
    echo "  the report above. Since it's purely structural (no site-specific"
    echo "  data), it will simply be replaced with the current template. The"
    echo "  current file will be backed up first as sensor_fields.json.dev."
    if check_backup_safe sensor_fields.json.dev; then
      cp -v sensor_fields.json sensor_fields.json.dev
      cp -v sensor_fields.json.template sensor_fields.json
    else
      echo -e "\e[0mSkipping the sensor_fields.json update -- resolve the"
      echo "  existing backup situation, then run install.sh again."
    fi
  fi
else
  cp -v sensor_fields.json.template sensor_fields.json
fi
if test -e ${htmldir}webimage.png; then
  echo -e "\e[0m${htmldir}webimage.png already exists; leaving it as-is."
else
  sudo cp -v webimage.png.template ${htmldir}webimage.png
  sudo chmod 644 ${htmldir}webimage.png
  echo -e "\e[0mA generic placeholder image was installed as webimage.png --"
  echo "  replace it with a photo of this station's actual location when"
  echo "  convenient."
fi
if test -e ${htmldir}webinfo.txt; then
  echo -e "\e[0m${htmldir}webinfo.txt already exists; leaving it as-is."
else
  sudo cp -v webinfo.txt.template ${htmldir}webinfo.txt
  sudo chmod 644 ${htmldir}webinfo.txt
  echo -e "\e[0mA generic placeholder description was installed as webinfo.txt --"
  echo "  edit it to describe this station when convenient."
fi
echo
echo -e "\e[0mChecking mailspool directories..."
ensure_dir() {
  local dir="$1" mode="$2"
  if [ -d "$dir" ]; then
    echo "OK (exists): $dir"
  else
    echo "MISSING -- creating: $dir"
    sudo mkdir -p "$dir"
  fi
  sudo chown tide:tide "$dir"
  sudo chmod "$mode" "$dir"
}
ensure_dir "${htmldir}mailspool" 770
ensure_dir "${htmldir}mailspool/failed" 700
echo
echo -e "\e[0mChecking Apache protection for files in the web root..."
# tide.env (symlinked here for the CGI scripts), tides.db and the mail
# spool all live in the web root, so without this Apache would serve
# them to anyone who asked. The CGI scripts and tide.py read them
# straight from disk and are unaffected. The rule is written for this
# station's HTML_DIRECTORY and only replaced if it has changed.
protect_conf=/etc/apache2/conf-available/tide-protect.conf
cat > /tmp/tide-protect.conf <<PROTECT_EOF
# Installed by install.sh. Keeps station configuration and data files
# that live in the web root (tide.env, tides.db, the mail spool, logs)
# from being served over HTTP. The CGI scripts and tide.py read these
# files directly from disk and are unaffected.
<Directory "${htmldir}">
    <FilesMatch "^(tide\.env|.*\.(json|db|db-journal|db-wal|db-shm|log|tmp|dev|bak|gz))\$">
        Require all denied
    </FilesMatch>
</Directory>
<Directory "${htmldir}mailspool/">
    Require all denied
</Directory>
PROTECT_EOF
if test -e $protect_conf && cmp -s /tmp/tide-protect.conf $protect_conf; then
  echo "OK (already installed): $protect_conf"
else
  sudo cp -v /tmp/tide-protect.conf $protect_conf
fi
rm -f /tmp/tide-protect.conf
sudo a2enconf -q tide-protect
if sudo apache2ctl configtest 2>&1 | grep -q "Syntax OK"; then
  sudo systemctl reload apache2
else
  echo -e "\e[31mWARNING: Apache configuration test failed -- not reloading."
  echo "  Run 'sudo apache2ctl configtest' to see the error.\e[0m"
fi
echo
echo -e "\e[0mChecking symlinks..."
ensure_symlink() {
  local target="$1" link="$2"
  if [ ! -e "$target" ]; then
    echo "WARNING: symlink target does not exist, skipping: $target"
    return
  fi
  if [ -L "$link" ]; then
    current_target="$(readlink -f "$link")"
    real_target="$(readlink -f "$target")"
    if [ "$current_target" == "$real_target" ]; then
      echo "OK (correct symlink): $link -> $target"
      return
    else
      echo "WRONG TARGET -- relinking: $link (was -> $current_target)"
      sudo rm -f "$link"
      sudo ln -s "$target" "$link"
    fi
  elif [ -e "$link" ]; then
    if cmp -s "$target" "$link"; then
      echo "REAL FILE at link path, but content matches target exactly -- replacing with a symlink: $link"
      sudo rm -f "$link"
      sudo ln -s "$target" "$link"
    else
      echo "REAL FILE at link path with DIFFERENT content -- NOT touching, check manually: $link"
      return
    fi
  else
    echo "MISSING -- creating: $link -> $target"
    sudo ln -s "$target" "$link"
  fi
  sudo chown -h tide:tide "$link"
}
ensure_symlink "$(pwd)/tidecrypto.py" "${cgidir}tidecrypto.py"
ensure_symlink "$(pwd)/tideplot.py"   "${cgidir}tideplot.cgi"
ensure_symlink "$(pwd)/tide.env"      "${htmldir}tide.env"
echo
echo -e "\e[0mCopying tracked files to their destinations..."
copy_tracked() {
  local pattern="$1" dest="$2" perms="$3"
  git ls-files "$pattern" | while read -r f; do
    echo "  $f -> $dest"
    sudo cp -v "$f" "$dest"
    sudo chmod "$perms" "$dest$(basename "$f")"
  done
}
copy_tracked '*.cgi'  "$cgidir" 755
copy_tracked '*.html' "$htmldir" 644
copy_tracked '*.pdf'  "$htmldir" 644
if [ -e "${htmldir}tide.html" ] && [ "$(stat -c '%U' "${htmldir}tide.html")" != "tide" ]; then
  echo -e "\e[0m${htmldir}tide.html is owned by $(stat -c '%U' "${htmldir}tide.html"),"
  echo "  not tide -- likely leftover from a version of install.sh that"
  echo "  incorrectly copied index.html over it. tide.py runs as the tide"
  echo "  user and needs to own this file to regenerate it. Fixing."
  sudo chown tide:tide "${htmldir}tide.html"
  sudo chmod 644 "${htmldir}tide.html"
fi
echo
echo -e "\e[0mThe tide plot page (tideplot.html) needs to be regenerated"
echo "  periodically to stay current. This is done via a cron job that runs"
echo "  tideplot.py at 1, 21, and 41 minutes past the hour."
echo -e "\e[31m"
cronline="1,21,41 * * * * /home/tide/.tidenv/bin/python3 /home/tide/bin/tidegauge/tideplot.py"
if crontab -l 2>/dev/null | grep -qF "$cronline"; then
  echo -e "\e[0mA matching tideplot.py cron entry already exists; skipping."
else
  read -p "Do you want to add the tideplot.py cron entry now? Y/N: " answ
  if [ $answ == "Y" ] || [ $answ == "y" ]; then
    (crontab -l 2>/dev/null; echo "$cronline") | crontab -
    echo -e "\e[0mAdded tideplot.py to crontab."
  fi
fi