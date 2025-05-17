echo "The installation starts with preparation of the secure constants file,"
echo "which will be used to generate the encrypted constants file used during"
echo "tide station initialization."
read -p "Hit return to continue"

if test -f ~/bin/tide_constantsx.json; then
  echo "An encrypted tide_constants file already exists"
  read -p "do you want to decrypt and edit the file? Y/N: " answ
  if [ $answ == "Y" ]; then
    /usr/bin/python decrypt_constants.py
    nano tide_constants_clear.json
    echo "Do you want to overwrite the original file with the one"
    read -p "that was just edited? Y/N: " answ
    if [ $answ == "Y" ]; then
      /usr/bin/python encrypt_constants.py
      echo "encrypting and writing new constants file"
    fi
  fi
else
  cp tide_constants_template.json tide_constants_working.json
  nano tide_constants_working.json
fi