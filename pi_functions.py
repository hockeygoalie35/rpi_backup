import os
from colorama import Fore, init
import subprocess
import datetime
import sys

init(autoreset=True)  # Set autoreset to True else color would be forwarded to the next print statement
script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))


def log(msg_type,log_string, log_path = './logs/python.log', print_entries = True):
    color = None

    if os.path.exists(os.path.dirname(log_path)) is False: #Make the dir path if it doesn't exist
        os.mkdir(os.path.dirname(log_path))
        if os.path.exists(log_path) is False:
            with open(f'{script_directory}/logs/python.log', 'a') as savefile:
                savefile.write("# Logging for python script if cronjob is not active" + "\n")
                savefile.close()  # save to log file



    if msg_type == "info" or msg_type == "i":
        color = Fore.CYAN
    elif msg_type == "success" or msg_type == "s":
        color = Fore.GREEN
    elif msg_type == "warning" or msg_type == "w":
        color = Fore.YELLOW
    elif msg_type == "error" or msg_type == "e":
        color = Fore.RED
    else:
        raise ValueError(f"msg_type {msg_type} is invalid. Must be: info, success, warning, error")

    log_entry = datetime.datetime.strftime(datetime.datetime.now(), '%D-%H:%M:%S') + " " + log_string
    if print_entries is True:
        print(color + log_entry) # print to output

    with open(f'{script_directory}/logs/python.log', 'a') as savefile:
        savefile.write(log_entry + "\n")
        savefile.close() # save to log file
def create_cifs_drive(network_path,mnt_path,username,password,uid = "pi"):
    # build fstab string
    fstab_string = f'{network_path} {mnt_path} cifs username={username},password={password},uid={uid}'


    if "$" in fstab_string: # if $ in any argument, add an escape slash so it doesn't get treated as bash variable
        fstab_string_formatted = fstab_string.replace('$', '\$')
    else:
        fstab_string_formatted = fstab_string



        # Attempt to create mount point
    if os.path.exists(mnt_path) is False:
        try:
            os.system(f'sudo mkdir {mnt_path}')
            log('i',f"Created mounting folder {mnt_path}")
        except:
            log('e',"Could not create mounting folder. See above error.")

    create_cifs = True # Check to see if line is in Fstab for some reason
    with open('/etc/fstab') as fstab:
        if fstab_string in fstab.read():
            create_cifs = False
    fstab.close()

    if create_cifs is True:
        os.system(f"sudo su -c \"echo '{fstab_string_formatted}' >> /etc/fstab\"") # add string to fstab
        log('i', "Created drive mount link in /etc/fstab")
    else:
        log('w',"Drive mount link already found in /etc/fstab")
    os.system("sudo systemctl daemon-reload")  # reload fstab to daemon

    log('i','Attempting to mount network drive...')
    os.system(f'sudo  mount {mnt_path}')  # Attempt to activate mount
    # Get list of mounts
    mount_list = str(subprocess.run('mount -l', shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8"))
    if mnt_path in mount_list:
        log('s',"Mount Success!")
        os.system(f'sudo  umount {mnt_path}')  # Attempt to activate mount
        log('i', f"Unmounted drive, remount with 'sudo mount {mnt_path}'")
    else:
        log('e',"Mount Error! See above error and adjust your flags")
        log('e', "Mount Error! See above error and adjust your flags")
        search_string = mnt_path.replace('/','[/]')
        os.system(f"sudo sed -i.bak '/{search_string}/d' /etc/fstab") # remove the line from Fstab
        log('w', "Removed faulty string from fstab")
        log('w', fstab_string_formatted)
        exit(1)
