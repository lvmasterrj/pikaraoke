# TODO: fazer uma lista de dispositivos já pareados para comparar com a lista de 
# devices, porque se fizer pesquisas rápido, a lista de devices contém dispositivos novos

import subprocess
import time
import configparser
import os
import ast
from time import localtime, strftime

now = strftime("%Y-%m-%d %H:%M:%S", localtime())
file = "btdevices.txt"
section = "DEVICES"
key = "known"
config_obj = configparser.ConfigParser()

def get_known_devices():
    if os.path.exists(file):
        config_obj.read(file)
        if section in config_obj:
            known_devices = ast.literal_eval(config_obj[section][key])
            return ['ok', known_devices]
        else:
            return ['error', 'no_section']
    else:
        return [ 'error' , 'no_file']

def add_known_device(device):
    device[0] = 'known'
    devices = get_known_devices()

    if devices[0] != "ok":
        devices[1]=[]
        config_obj.add_section(section)

    devices[1].append(device)
    config_obj[section][key] = str(devices[1])
    with open(file, 'w') as configfile:
        config_obj.write(configfile)
    return
    
def remove_known_device(device):
    print("==== Removing device=====")
    print(device)
    if os.path.exists(file):
        devices = get_known_devices()
        if devices[0] == "ok":
            devices[1] = [item for item in devices[1] if item[1] != device]
            config_obj[section][key] = str(devices[1])
            with open(file, 'w') as configfile:
                config_obj.write(configfile)
            return "ok"
    return "error"

def run_bluetoothctl_command(process, command):
    # Inicia o processo bluetoothctl
    process.stdin.write(command)
    process.stdin.flush()
    return

def run_commands(process, commands):
    for command in commands:
        run_bluetoothctl_command(process, command)
        # time.sleep(2)
    return

def scan_and_get_devices(scan_time=10):

    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    
    run_commands(process, ['scan on\n'])

    time.sleep(scan_time)

    run_commands(process, ['scan off\n', 'devices\n'])

    devices_output, _ = process.communicate()

    # Filtra e captura apenas as linhas que contenham 'Device', ou seja, os dispositivos reais
    devices_new = []
    devices_known = []

    lines = devices_output.splitlines()

    for line in lines:
        if 'Device' in line:
            line = line.split()
            if line[0] == '\x1b[K[\x01\x1b[0;92m\x02NEW\x01\x1b[0m\x02]':
                if line[2] != line[3].replace('-', ':'):
                    newline = ['new', line[2], ' '.join(line[3:]), now]
                    devices_new.append(newline)
    devices_known = get_known_devices()

    if devices_known[0] == "ok":
        print("===== Known Devices =====")
        print(devices_known)

    if devices_new:
        print("===== New Devices =====")
        return devices_new
    
def show_devices():
    print("===== Devices =====")
    print(scan_and_get_devices())

def connect_to_device(device):
    tries = 0
    success = False
    
    while tries != 5:
        tries += 1
        print(f'==== Tentativa {tries} =====')

        process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
        process.stdin.write('scan on\n')
        process.stdin.flush()
        time.sleep(10)
        process.stdin.write(f'pair {device[1]}\n')
        process.stdin.flush()
        time.sleep(2)
        process.stdin.write(f'connect {device[1]}\n')
        process.stdin.flush()
        time.sleep(2)
        process.stdin.write(f'trust {device[1]}\n')
        process.stdin.flush()
        result, _ = process.communicate()
        
        lines = result.splitlines()

        for line in lines:
            if 'Connection successful' in line:
                success = True
                tries = 5
                break

    if success:
        print("===== Conectado com sucesso!!! =====")
        add_known_device(device)
    else:
        print(f'===== Falha ao conectar a {device[2]} =====')

def get_connected_device():

    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    process.stdin.write('scan on\n')
    process.stdin.flush()
    result, _ = process.communicate()

    lines = result.splitlines()

    for line in lines:
        if 'Device' in line:
            return line
        else:
            return[]
    
    
        

def remove_device(device):
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    process.stdin.write(f'remove {device[1]}\n')
    process.stdin.flush()
    result, _ = process.communicate()
    print(result)
    remove_known_device(device[1])