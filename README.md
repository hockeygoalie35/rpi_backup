# rpi_backup
Raspberry Pi SD card live backups using RonR's Image-Utils to a specified network location


To install:

```bash
cd ~
git clone https://github.com/hockeygoalie35/rpi_backup
cd ~/rpi_backup/
bash install.sh
source ./rpi_backup_venv/bin activate
python backup.py -s -networkpath '//192.168.0.0/D/path' -user 'your_share_username' -password 'your_share_password'
