import subprocess
import os
import time

def get_filesystem_name(unit = None):
    cmd = "df -h /|awk '/\/dev\//{printf(\"%.2f\",$3);}'"
    filesystem_size = str(subprocess.check_output(cmd, shell=True).decode('utf-8')).replace("\n", "")
    if unit == 'MB':
        filesystem_size = float(filesystem_size) * 1000
    if unit == 'TB':
        filesystem_size = float(filesystem_size) / 1000
    else:
        filesystem_size = int(filesystem_size)
    return filesystem_size


def get_uid():
    return str(subprocess.check_output('whoami', shell=True).decode('utf-8')).replace("\n", "")


def disable_docker():
    os.system("sudo docker stop $(sudo docker ps -a -q)")
    os.system("sudo systemctl disable docker.socket --now")
    os.system("sudo systemctl disable docker --now")

def enable_docker(priority_containers):

    os.system("sudo systemctl enable docker --now")
    os.system("sudo systemctl enable docker.socket --now")

    if priority_containers != ['']:
        command_string = 'sudo docker start '
        # build priority start command
        for container in priority_containers:
            command_string = command_string + container + ' '
        os.system(command_string)
    time.sleep(5)
    os.system("sudo docker start $(sudo docker ps -a -q)")  # restart all rest of containers



    # Enable and fill this if you need containers to start in an order I.e. a vpn container.
    time.sleep(5)  # You can duplicate & change the time however many dependencies you have
    os.system("sudo docker start $(sudo docker ps -a -q)")  # restart all rest of containers


def get_host_name():
    return str(subprocess.check_output("hostname | cut -d\' \' -f1", shell=True).decode('utf-8')).replace("\n", "")

def program_exists(program_name):
    results = subprocess.check_output(f'command -v {program_name}', shell=True)
    if results == "":
        return False
    return True


if __name__ == '__main__':
    program_exists('docker')