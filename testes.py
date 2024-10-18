import subprocess
import time

def scan_and_get_devices_only():
    # Inicia o processo bluetoothctl
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Envia o comando 'scan bredr' para iniciar a busca por dispositivos Bluetooth
    process.stdin.write('scan bredr\n')
    process.stdin.flush()

    # Aguarda por 5 segundos para realizar a varredura
    time.sleep(10)

    # Envia o comando 'scan off' para parar a varredura
    process.stdin.write('scan off\n')
    process.stdin.flush()

    # Envia o comando 'devices' para listar os dispositivos conhecidos
    process.stdin.write('devices\n')
    process.stdin.flush()

    # Coleta apenas a saída do comando 'devices'
    devices_output, _ = process.communicate()

    # Filtra e captura apenas as linhas que contenham 'Device', ou seja, os dispositivos reais
    new_devices = []
    nown_devices = []
    nown_off_devices = []


    lines = devices_output.splitlines()

    for line in lines:
        if 'Device' in line:
            line = line.split()
            # print(line)
            if line[0] == '\x1b[K[\x01\x1b[0;92m\x02NEW\x01\x1b[0m\x02]':
                if line[2] != line[3].replace('-', ':'):
                    # line = line.remove[0]
                    new_devices.append(line)

            if line[0] == 'Device':
                if line[1] != line[2].replace('-', ':'):
                    nown_devices.append(line)

    print("Nown==============")
    print(type(nown_devices))
    print(nown_devices)
    print("New==============")
    print(type(new_devices))
    print(new_devices)
    
    # for device in nown_devices:
    #     if 

        #     print(line)



        # if 'Device' in line:
        #     line = line.split()
        #     print(line)




            # devices.append(line)
            # if line[0] == '[NEW]':




            
            # if line[0] == 'Device':
            #     line = line.remove[0]
            #     print(line)
            #     if line[0] != line[1]:
            #         devices.append(line)

    # Retorna a lista de dispositivos
    return (new_devices, nown_devices)

# Executa a função e imprime os dispositivos encontrados
new_devices, nown_devices = scan_and_get_devices_only()

print("Novos")
for device in new_devices:
    print(device)

print("Conhecidos")
for device in nown_devices:
    print(device)