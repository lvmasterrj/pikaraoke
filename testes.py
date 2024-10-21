# TODO: fazer uma lista de dispositivos já pareados para comparar com a lista de 
# devices, porque se fizer pesquisas rápido, a lista de devices contém dispositivos novos

import subprocess
import time

def run_bluetoothctl_command(command):
    # Inicia o processo bluetoothctl
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    process.stdin.write(command)
    process.stdin.flush()
    devices_output, _ = process.communicate()

    return devices_output

def run_commands(commands):
    for command in commands:
        output = run_bluetoothctl_command(command)
        # time.sleep(2)
    return output

def scan_and_get_devices(scan_time=10):

    run_commands(['scan bredr\n'])

    time.sleep(scan_time)

    devices_output = run_commands(['scan off\n', 'devices\n'])

    print("====== Devices Output==========")
    print(devices_output)
   
   
   
   
   
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
            print("====== Line ======")
            print(line)
            if line[0] == '\x1b[K[\x01\x1b[0;92m\x02NEW\x01\x1b[0m\x02]':
                if line[2] != line[3].replace('-', ':'):
                    newline = ['new', line[2], ' '.join(line[3:])]
                    # # print(line)
                    # del line[0]
                    # line[0] = 'new'
                    # line[2] = ' '.join(line[2:])
                    
                    devices_new.append(newline)

            elif line[0] == 'Device':
                if line[1] != line[2].replace('-', ':'):
                    newline = ['known', line[1], ' '.join(line[2:])]
                    devices_known.append(newline)

    print("===== New Devices =====")
    print(devices_new)
    print("===== Known Devices =====")
    print(devices_known)               

    # Itera sobre a lista de dispositivos conhecidos
    for known_device in devices_known[:]:  # Usando [:] para fazer uma cópia da lista durante a iteração
        found = False
        # Verifica se o dispositivo conhecido está na lista de dispositivos novos
        for new_device in devices_new:
            if known_device[1] == new_device[1]:  # Compara o endereço MAC
                # Se o dispositivo estiver na lista de dispositivos novos, remova-o de 'devices_nown'
                devices_known.remove(known_device)
                found = True
                break
        
        # Se não encontrado, muda 'known' para 'known_off'
        if not found:
            known_device[0] = 'known_off'

    return devices_new + devices_known

# def connect_to_device(mac_number):

devices = scan_and_get_devices(10)

for device in devices:
    print(device)
