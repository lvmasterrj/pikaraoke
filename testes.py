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
        config_obj.add_section(section)

    devices[1].append(device)
    config_obj[section][key] = str(devices[1])
    with open(file, 'w') as configfile:
        config_obj.write(configfile)
    return
    
    
def remove_known_device(device):
    if os.path.exists(file):
        devices = get_known_devices()
        if devices[0] == "ok":
            devices[1] = [item for item in devices[1] if item[1] != device[0]]
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

    # print("====== Devices Output==========")
    # print(devices_output)
   
   
   
   
   
    # # Envia o comando 'scan bredr' para iniciar a busca por dispositivos Bluetooth
    # run_bluetoothctl_command(command)
    # process.stdin.write('scan bredr\n')
    # process.stdin.flush()

    # # Aguarda pelo tempo requerido ou 10s para realizar a varredura
    # time.sleep(time)

    # # Envia o comando 'scan off' para parar a varredura
    # process.stdin.write('scan off\n')
    # process.stdin.flush()

    # # Envia o comando 'devices' para listar os dispositivos conhecidos
    # process.stdin.write('devices\n')
    # process.stdin.flush()

    # # Coleta apenas a saída do comando 'devices'
    # devices_output, _ = process.communicate()

    # Filtra e captura apenas as linhas que contenham 'Device', ou seja, os dispositivos reais
    devices_new = []
    devices_known = []

    lines = devices_output.splitlines()

    for line in lines:
        if 'Device' in line:
            line = line.split()
            # print("====== Line ======")
            # print(line)
            if line[0] == '\x1b[K[\x01\x1b[0;92m\x02NEW\x01\x1b[0m\x02]':
                if line[2] != line[3].replace('-', ':'):
                    newline = ['new', line[2], ' '.join(line[3:]), now]
                    # # print(line)
                    # del line[0]
                    # line[0] = 'new'
                    # line[2] = ' '.join(line[2:])
                    
                    devices_new.append(newline)

            # elif line[0] == 'Device':
            #     if line[1] != line[2].replace('-', ':'):
            #         newline = ['known', line[1], ' '.join(line[2:])]
            #         devices_known.append(newline)

    # print("===== New Devices =====")
    # print(devices_new)

    devices_known = get_known_devices()

    if devices_known[0] == "ok":
        print("===== Known Devices =====")
        print(devices_known)

    if devices_new:
        print("===== New Devices =====")
        return devices_new
    
    # print("===== Known Devices =====")
    # print(devices_known)               

    # Itera sobre a lista de dispositivos conhecidos
    # for known_device in devices_known[:]:  # Usando [:] para fazer uma cópia da lista durante a iteração
    #     found = False
    #     # Verifica se o dispositivo conhecido está na lista de dispositivos novos
    #     for new_device in devices_new:
    #         if known_device[1] == new_device[1]:  # Compara o endereço MAC
    #             # Se o dispositivo estiver na lista de dispositivos novos, remova-o de 'devices_nown'
    #             devices_known.remove(known_device)
    #             found = True
    #             break
        
    #     # Se não encontrado, muda 'known' para 'known_off'
    #     if not found:
    #         known_device[0] = 'known_off'

    # return devices_new + devices_known

# def connect_to_device(mac_number):

# devices = scan_and_get_devices(10)

# for device in devices:
#     print("===== Devices =====")
#     print(device)


def show_devices():
    print("===== Devices =====")
    print(scan_and_get_devices())


def connect_to_device(device):

    tries = 0
    success = False
    
    while tries != 5:
        tries += 1
        print(f'==== Tentativa {tries} =====')

        # scan_and_get_devices(10)
        # show_devices()

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
            print("--- Linha")
            print(line)
            if 'Connection successful' in line:
                success = True
                tries = 5
                break
        
        


    if success:
        print("===== Conectado com sucesso!!! =====")
        add_known_device(device)
    else:
        print(f'===== Falha ao conectar a {device[2]} =====')

def remove_device(device):
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    process.stdin.write(f'remove {device[1]}\n')
    process.stdin.flush()
    result, _ = process.communicate()
    print(result)
    remove_known_device(device(1))