import subprocess
import time

def scan_and_get_devices_only():
    # Inicia o processo bluetoothctl
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Envia o comando 'scan bderd' para iniciar a busca por dispositivos Bluetooth
    process.stdin.write('scan bderd\n')
    process.stdin.flush()

    # Aguarda por 5 segundos para realizar a varredura
    time.sleep(5)

    # Envia o comando 'scan off' para parar a varredura
    process.stdin.write('scan off\n')
    process.stdin.flush()

    # Envia o comando 'devices' para listar os dispositivos conhecidos
    process.stdin.write('devices\n')
    process.stdin.flush()

    # Coleta apenas a saída do comando 'devices'
    devices_output, _ = process.communicate()

    # Filtra e captura apenas as linhas que contenham 'Device', ou seja, os dispositivos reais
    devices = []
    for line in devices_output.splitlines():
        if 'Device' in line:
            # line = line.split()
            devices.append(line)
            # if line[0] == '[NEW]':




            
            # if line[0] == 'Device':
            #     line = line.remove[0]
            #     print(line)
            #     if line[0] != line[1]:
            #         devices.append(line)

    # Retorna a lista de dispositivos
    return devices

# Executa a função e imprime os dispositivos encontrados
devices_found = scan_and_get_devices_only()
for device in devices_found:
    print(device)
