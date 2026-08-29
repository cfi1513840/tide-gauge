#!/bin/bash
if test -e /home/tide/bin/tidegauge/k1; then
  keyfound=1
else
  keyfound=0
fi
if test -e /home/tide/bin/tidegauge/tide_constants.json; then
  jsonfound=1
else
  jsonfound=0
fi
echo "Prerequisites for tide station installation:"
echo
echo " 1.  A phone number and email address to be used for receiving administrative alerts."
echo " 2.  A mail server account and address to be used for the issuance of tide station alerts."
echo " 3.  InfluxDB installed and configured with Organization: TideGauge, Bucket: TideData."
echo " 4.  A TWILIO SMS account for the issuance of tide station alert messages."
echo " 5.  One of the following API keys: WeatherUndergroud, OpenWeatherMap, or WeatherLink."
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
   echo "Apache2 and all other supporting modules must be"
   echo " installed prior to running the install.sh script"
   exit
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
pyvenv=$(dpkg -l | grep python3-venv)
if [ -z "$pyvenv" ]; then
   echo "python3-venv must be installed prior to running the install.sh script"
   echo "  (apt install python3-venv)"
   exit
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
  /usr/bin/python check_config_drift.py tide.env tide.env.template env
  if [ $? -eq 0 ]; then
    echo -e "\e[0mtide.env is up to date -- nothing to do."
  else
    echo
    echo -e "\e[0mThe existing tide.env needs updating, per the report above."
    echo "  It will now open in nano so you can add any missing parameters"
    echo "  and remove any obsolete ones. The current file will be backed up"
    echo "  first as tide.env.dev, in case anything needs to be reverted."
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
  echo -e "\e[0mChecking the existing /home/tide/bin/tidegauge/tide_constants.json"
  echo "  against tide_constants.json.template for missing or obsolete"
  echo "  parameters..."
  /usr/bin/python check_config_drift.py /home/tide/bin/tidegauge/tide_constants.json tide_constants.json.template json
  if [ $? -eq 0 ]; then
    echo -e "\e[0mtide_constants.json is up to date -- nothing to do."
  else
    echo
    echo -e "\e[31mThe existing tide_constants.json needs updating, per the report"
    echo "  above. Since it's encrypted, this requires decrypting it to a"
    echo "  clear-text scratch copy for editing, then re-encrypting. The"
    echo "  original encrypted file will be backed up first as"
    echo "  tide_constants.json.dev, in case anything needs to be reverted."
    echo -e "\e[31m"
    read -p "Hit return to continue: " go
    if check_backup_safe tide_constants.json.dev; then
      cp -v /home/tide/bin/tidegauge/tide_constants.json tide_constants.json.dev
      /usr/bin/python decrypt_constants.py /home/tide/bin/tidegauge/tide_constants.json
      nano tide_constants_decrypted.tmp
      /usr/bin/python encrypt_constants.py tide_constants_decrypted.tmp
      echo "encrypting and writing updated constants file to /home/tide/bin/tidegauge/tide_constants.json"
      mv -v tide_constants.tmp tide_constants.json
      rm -f tide_constants_decrypted.tmp
    else
      echo -e "\e[0mSkipping the tide_constants.json update -- resolve the"
      echo "  existing backup situation, then run install.sh again."
    fi
  fi
else
  if test -e tide_constants.tmp; then
    echo "A clear text version of the tide_constants.tmp file already exists."
    echo -e "\e[31m"
    cat tide_constants.tmp
    read -p "Do you want to use it to create the encrypted constants file? Y/N: " answ
    if [ $answ == "Y" ] || [ $answ == "y" ]; then
      /usr/bin/python encrypt_constants.py tide_constants.tmp
      echo "encrypting and writing new constants file to /home/tide/bin/tidegauge/tide_constants.json"
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
    echo "  /home/tide/bin/tidegauge/tide_constants.json."
    echo "  Note that no clear text versions of the edited file will be saved."
    echo -e "\e[31m" 
    read -p "Hit return to continue: " go
    echo
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
sudo cp -v index.html ${htmldir}tide.html
sudo chmod 644 ${htmldir}tide.html
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