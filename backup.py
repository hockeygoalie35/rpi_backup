import os
import sys
import subprocess
from colorama import init, Fore
import datetime
import json
import traceback
import argparse
from pi_functions import *





class rpi_backup():
    def __init__(self):
        self.script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
        init(autoreset=True)  # Set autoreset to True else color would be forwarded to the next print statement
        self.argument_parsing()
        if self.argument.setup:
            credentials_dict = {
                "-networkpath": self.argument.networkpath,
                "-username": self.argument.username,
                "-password": self.argument.password,
                "-uid": self.argument.uid}
            mnt_path = '/mnt/backups'
            print(Fore.GREEN + '\n\n########|STARTING SETUP|#########')
            self.check_networks_drive_credentials(credentials_dict)
            create_cifs_drive(credentials_dict['-networkpath'], mnt_path, credentials_dict['-username'], credentials_dict['-password'])
            print(Fore.GREEN + '#########|SETUP Complete|#########\n\n')
        if self.argument.runbackup:
            print(Fore.GREEN + '\n\n########|STARTING BACKUP|#########')
            self.run_backup()
            print(Fore.GREEN + '########|BACKUP COMPLETE|#########')
        if self.argument.enablecron:
            self.enable_cron()
        if self.argument.disablecron:
            self.disable_cron()
        if self.argument.uninstall:
            answer = input("Are you sure you want to uninstall? y/n")
            if answer == "y":
                self.wipe_rpi_backup()

    def argument_parsing(self):
        parser = argparse.ArgumentParser(description="CLI Commands")
        parser.add_argument("-s", "--setup",help="initial setup, supply path, username, password and uid if user is not pi",required=False, default=False, action='store_true')
        parser.add_argument("-rb", "--runbackup", help="run backup", required=False, default=False, action='store_true')
        parser.add_argument("-ec", "--enablecron", help="enables cronjob to schedule backup", required=False,default=False, action='store_true')
        parser.add_argument("-dc", "--disablecron", help="enables cronjob to schedule backup", required=False,default=False, action='store_true')
        parser.add_argument("-networkpath", help="path to network share", required=False, default=False)
        parser.add_argument("-username", help="network share username", required=False, default=False)
        parser.add_argument("-password", help="network share password", required=False, default=False)
        parser.add_argument("-uid", help="user,run whoami to get answer", required=False, default=False)
        parser.add_argument("-uninstall", help="uninstalls network drive from fstab", required=False, default=False, action='store_true')
        self.argument = parser.parse_args()
    def enable_cron(self): # TODO Test this func to make sure it works
        os.system(f'(crontab -l ; echo "0 0 1 * * {self.script_directory}/rpi_backup_venv/bin/python {self.script_directory}/backup.py -rb>> {self.script_directory}/logs/cron.log") | crontab -')
        os.system(f'echo "# Log for Backups running through Cron" > {self.script_directory}/logs/cron.log')
        os.system(f'echo "---------------------------------------" >> {self.script_directory}/logs/cron.log')
        log('i',"cronjob enabled")
    def disable_cron(self):
        os.system(f"crontab -l | grep -v '{self.script_directory}/rpi_backup_venv/bin/python {self.script_directory}/backup.py -rb'  | crontab -")
        log('i',"cronjob disabled")


    def check_networks_drive_credentials(self,credentials_dict):

        # let user know if they're missing a flag
        stop_code = False
        for cred in credentials_dict:
            if cred != "-uid": # ignore uid, it's optional
                if credentials_dict[cred] is False:
                    log('e',f'missing {cred} argument')
                    stop_code = True
        if stop_code is True:
            exit(0)





    def run_backup(self):

        # Ensure Image-Utils was downloaded and ask user to do so if not
        if os.path.exists(f'{script_directory}/image-utils/image-backup') is False:
            log('e',"Please Download Image-Utils and place in this folder /rpi_backup/image-utils\nhttps://forums.raspberrypi.com/viewtopic.php?t=332000")
            exit(1)
        # Backup Settings
        filesize_buffer = 5000
        incremental_size = 0

        log('i',"Backup Starting....")

        # Mount network drive
        os.system("sudo mount /mnt/backups")
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if '/mnt/backups' in mount_list:
            log('s',"Backup Drive Mounted")
        else:
            log('e',"Mount Error! See above error.")
            log('e', "If first time running, re-run with -s flag instead to do initial setup")
            exit(1)


        # Get hostname and see if directory exists
        cmd = "hostname | cut -d\' \' -f1"
        hostname = str(subprocess.check_output(cmd, shell=True).decode('utf-8')).replace("\n", "")
        if os.path.exists(f'/mnt/backups/{hostname}') is False:
            log('i',f"Creating Directory {hostname}")
            os.system('sudo mkdir /mnt/backups/{hostname}')

        # Get Filesystem size
        cmd = "df -h /|awk '/\/dev\//{printf(\"%.2f\",$3);}'"
        file_size_gb = str(subprocess.check_output(cmd, shell=True).decode('utf-8')).replace("\n", "")
        file_size_mb = float(file_size_gb) * 1000
        log('i', f"File System Size: {file_size_mb}MB")

        # Build up back-up args
        filesystem_size = int(file_size_mb + filesize_buffer)

        # Get uid
        uid = str(subprocess.check_output('whoami', shell=True).decode('utf-8')).replace("\n", "")
        log('i',f'Identified user as {uid}')
        # Disable Docker
        log('i',"Docker disabled (Temporarily)")
        os.system("sudo systemctl disable docker.socket --now")
        os.system("sudo systemctl disable docker --now")
        log('i', "Beginning image-backup")
        # # backup string
        os.system(f"sudo bash /home/{uid}/rpi_backup/image-utils/image-backup -i /mnt/backups/{hostname}/{hostname}_$(date +%d-%b-%y_%T).img,{filesystem_size},{incremental_size}")
        log('i', "image-backup Finishing")
        # Unmount network drive
        os.system("sudo umount /mnt/backups")
        log('s', "Backup Drive Unmounted")

        # Enable Docker
        os.system("sudo systemctl enable docker --now")
        os.system("sudo systemctl enable docker.socket --now")
        log('i', "Docker Re-enabled")

        log('s',"Backup Completed")
        log('i',"\n--------------------------------------------------")


    def wipe_rpi_backup(self): # wipes rpi_backups to test deployment
        log('i', 'Unmounting drive')
        os.system(f"sudo umount /mnt/backups")  # unmount backups
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if '/mnt/backups' not in mount_list:
            log('s', "Backup Drive Unmounted Successfully")
        else:
            log('e', "Backup Drive Could Not Be Unmounted")
            exit(1)
        os.system(f"crontab -l | grep -v '{self.script_directory}/rpi_backup_venv/bin/python {self.script_directory}/backup.py -rb'  | crontab -")
        log('s',"cronjob disabled")
        os.system('sudo rm -r /mnt/backups') # delete backup location
        log('s', "deleted /mnt/backups")
        os.system(f"sudo sed -i.bak '/backups/d' /etc/fstab")  # remove the line from Fstab
        log('s', "Removed line from FSTAB")
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon
        print('rpi_backups uninstalled, go home and run "rm -r ./rpi_backup" to delete folder')




if __name__ == '__main__':
    a=rpi_backup()
