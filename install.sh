# Setup Venv
sudo apt install python3.11-venv
echo "Creating Venv"
python3 -m venv rpi_backup_venv
source ./rpi_backup_venv/bin/activate
pip3 install -r ./requirements.txt
deactivate



