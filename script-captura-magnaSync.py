import time as t
from datetime import datetime

import psutil as p
from mysql.connector import connection

ID_EQUIPAMENTO = 1       # equipamento criado no script SQL
INTERVALO_CAPTURA = 3     # segundos entre capturas  
GB = 1024 ** 3

limite_atencao = 70
limite_alerta = 90

conexao = connection.MySQLConnection(
    host="localhost",
    user="aluno2",
    password="sptech",
    database="magnasync",
)
cursor = conexao.cursor()

# DISCRETIZAÇÃO

def classificar_percentual(valor, limiteAtencao=limite_atencao, limiteAlerta=limite_alerta):
    if valor >= limiteAlerta:
        return "Alerta!"
    elif valor >= limiteAtencao:
        return "Atenção"
    else:
        return "Normal"


def pior_status(lista_status):
    pior_componente = {"Normal": 0, "Atenção": 1, "Alerta!": 2}
    return max(lista_status, key=lambda status: pior_componente[status])


# COLETA

def coletar_cpu():
    percentual = p.cpu_percent(interval=1)
    freq = p.cpu_freq()
    frequencia = freq.current if freq else 0
    nucleos = p.cpu_count()
    return percentual, frequencia, nucleos

def coletar_ram():
    ram = p.virtual_memory()
    return ram.percent, ram.total / GB, ram.available / GB

def coletar_disco():
    disco = p.disk_usage("/")
    return disco.percent, disco.total / GB, disco.free / GB

def coletar_rede():
    rede = p.net_io_counters()
    download = round(rede.bytes_recv / 1000000, 1) 
    upload = round(rede.bytes_sent / 1000000, 1)     
    return download, upload

def capturar_e_inserir():
    agora = datetime.now()

    perc_cpu, freq_cpu, nucleos = coletar_cpu()
    perc_ram, ram_total, ram_disp = coletar_ram()
    perc_disco, disco_total, disco_disp = coletar_disco()
    download, upload = coletar_rede()

    status_cpu = classificar_percentual(perc_cpu)
    status_ram = classificar_percentual(perc_ram)
    status_disco = classificar_percentual(perc_disco)
    status_geral = pior_status([status_cpu, status_ram, status_disco])

    print(f"\nCaptura em {agora.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"CPU:   {perc_cpu}% | {freq_cpu:.0f} MHz | {nucleos} núcleos | {status_cpu}")
    print(f"RAM:   {perc_ram}% | Disponível: {ram_disp:.2f} GB | {status_ram}")
    print(f"Disco: {perc_disco}% | Disponível: {disco_disp:.2f} GB | {status_disco}")
    print(f"Rede:  Download: {download} MB | Upload: {upload} MB")
    print(f"Status geral: {status_geral}")

    comando = """
        INSERT INTO registros
        (id_equipamento,
         cpu_percentual, cpu_frequencia, cpu_nucleos, cpu_status,
         ram_percentual, ram_total, ram_disponivel, ram_status,
         disco_percentual, disco_total, disco_disponivel, disco_status,
         download_mb, upload_mb,
         status_geral, data_hora)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    valores = (ID_EQUIPAMENTO,
               perc_cpu, freq_cpu, nucleos, status_cpu,
               perc_ram, ram_total, ram_disp, status_ram,
               perc_disco, disco_total, disco_disp, status_disco,
               download, upload,
               status_geral, agora)

    cursor.execute(comando, valores)
    conexao.commit()


def captura_continua():
    print("\nCapturando dados. Pressione 'ctrl + c' para voltar ao menu.")
    while True:
        try:
            capturar_e_inserir()
            print("Dados inseridos com sucesso!")
            t.sleep(3)
        except KeyboardInterrupt:
            conexao.rollback()
            print("\nCaptura interrompida. Voltando ao menu...")
            break


def ver_cpu():
    cursor.execute(
        "SELECT id_registro, cpu_percentual, cpu_frequencia, cpu_nucleos, cpu_status, data_hora "
        "FROM registros ORDER BY id_registro DESC LIMIT %s", (20,))
    print("\nCPU")
    for l in cursor.fetchall():
        print(f"ID: {l[0]} | CPU: {l[1]}% | Frequência: {l[2]} MHz | Núcleos: {l[3]} | Status: {l[4]} | Timestamp: {l[5]}")


def ver_ram():
    cursor.execute(
        "SELECT id_registro, ram_percentual, ram_total, ram_disponivel, ram_status, data_hora "
        "FROM registros ORDER BY id_registro DESC LIMIT %s", (20,))
    print("\nMemória")
    for l in cursor.fetchall():
        print(f"ID: {l[0]} | Uso: {l[1]}% | Total: {l[2]:.2f} GB | Disponível: {l[3]:.2f} GB | Status: {l[4]} | Timestamp: {l[5]}")


def ver_disco():
    cursor.execute(
        "SELECT id_registro, disco_percentual, disco_total, disco_disponivel, disco_status, data_hora "
        "FROM registros ORDER BY id_registro DESC LIMIT %s", (20,))
    print("\nDisco")
    for l in cursor.fetchall():
        print(f"ID: {l[0]} | Uso: {l[1]}% | Total: {l[2]:.2f} GB | Disponível: {l[3]:.2f} GB | Status: {l[4]} | Timestamp: {l[5]}")


def ver_rede():
    cursor.execute(
        "SELECT id_registro, download_mb, upload_mb, data_hora "
        "FROM registros ORDER BY id_registro DESC LIMIT %s", (20,))
    print("\nRedes")
    for l in cursor.fetchall():
        print(f"ID: {l[0]} | Download: {l[1]} MB | Upload: {l[2]} MB | Timestamp: {l[3]}")


def ver_tudo():
    cursor.execute(
        "SELECT id_registro, cpu_percentual, cpu_status, ram_percentual, ram_status, "
        "disco_percentual, disco_status, download_mb, upload_mb, status_geral, data_hora "
        "FROM registros ORDER BY id_registro DESC LIMIT %s", (20,))
    print("\nTodos os dados")
    for l in cursor.fetchall():
        print(f"ID: {l[0]} | CPU: {l[1]}% ({l[2]}) | RAM: {l[3]}% ({l[4]}) | Disco: {l[5]}% ({l[6]}) "
              f"| Download: {l[7]} MB | Upload: {l[8]} MB | Status geral: {l[9]} | Timestamp: {l[10]}")


def deletar_ultimos(qtd=5):
    cursor.execute(f"DELETE FROM registros ORDER BY id_registro DESC LIMIT {int(qtd)}")
    conexao.commit()
    print(f"Os {qtd} últimos registros foram deletados.")


def atualizar_ultimos(qtd=3):
    cursor.execute(f"UPDATE registros SET data_hora = NOW() ORDER BY id_registro DESC LIMIT {int(qtd)}")
    conexao.commit()
    print(f"Os {qtd} últimos registros foram atualizados para a data atual.")


# MENU

def menu():
    while True:
        print("\nMENU")
        print("1 - Capturar dados (contínuo)")
        print("2 - Ver todos os dados")
        print("3 - Ver CPU")
        print("4 - Ver memória")
        print("5 - Ver disco")
        print("6 - Ver redes")
        print("7 - Deletar os últimos 5 registros")
        print("8 - Atualizar os 3 últimos registros para a data atual")
        print("9 - Sair")
        print("-----------------------------")

        opcao = input("Digite o que você quer: ").strip()

        if opcao == "1":
            captura_continua()
            continue
        elif opcao == "2":
            ver_tudo()
        elif opcao == "3":
            ver_cpu()
        elif opcao == "4":
            ver_ram()
        elif opcao == "5":
            ver_disco()
        elif opcao == "6":
            ver_rede()
        elif opcao == "7":
            deletar_ultimos(5)
        elif opcao == "8":
            atualizar_ultimos(3)
        elif opcao == "9":
            print("\nEncerrando programa...")
            break
        else:
            print("\nOpção inválida, digite um número de 1 a 9.")
            continue

        input("\nPressione ENTER para voltar ao menu...")


try:
    menu()
finally:
    cursor.close()
    conexao.close()