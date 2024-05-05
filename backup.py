import os
import sys
import subprocess
import argparse
from datetime import datetime
import requests
import time
import configparser
import linux_commands
import prettylogging


# backup.py
VERSION = '2.0 Alpha'

BOOL_DICT = {'true': True, 'false': False}
WORKING_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_PATH = f'{WORKING_DIR}/config.ini'

# Logging Consts
NOW = datetime.strftime(datetime.now(), "%b-%d-%Y-%H-%M-%S")
LOGGER_NAME = 'rpi_backup'
LOG_OUTPUT_PATH = f'{WORKING_DIR}/logs/Backup-'+NOW+'.log'

log = prettylogging.init_logging(LOGGER_NAME, VERSION, log_file_path=LOG_OUTPUT_PATH, info_color="GREEN")


class SetupError(BaseException):
    def __init__(self, exception_message):
        log.error('Setup Error: '+exception_message)
        exit(1)


class RpiBackup:
    def __init__(self):
        self.config = read_config(CONFIG_PATH)
        self.credentials_dict = {}
        self.mnt_path = self.config['rpi-backup']['rpi_mount_path']
        self.ntfy_enabled = BOOL_DICT[self.config['ntfy']['ntfy_enabled'].lower()]
        self.ntfy_server_topic = self.config['ntfy']['ntfy_server_topic']
        self.ntfy_user_token = self.config['ntfy']['ntfy_user_token']
        self.priority_containers = self.config['docker']['priority_containers'].split(',')
        self.incremental_size = self.config['image-backup']['incremental_size']
        self.filesize_buffer = self.config['image-backup']['filesize_buffer']
        self.cron_interval = self.config['cronjob']['cron_run_interval']
        self.hostname = linux_commands.get_host_name()
        self.docker_installed = linux_commands.program_exists('docker')
        self.uid = linux_commands.get_uid()

        try:
            self.argument_parsing()  # parse the passed arguments from the CLI
        except SystemExit:
            print("If you're getting a 'password: expected one arg' error, try placing your password in quotes")
            exit(2)

        if self.argument.setup:
            self.setup()  # Run the setup script to set up auto-mounting
            log.info('Setup Complete!')
        if self.argument.runbackup:
            self.run_backup(backup_type='Full')  # Run a backup
        if self.argument.runincremental:
            self.run_backup(backup_type='Incremental')  # Run a backup
        if self.argument.enablecron:
            self.enable_cron()  # Enable a cronjob to run at a set interval
        if self.argument.disablecron:
            self.disable_cron()  # Disable cronjob
        if self.argument.uninstall:
            answer = input("Are you sure you want to uninstall? y/n\n")
            if answer == "y":
                self.wipe_rpi_backup()  # Remove application

    def argument_parsing(self):
        parser = argparse.ArgumentParser(description="CLI Commands")
        parser.add_argument("-s", "--setup", help="initial setup, supply path, username, password and uid if user is not pi", required=False, default=False, action='store_true')
        parser.add_argument("-rb", "--runbackup", help="run full backup", required=False, default=False, action='store_true')
        parser.add_argument("-ec", "--enablecron", help="enables cronjob to schedule backup", required=False, default=False, action='store_true')
        parser.add_argument("-dc", "--disablecron", help="enables cronjob to schedule backup", required=False, default=False, action='store_true')
        parser.add_argument("-np", "--networkpath", help="path to network share", required=False, default=False)
        parser.add_argument("-u", "--username", help="network share username", required=False, default=False)
        parser.add_argument("-p", "--password", help="network share password", required=False, default=False)
        parser.add_argument("-uid", help="user,run whoami to get answer", required=False, default=False)
        parser.add_argument("-uninstall", help="uninstalls network drive from fstab", required=False, default=False, action='store_true')
        parser.add_argument("-ri", "--runincremental", help="run incremental backup", required=False, default=False, action='store_true')
        self.argument = parser.parse_args()

    def setup(self):
        log.info('Attempting setup with supplied credentials...')
        self.credentials_dict = {
            "--networkpath": self.argument.networkpath,
            "--username": self.argument.username,
            "--password": self.argument.password,
            "--uid": self.argument.uid
        }

        for cred in self.credentials_dict:  # let user know if they're missing a flag
            if cred != "--uid":  # ignore uid, it's optional
                if self.credentials_dict[cred] is False:
                    raise SetupError(f'Missing {cred} argument from setup')

        try:
            self.create_cifs_drive()
        except Exception as e:
            raise SetupError(str(e))

    def get_latest_backup(self):
        # Get current log file
        path = self.mnt_path + f'/{self.hostname}/'
        latest_file = max([os.path.join(path, f) for f in os.listdir(path) if self.hostname in f], key=os.path.getctime)
        return latest_file

    def run_backup(self, backup_type=None):
        log.info(f'Running {backup_type} Backup...')
        log.info("If using cron, check cron.log for terminal output.")
        os.system(f'echo "Check {LOG_OUTPUT_PATH} in case of error" >> {WORKING_DIR}/logs/cron.log')
        if backup_type is None:
            log.warning(f'Backup type not set, assuming full.')

        # Ensure Image-Utils was downloaded and ask user to do so if not
        if os.path.exists(f'{WORKING_DIR}/image-utils/image-backup') is False:
            log.error("Please Download Image-Utils and place in this folder /rpi_backup/image-utils\nhttps://forums.raspberrypi.com/viewtopic.php?t=332000")
            ntfy_notify(self.ntfy_server_topic, self.ntfy_user_token, f"Backup of {self.hostname} failed, see logs for details.")
            exit(1)

        # Mount network drive
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon
        os.system("sudo mount /mnt/backups")  # mount drive

        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))

        if '/mnt/backups' not in mount_list:
            self.failed_backup("Bind mount not found. re-run with the -s flag or check your fstab file", backup_started=False)
        log.info("Backup Drive Mounted")

        # Get Hostname & see if directory exists on mount target
        self.hostname = linux_commands.get_host_name()
        if os.path.exists(f'/mnt/backups/{self.hostname}') is False:
            os.system(f'sudo mkdir /mnt/backups/{self.hostname}')
            log.info(f"Created Backup Directory {self.hostname}")

        # Get Filesystem size
        filesystem_size = linux_commands.get_filesystem_name('MB')
        log.debug(f"File System Size: {int(filesystem_size/1000)}GB")

        # Get uid
        uid = linux_commands.get_uid()
        log.debug(f'Identified user as {uid}')

        # image-utils
        log.debug(f'Backup buffer: {self.filesize_buffer}')
        log.debug(f'incremental Size = {self.incremental_size}')
        backup_image_size = int(filesystem_size + int(self.filesize_buffer))

        # Disable Docker if installed
        if self.docker_installed:  # if docker is installed, disable
            log.debug("Disabling Docker")
            linux_commands.disable_docker()
            log.info("Docker disabled (Temporarily)")

        try:
            log.debug("Beginning image-backup")
            if backup_type == 'Incremental':
                backup_path = self.get_latest_backup()
                log.debug(f"Starting Incremental Backup of last full: {backup_path}")
                # incremental backup string
                os.system(f"sudo bash /home/{uid}/rpi_backup/image-utils/image-backup {backup_path}")
            else:
                # full backup string
                log.debug("Starting Full Backup")
                os.system(f"sudo bash /home/{uid}/rpi_backup/image-utils/image-backup -i /mnt/backups/{self.hostname}/{self.hostname}_$(date +%d-%b-%y_%T).img,{backup_image_size},{self.incremental_size}")
            log.info("image-backup Finishing")
            # Unmount network drive
            os.system("sudo umount /mnt/backups")
            log.info("Backup Drive Unmounted")
        except Exception as e:
            self.failed_backup(str(e))

        if self.docker_installed:  # if docker is installed, disable
            linux_commands.enable_docker(self.priority_containers)
            log.info("Docker Re-enabled")

        log.info("Backup Completed!")
        time.sleep(20)  # Give it time for ntfy to start back up
        if backup_type == 'incremental':
            ntfy_notify(self.ntfy_server_topic, self.ntfy_user_token, f"{self.hostname}\nBackup-{NOW} Complete! \U00002705")
        else:
            ntfy_notify(self.ntfy_server_topic, self.ntfy_user_token, f"{self.hostname}\nBackup-{NOW} Complete! \U00002705")

    def enable_cron(self):
        if self.cron_interval != '':
            os.system(f'(crontab -l ; echo "{self.cron_interval} {WORKING_DIR}/rpi_backup_venv/bin/python {WORKING_DIR}/backup.py -rb >> {WORKING_DIR}/logs/cron.log") | crontab -')
            os.system(f'echo "# Log for Backups running through Cron" > {WORKING_DIR}/logs/cron.log')
            os.system(f'echo "---------------------------------------" >> {WORKING_DIR}/logs/cron.log')
            log.info(f"cronjob enabled, with interval {self.cron_interval}")

    def disable_cron(self):
        os.system(f"crontab -l | grep -v '/rpi_backup_venv/bin/python'  | crontab -")
        log.info("cronjob disabled")

    def wipe_rpi_backup(self):  # wipes rpi_backups to test deployment
        log.debug('Unmounting drive')
        os.system(f"sudo umount /mnt/backups")  # unmount backups
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if '/mnt/backups' not in mount_list:
            log.info("Backup Drive Unmounted Successfully")
        else:
            log.error("Backup Drive Could Not Be Unmounted")
            exit(1)
        os.system(f"crontab -l | grep -v '{WORKING_DIR}/rpi_backup_venv/bin/python {WORKING_DIR}/backup.py -rb'  | crontab -")
        log.info("cronjob disabled")
        os.system('sudo rm -r /mnt/backups')  # delete backup location
        log.info("deleted /mnt/backups")
        os.system(f"sudo sed -i.bak '/backups/d' /etc/fstab")  # remove the line from Fstab
        log.info("Removed line from FSTAB")
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon
        log.info('rpi_backups uninstalled, go home and run "rm -r ./rpi_backup" to delete folder')

    def failed_backup(self, error_message, backup_started=True):
        log.error(f"Backup of {self.hostname} failed:\n{error_message}")
        if self.ntfy_enabled:  # if ntfy is set up
            ntfy_notify(self.ntfy_server_topic, self.ntfy_user_token,
                        f"{self.hostname}\nBackup-{NOW} Failed \U0000274C\n{error_message}")
        if backup_started is False:
            exit(1)
        # Unmount network drive
        os.system("sudo umount /mnt/backups")
        if self.docker_installed:  # if docker is installed, disable
            linux_commands.enable_docker(self.priority_containers)
        if self.ntfy_enabled:  # if ntfy is set up
            ntfy_notify(self.ntfy_server_topic, self.ntfy_user_token,
                        f"{self.hostname}\nBackup-{NOW} Failed \U0000274C\n{error_message}")
        exit(1)

    def create_cifs_drive(self):
        # build fstab string
        fstab_string = f"{self.credentials_dict['--networkpath']} {self.mnt_path} cifs username={self.credentials_dict['--username']},password={self.credentials_dict['--password']},uid={self.uid}"

        if "$" in fstab_string:  # if $ in any argument, add an escape slash, so it doesn't get treated as bash variable
            fstab_string_formatted = fstab_string.replace('$', '\$')
        else:
            fstab_string_formatted = fstab_string

            # Attempt to create mount point
        if os.path.exists(self.mnt_path) is False:
            try:
                os.system(f'sudo mkdir {self.mnt_path}')
                log.info(f"Created mounting folder {self.mnt_path}")
            except:
                raise SetupError("Could not create mounting folder. See above error.")

        create_cifs = True  # Check to see if line is in Fstab for some reason
        with open('/etc/fstab') as fstab:
            if fstab_string in fstab.read():
                create_cifs = False
        fstab.close()
        log.debug(f'string to be added to fstab: {fstab_string_formatted}')
        if create_cifs is True:
            os.system(f"sudo su -c \"echo '{fstab_string_formatted}' >> /etc/fstab\"")  # add string to fstab
            log.info("Created drive mount link in /etc/fstab")
        else:
            log.warning("Drive mount link already found in /etc/fstab")
        os.system("sudo systemctl daemon-reload")  # reload fstab to daemon

        log.debug('Attempting to mount network drive...')
        os.system(f'sudo  mount {self.mnt_path}')  # Attempt to activate mount
        # Get list of mounts
        mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
        if self.mnt_path in mount_list:
            log.info("Mount Success!")
            os.system(f'sudo  umount {self.mnt_path}')  # Attempt to activate mount
            log.info(f"Unmounted drive, remount with 'sudo mount {self.mnt_path}'")
        else:
            log.error("Mount Error! See above error and adjust your flags")
            search_string = self.mnt_path.replace('/', '[/]')
            os.system(f"sudo sed -i.bak '/{search_string}/d' /etc/fstab")  # remove the line from Fstab
            raise SetupError(f"Removed faulty string from fstab: {fstab_string_formatted}")


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


def read_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    dictionary = {}
    for section in config.sections():
        dictionary[section] = {}
        for option in config.options(section):
            dictionary[section][option] = config.get(section, option)
    config = dictionary
    return (config)


if __name__ == '__main__':
    a=RpiBackup()
