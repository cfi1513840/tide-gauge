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
echo 
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
echo -e "\e[0mSetting up tide gauge environment for ${USER}"
echo
echo "Adding ${USER} to the www-data group"
sudo usermod -a -G "www-data" "$USER"
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
    echo "  and remove any obsolete ones."
    echo -e "\e[31m"
    read -p "Hit return to continue: " go
    nano tide.env
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
if test -e tide.service; then
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
  nano tide.service
  echo
  read -p "Do you want copy the service file to the systemd directory? Y/N: " answ
  if [ $answ == "Y" ] || [ $answ == "y" ]; then
    sudo cp -v tide.service /etc/systemd/system/
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
    cp -v /home/tide/bin/tidegauge/tide_constants.json tide_constants.json.dev
    /usr/bin/python decrypt_constants.py /home/tide/bin/tidegauge/tide_constants.json
    nano tide_constants_decrypted.tmp
    /usr/bin/python encrypt_constants.py tide_constants_decrypted.tmp
    echo "encrypting and writing updated constants file to /home/tide/bin/tidegauge/tide_constants.json"
    mv -v tide_constants.tmp tide_constants.json
    rm -f tide_constants_decrypted.tmp
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
  if test -e tide_constants.tmp; then
    echo "A clear text version of the tide_constants.tmp file already exists."
    echo -e "\e[31m"
    read -p "Do you want to use it to create the encrypted constants file? Y/N: " answ
    if [ $answ == "Y" ] || [ $answ == "y" ]; then
      /usr/bin/python encrypt_constants.py tide_constants.tmp
      echo "encrypting and writing new constants file to /home/tide/bin/tidegauge/tide_constants.json"
      mv -v tide_constants.tmp tide_constants.json
    fi  
  else
    cp -v tide_constants.json.template tide_constants.tmp
    nano tide_constants.tmp
    /usr/bin/python encrypt_constants.py tide_constants.tmp
    echo -e "\e[0mEncrypting and writing new constants file"
    mv -v tide_constants.tmp tide_constants.json  
  fi  
fi
sudo cp -v sqltides.db ${htmldir}tides.db
if test -e sensor_fields.json; then
  echo -e "\e[0msensor_fields.json already exists; leaving it as-is."
else
  cp -v sensor_fields.json.template sensor_fields.json
fi
sudo cp -v *.png ${htmldir}.
sudo cp -v index.html ${htmldir}tide.html
sudo cp -v *.html ${htmldir}.
sudo cp -v *.cgi ${cgidir}.
sudo chown www-data ${htmldir}*
sudo chgrp www-data ${htmldir}*
sudo chmod 660 ${htmldir}*
sudo chown www-data ${cgidir}*
sudo chgrp www-data ${cgidir}*
sudo chmod 770 ${cgidir}*
echo
echo -e "\e[0mThe tide plot page (tideplot.html) needs to be regenerated"
echo "  periodically to stay current. This is done via a cron job that runs"
echo "  tideplot.py at 1, 21, and 41 minutes past the hour."
echo -e "\e[31m"
read -p "Do you want to add the tideplot.py cron entry now? Y/N: " answ
if [ $answ == "Y" ] || [ $answ == "y" ]; then
  cronline="1,21,41 * * * * /home/tide/.tidenv/bin/python3 /home/tide/bin/tidegauge/tideplot.py"
  if crontab -l 2>/dev/null | grep -qF "$cronline"; then
    echo -e "\e[0mA matching tideplot.py cron entry already exists; skipping."
  else
    (crontab -l 2>/dev/null; echo "$cronline") | crontab -
    echo -e "\e[0mAdded tideplot.py to crontab."
  fi
fi