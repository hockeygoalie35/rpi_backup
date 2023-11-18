# Setup Venv
echo "Creating Venv"
python3 -m venv rpi_backup_venv
source ./rpi_backup_venv/bin/activate
pip3 install -r ./requirements.txt
deactivate



# (Optional) Set up Cronjob to run at set interval
# Currently set to midnight on the first of each month, but change it for your needs
#                Mn Hr DoM Mon DoW
#(crontab -l ; echo "0  0 1 * * bash $HOME/rpi_backup/run.sh >> $HOME/rpi_backup/cron.log") | crontab -
#echo "# Log for Backups running through Cron" >> cron.log
#echo "---------------------------------------" >> cron.log



