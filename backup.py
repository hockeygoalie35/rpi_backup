# Python 3.11.2
# Usage: Raspberry Pi SD Card live backups using Image-Utils by RonR.
# Attaches to a network drive of your choosing.

import os
import subprocess
from colorama import init, Fore
import datetime
import json
import traceback

def log_error(log_string):
    print(Fore.RED + datetime.datetime.strftime(datetime.datetime.now(),'%D-%H:%M:%S') + " " + log_string)
    with open('.//python_log.txt', 'a') as savefile:
        savefile.write("------------------------------------\n"+datetime.datetime.strftime(datetime.datetime.now(),'%D-%H:%M:%S') + ":\n " + log_string + "\n")
        savefile.close()
def log(log_string):
    print(Fore.GREEN+ datetime.datetime.strftime(datetime.datetime.now(),'%D-%H:%M:%S') + " " + log_string)
    with open('.//python_log.txt', 'a') as savefile:
        savefile.write(datetime.datetime.strftime(datetime.datetime.now(),'%D-%H:%M:%S') + ": " + log_string + "\n")
        savefile.close()

def run_backup():
    init(autoreset=True)  # Set autoreset to True else color would be forwarded to the next print statement

    # Windows Share
    # path E.g //192.168.1.5/E/Folder/Folder2/etc...
    # Username and Pass are Windows account
    # uid = raspberry pi username...usually pi

    # Try to load credentials, if not, create the file and ask user to fill
    try:
        with open('./creds.json') as openfile:
            # Reading from json file
            creds = json.load(openfile)  # loads in the credential dict
            openfile.close()
    except:
        creds = {"path": "","username": "","password": "","uid": ""}
        creds = json.dumps(creds)
        with open('./creds.json', 'w') as savefile:
            savefile.write(creds)
        log_error("creds.json created.")
        exit(0)
    path=creds["path"]
    username=creds["username"]
    password=creds["password"]
    uid = creds["uid"]


    # Ensure Image-Utils was downloaded and ask user to do so if not
    if os.path.exists('./image-utils/image-backup') is False:
        log_error("Please Download Image-Utils and place in this folder /rpi_backup/image-utils\nhttps://forums.raspberrypi.com/viewtopic.php?t=332000")
        exit("missing utils")
    # Backup Settings
    filesize_buffer = 5000
    incremental_size = 0

    fstab_string = f'{path} /mnt/backups cifs username={username},password={password},uid={uid}'
    log( f"Backup Starting....")


    # Create Mount point on pi if needed
    with open('/etc/fstab') as fstab:
        if  os.path.exists('/mnt/backups') is False or fstab_string not in fstab.read():
            if os.path.exists('/mnt/backups') is False:
                try:
                    os.mkdir('/mnt/backups')
                    log( "Created mounting point")
                except:
                    log(Fore.RED + "Could not create mounting point. See above error")
                    exit(1)
            if fstab_string not in fstab.read():
                os.system(f"sudo su -c \"echo '{fstab_string}' >> /etc/fstab\"")
                os.system("sudo systemctl daemon-reload")
                log( "Created drive mount link")
    fstab.close()

    # Mount network drive
    os.system("sudo mount /mnt/backups")
    log( "Backup Drive Mounted")

    # Get hostname and see if directory exists
    cmd = "hostname | cut -d\' \' -f1"
    hostname = str(subprocess.check_output(cmd, shell=True).decode('utf-8')).replace("\n","")
    if os.path.exists(f'/mnt/backups/{hostname}') is False:
        log( f"Creating Directory {hostname}")
        os.mkdir(f'/mnt/backups/{hostname}')

    # Get Filesystem size
    cmd = "df -h /|awk '/\/dev\//{printf(\"%.2f\",$3);}'"
    file_size_gb = str(subprocess.check_output(cmd,shell=True).decode('utf-8')).replace("\n","")
    file_size_mb  = float(file_size_gb) * 1000

    # Build up back-up args
    filesystem_size = int(file_size_mb + filesize_buffer)

    # Disable Docker
    log( "Docker disabled (Temporarily)")
    os.system("sudo systemctl disable docker --now")
    os.system("sudo systemctl disable docker.socket --now")
    os.system(f"sudo bash /home/{uid}/rpi_backup/image-utils/image-backup -i /mnt/backups/{hostname}/{hostname}_$(date +%d-%b-%y_%T).img,{filesystem_size},{incremental_size}")



    # Unmount network drive
    os.system("sudo umount /mnt/backups")
    log( "Backup Drive Unmounted")

    # Enable Docker
    os.system("sudo systemctl enable docker --now")
    os.system("sudo systemctl enable docker.socket --now")
    log( "Docker Re-enabled")


    log( f"Backup Completed")
    log( "\n--------------------------------------------------")

if __name__ == '__main__':
    try:
        run_backup()
    except Exception:
        log_error(traceback.format_exc())
        exit(1)

