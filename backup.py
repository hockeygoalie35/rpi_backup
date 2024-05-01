import os
import sys
import subprocess
import argparse
from pi_functions import create_cifs_drive
import time
from datetime import datetime
import requests
import time


# TODO: Better error handling, unmount drive and restart containers on error.
# TODO: ini file for ntfy and setup stuff
# TODO: incremental backups


import prettylogging

NOW = datetime.strftime(datetime.now(), "%b-%d-%Y-%H-%M-%S")
LOGGER_NAME = 'rpi_backup'
LOG_OUTPUT_PATH = './logs/Backup-'+NOW+'.log'
VERSION = '1.8'
ntfyServerTopic="http://docker:9191/rpi_backup"
ntfyUserToken="tk_98vch00s7fjntopamcfed95f2s77q"

log = prettylogging.init_logging(LOGGER_NAME, VERSION, log_file_path=LOG_OUTPUT_PATH, info_color="GREEN")

class SendNtfyError():
    def __init__(self,host_name,error):
        ntfy_notify(ntfyServerTopic,ntfyUserToken,f"Backup of {host_name} failed:\n{error}")

class DeinitBackup():
    def __init__(self):
        pass

class RpiBackup():
    def __init__(self):
        self.working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))  # working dir
        self.hostname = None
        self.credentials_dict = None

        self.argument_parsing()  # parse the passed arguments from the CLI
        if self.argument.setup:
            self.setup()  # Run the setup script to set up auto-mounting
        if self.argument.runbackup:
            self.run_backup()  # Run a backup
        if self.argument.enablecron:
            self.enable_cron()  # Enable a cronjob to run at a set interval TODO: (place behind ini)
        if self.argument.disablecron:
            self.disable_cron()  # Disable cronjob
        if self.argument.uninstall:
            answer = input("Are you sure you want to uninstall? y/n")
            if answer == "y":
                self.wipe_rpi_backup()  # Remove application

    def argument_parsing(self):
        parser = argparse.ArgumentParser(description="CLI Commands")
        parser.add_argument("-s", "--setup",help="initial setup, supply path, username, password and uid if user is not pi",required=False, default=False, action='store_true')
        parser.add_argument("-rb", "--runbackup", help="run full backup", required=False, default=False, action='store_true')
        parser.add_argument("-ec", "--enablecron", help="enables cronjob to schedule backup", required=False,default=False, action='store_true')
        parser.add_argument("-dc", "--disablecron", help="enables cronjob to schedule backup", required=False,default=False, action='store_true')
        parser.add_argument("-np", "--networkpath", help="path to network share", required=False, default=False)
        parser.add_argument("-u", "--username", help="network share username", required=False, default=False)
        parser.add_argument("-p", "--password", help="network share password", required=False, default=False)
        parser.add_argument("-uid", help="user,run whoami to get answer", required=False, default=False)
        parser.add_argument("-uninstall", help="uninstalls network drive from fstab", required=False, default=False, action='store_true')
        parser.add_argument("-ri", "--runincremental", help="run incremental backup", required=False, default=False, action='store_true')
        self.argument = parser.parse_args()

    def setup(self):
        self.credentials_dict = {
            "-networkpath": self.argument.networkpath,
            "-username": self.argument.username,
            "-password": self.argument.password,
            "-uid": self.argument.uid}
        mnt_path = '/mnt/backups'
        log.info('Attempting setup with supplied credentials...')

        self.check_networks_drive_credentials()
        create_cifs_drive(self.credentials_dict['-networkpath'], mnt_path, self.credentials_dict['-username'],
                          self.credentials_dict['-password'])
        log.info('Setup Complete!')

    def check_networks_drive_credentials(self):
        # let user know if they're missing a flag
        for cred in self.credentials_dict:
            if cred != "-uid":  # ignore uid, it's optional
                if self.credentials_dict[cred] is False:
                    log.error(f'missing {cred} argument')
                    exit(1)

    def run_backup(self, backup_type = None):
        log.info('Starting Backup...')
        if backup_type is None:
            log.warning(f'Backup type not set, assuming full.')

        # Ensure Image-Utils was downloaded and ask user to do so if not
        if os.path.exists(f'{self.working_dir}/image-utils/image-backup') is False:
            log.error("Please Download Image-Utils and place in this folder /rpi_backup/image-utils\nhttps://forums.raspberrypi.com/viewtopic.php?t=332000")
            ntfy_notify(ntfyServerTopic, ntfyUserToken, f"Backup of {self.hostname} failed, see logs for details.")
            exit(1)
        # Backup Settings
        filesize_buffer = 5000
        incremental_size = 0

        log.info("Backup Starting....")

        # Mount network drive
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon
        os.system("sudo mount /mnt/backups")
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if '/mnt/backups' in mount_list:
            log.info("Backup Drive Mounted")
        else:
            log.error("Mount Error! See above error.")
            log.error("If first time running, re-run with -s flag instead to do initial setup")
            ntfy_notify(ntfyServerTopic, ntfyUserToken, f"Backup of {self.hostname} failed, see logs for details.")
            exit(1)

        # Get Hostname & see if directory exists
        self.hostname = str(subprocess.check_output("hostname | cut -d\' \' -f1", shell=True).decode('utf-8')).replace("\n", "")
        if os.path.exists(f'/mnt/backups/{self.hostname}') is False:
            log.info(f"Creating Directory {self.hostname}")
            os.system(f'sudo mkdir /mnt/backups/{self.hostname}')

        # Get Filesystem size
        cmd = "df -h /|awk '/\/dev\//{printf(\"%.2f\",$3);}'"
        file_size_gb = str(subprocess.check_output(cmd, shell=True).decode('utf-8')).replace("\n", "")
        file_size_mb = float(file_size_gb) * 1000
        log.debug(f"File System Size: {file_size_mb}MB")

        # Build up back-up args
        filesystem_size = int(file_size_mb + filesize_buffer)

        # Get uid
        uid = str(subprocess.check_output('whoami', shell=True).decode('utf-8')).replace("\n", "")
        log.debug(f'Identified user as {uid}')

        # Disable Docker
        log.debug("Disabling Docker")
        os.system("sudo docker stop $(sudo docker ps -a -q)")
        os.system("sudo systemctl disable docker.socket --now")
        os.system("sudo systemctl disable docker --now")
        log.info("Docker disabled (Temporarily)")

        log.debug("Beginning image-backup")
        # # backup string
        os.system(f"sudo bash /home/{uid}/rpi_backup/image-utils/image-backup -i /mnt/backups/{self.hostname}/{self.hostname}_$(date +%d-%b-%y_%T).img,{filesystem_size},{incremental_size}")
        log.info("image-backup Finishing")
        # Unmount network drive
        os.system("sudo umount /mnt/backups")
        log.info("Backup Drive Unmounted")

        # Enable Docker
        os.system("sudo systemctl enable docker --now")
        os.system("sudo systemctl enable docker.socket --now")
        os.system("sudo docker start wireguard_pia portainer")
        # Enable and fill this if you need containers to start in an order I.e. a vpn container.
        time.sleep(5)  # You can duplicate & change the time however many dependencies you have
        os.system("sudo docker start $(sudo docker ps -a -q)")  # restart all rest of containers

        log.info("Docker Re-enabled")

        log.info("Backup Completed!")
        notify_datetime = datetime.strftime(datetime.now(), '%b-%d-%Y @ %I:%M%p')
        time.sleep(30)  # Give it time for ntfy to start back up
        ntfy_notify(ntfyServerTopic, ntfyUserToken, f"Completed Backup for {self.hostname} on {notify_datetime}")

    def enable_cron(self):  # TODO Test this func to make sure it works, make it more configurable
        os.system(f'(crontab -l ; echo "0 0 1 * * {self.working_dir}/rpi_backup_venv/bin/python {self.working_dir}/backup.py -rb>> {self.working_dir}/logs/cron.log") | crontab -')
        os.system(f'echo "# Log for Backups running through Cron" > {self.working_dir}/logs/cron.log')
        os.system(f'echo "---------------------------------------" >> {self.working_dir}/logs/cron.log')
        log.info("cronjob enabled")

    def disable_cron(self):
        os.system(f"crontab -l | grep -v '{self.working_dir}/rpi_backup_venv/bin/python {self.working_dir}/backup.py -rb'  | crontab -")
        log.info("cronjob disabled")

    def wipe_rpi_backup(self): # wipes rpi_backups to test deployment
        log.info('Unmounting drive')
        os.system(f"sudo umount /mnt/backups")  # unmount backups
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if '/mnt/backups' not in mount_list:
            log.info("Backup Drive Unmounted Successfully")
        else:
            log.error("Backup Drive Could Not Be Unmounted")
            exit(1)
        os.system(f"crontab -l | grep -v '{self.working_dir}/rpi_backup_venv/bin/python {self.working_dir}/backup.py -rb'  | crontab -")
        log.info("cronjob disabled")
        os.system('sudo rm -r /mnt/backups') # delete backup location
        log.info("deleted /mnt/backups")
        os.system(f"sudo sed -i.bak '/backups/d' /etc/fstab")  # remove the line from Fstab
        log.info("Removed line from FSTAB")
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon
        print('rpi_backups uninstalled, go home and run "rm -r ./rpi_backup" to delete folder')

def ntfy_notify(server_plus_topic, token, message):  # Send Notification to ntfy topic
    log.info('Attempting ntfy notification')
    try:
        requests.post(server_plus_topic,
                      data=message.encode(encoding='utf-8'),
                      headers={
                          "Authorization": f"Bearer {token}"}
                      )
        log.info('ntfy notification sent successfully')
    except Exception as e:
        if "Failed to resolve" in str(e):
            log.error("ntfy ERROR: Check if server and user token correct in extended.conf")
        else:
            log.error("NTFY ERROR: " + str(e))


if __name__ == '__main__':
    a=RpiBackup()
    #ntfy_notify(ntfyServerTopic,ntfyUserToken,"ping")
