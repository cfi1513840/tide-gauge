#!/bin/bash
if test -e tide_constants.tmp; then
  confound=1
else
  confound=0
fi
if test -e /var/www/html/k1; then
  keyfound=1
else
  keyfound=0
fi
if test -e /var/www/html/tide_constants.json; then
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
echo " 12. Site specific configuration defined (see tide_constants_example.json and"
echo "     tide_template.env for examples and guidance on how to prepare these files."
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
echo "To prepare for installation, the environment variable file must be edited"
echo "  to include all installation-specific parameters. note that this will"
echo "  overwrite an existing tide.env file. This feature can also be"
echo "  used to allow practice installs to temporary directories for testing."
echo -e "\e[31m" 
read -p "Do you want to prepare a new tide.env file? Y/N: " answ
if [ $answ == "Y" ] || [ $answ == "y" ]; then
  cp -v tide_template.env tide_env.tmp
  nano tide_env.tmp
fi
if test -e tide_env.tmp && test -e tide.env; then
  echo "Warning: the next step will overwrite the existing tide.env file."
  read -p "Do you want to proceed with the overwrite? Y/N: " answ
  if [ $answ == "Y" ] || [ $answ == "y" ]; then
    mv -v tide_env.tmp tide.env
  fi
elif test -e tide_env.tmp; then
  mv -v tide_env.tmp tide.env
fi
echo
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
  sudo cp -v tide.service /lib/systemd/system/
fi
sudo systemctl enable tide
python makekeys.py
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
sudo cp -v k* ${htmldir}.
sudo chown www-data ${htmldir}k*
sudo chgrp www-data ${htmldir}k*
sudo chmod 660 ${htmldir}k*
echo
if [ $jsonfound == 1 ]; then
  echo -e "\e[31mAn encrypted tide_constants.json file already exists."
  echo "  If you proceed with the installation, all encryption keys"
  echo "  and the tide_constants.json file will be overwritten,"
  echo "  thus nullifyin any existing encrypted entries in the database."
  echo
  read -p "Do you want to proceed? Y/N: " answ
  if [ $answ != "Y" ] && [ $answ != "y" ]; then
    exit
  fi
fi
echo  
echo -e "\e[0mIf you would like to use your choice of an editor to prepare the"
echo "  constants file, you can exit this session and edit the file"
echo "  tide_constants.tmp at your leisure. When editing is complete,"
echo "  run the install script again to complete the setup process."
echo -e "\e[31m" 
read -p "Would you like to exit now to edit the tide_constants.tmp file? Y/N: " answ
if [ $answ == "Y" ] || [ $answ == "y" ]; then
  cp -v tide_constants_example.json tide_constants.tmp
  exit
fi
echo
echo -e "\e[0mThe constants file will be edited using the nano editor in"
echo "  clear text format to include all parameters associated with this"
echo "  tide station implementation. When editing is complete and the file has"
echo "  been saved, it will be encrypted and saved as ${htmldir}tide_constants.json."
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
    echo "encrypting and writing new constants file to /var/www/html/tide_constants.json"
    sudo mv -v tide_constants.tmp ${htmldir}tide_constants.json
  fi  
else
    cp -v tide_constants_example.json tide_constants.tmp
    nano tide_constants.tmp
    /usr/bin/python encrypt_constants.py tide_constants.tmp
    echo -e "\e[0mEncrypting and writing new constants file"
    sudo mv -v tide_constants.tmp ${htmldir}tide_constants.json  
fi  
sudo cp -v sqltides.db ${htmldir}tides.db
sudo cp -v tide.env ${htmldir}.
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