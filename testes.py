import subprocess
import time

def scan_bluetooth_devices():
    # Inicia o processo bluetoothctl
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Envia o comando 'scan on' para iniciar a busca por dispositivos
    process.stdin.write('scan on\n')
    process.stdin.flush()

    # Aguarda por 5 segundos para realizar a varredura
    time.sleep(5)

    # Envia o comando 'scan off' para interromper a busca por dispositivos
    process.stdin.write('scan off\n')
    process.stdin.flush()

    # Envia o comando 'devices' para listar os dispositivos encontrados
    process.stdin.write('devices\n')
    process.stdin.flush()

    # Captura a saída do comando
    output, _ = process.communicate()

    # Filtra as linhas que contenham dispositivos reais (baseado na saída do comando 'devices')
    devices = []
    for line in output.splitlines():
        if 'Device' in line:
            devices.append(line)

    # Retorna a lista de dispositivos encontrados
    return devices

# Executa a função e imprime os dispositivos encontrados
devices_found = scan_bluetooth_devices()
for device in devices_found:
    print(device)
