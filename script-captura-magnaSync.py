import time as t

import psutil as p
from mysql.connector import connection

INTERVALO_CAPTURA = 3     # segundos entre leituras
GB = 1024 ** 3
MB = 1000000

# funções do psutil que precisam de um argumento para funcionar
ARGUMENTOS = {"disk_usage": "/", "cpu_percent": 1}

conexao = connection.MySQLConnection(
    host="localhost",
    user="aluno2",
    password="sptech",
    database="magnasync",
)
conexao.autocommit = True   # assim o menu enxerga o que for inserido no banco sem reiniciar
cursor = conexao.cursor()

# Mac Adress

def pegar_mac():
    stats = p.net_if_stats()
    for interface, enderecos in p.net_if_addrs().items():
        if interface not in stats or not stats[interface].isup:
            continue
        for endereco in enderecos:
            if endereco.family == p.AF_LINK:
                so_digitos = endereco.address.replace("-", "").replace(":", "")
                if so_digitos != "" and so_digitos != "000000000000":
                    return endereco.address.replace("-", ":").upper()
    return None


def buscar_equipamento(mac):
    cursor.execute("SELECT id FROM equipamento WHERE mac_adress = %s", (mac,))
    resultado = cursor.fetchone()
    if resultado is None:
        return None
    return resultado[0]


# CADASTRO

def cadastrar_maquina(mac):
    if buscar_equipamento(mac) is not None:
        print("\nEsta máquina já está cadastrada. Faça o login.")
        return

    cursor.execute("SELECT id, nome FROM hospital")
    hospitais = cursor.fetchall()

    if len(hospitais) == 0:
        print("\nNenhum hospital cadastrado no banco.")
        return

    print("\nHospitais cadastrados:")
    for hospital in hospitais:
        print(f"{hospital[0]} - {hospital[1]}")

    hospital_id = input("ID do hospital: ").strip()
    if hospital_id not in [str(hospital[0]) for hospital in hospitais]:
        print("\nHospital inválido.")
        return

    
    # Dados que não mudam esses componentes ja estão fixos na máquina

    nucleos_logicos = p.cpu_count(logical=True)
    nucleos_fisicos = p.cpu_count(logical=False) or nucleos_logicos
    freq = p.cpu_freq()
    frequencia_maxima = freq.max if freq and freq.max else 0
    memoria_total = f"{round(p.virtual_memory().total / GB, 1)} GB"
    capacidade_total = f"{round(p.disk_usage('/').total / GB, 1)} GB"

    print("\nDados Capturados:")
    print(f"MAC Address: {mac}")
    print(f"Núcleos Físicos: {nucleos_fisicos}")
    print(f"Núcleos Lógicos: {nucleos_logicos}")
    print(f"Frequência Máxima: {frequencia_maxima} MHz")
    print(f"Memória Total: {memoria_total}")
    print(f"Capacidade de Disco: {capacidade_total}")

    comando = """
        INSERT INTO equipamento
        (mac_adress, nucleos_fisicos, nucleos_logicos, frequencia_maxima, memoria_total, capacidade_total, hospital_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(comando, (mac, nucleos_fisicos, nucleos_logicos, frequencia_maxima,
                             memoria_total, capacidade_total, hospital_id))

    print("\nMáquina cadastrada! Faça o login acessando a Opção 1.")


# LEITURA DO COMPONENTE (o comando vem do banco)

def ler_valor(biblioteca, comando, medida):
    if biblioteca != "psutil":
        raise Exception(f"biblioteca {biblioteca} não suportada")

    # ex.: 'virtual_memory.percent' -> psutil.virtual_memory().percent
    partes = comando.split(".")
    funcao = getattr(p, partes[0])

    if partes[0] in ARGUMENTOS:
        valor = funcao(ARGUMENTOS[partes[0]])
    else:
        valor = funcao()

    for atributo in partes[1:]:
        valor = getattr(valor, atributo)

    if hasattr(valor, "current"):    # cpu_freq devolve (current, min, max)
        valor = valor.current

    if medida == "GB":
        valor = valor / GB
    elif medida == "MB":
        valor = valor / MB

    return round(valor, 2)


def pegar_parametro(id_equipamento, id_componente):
    # a leitura só pode ser gravada se existir o parâmetro (equipamento + componente)
    cursor.execute(
        "SELECT id FROM parametro WHERE fkEquipamento = %s AND fkComponente = %s",
        (id_equipamento, id_componente))
    resultado = cursor.fetchone()
    if resultado is not None:
        return resultado[0]

    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM parametro")
    novo_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO parametro (id, fkEquipamento, fkComponente) VALUES (%s, %s, %s)",
        (novo_id, id_equipamento, id_componente))
    return novo_id


def monitorar(id_equipamento, opcao):
    id_componente, tipo, biblioteca, comando, medida = opcao
    id_parametro = None

    print(f"\nMonitorando {tipo}. Pressione 'ctrl + c' para voltar ao menu.")
    while True:
        try:
            valor = ler_valor(biblioteca, comando, medida)

            if id_parametro is None:   # só cria o parâmetro depois que a leitura funcionou
                id_parametro = pegar_parametro(id_equipamento, id_componente)

            cursor.execute(
                "INSERT INTO leitura (fkEquipamento, fkComponente, fkMetrica, valor, data_hora) "
                "VALUES (%s, %s, %s, %s, NOW())",
                (id_equipamento, id_componente, id_parametro, valor))

            print(f"{tipo}: {valor} {medida}")
            t.sleep(INTERVALO_CAPTURA)
        except KeyboardInterrupt:
            print("\nMonitoramento interrompido. Voltando ao menu...")
            break
        except Exception as erro:
            print(f"\nNão foi possível monitorar {tipo}: {erro}")
            break


# MENUS (Select pega os componentes que estão cadastrados no banco)

def menu_opcoes(id_equipamento, componente):
    cursor.execute(
        "SELECT c.id, c.tipo, c.biblioteca, c.comando, d.medida "
        "FROM componente c JOIN dado d ON d.id = c.dado_id "
        "WHERE SUBSTRING_INDEX(c.tipo, ' - ', 1) = %s ORDER BY c.id", (componente,))
    opcoes = cursor.fetchall()


    #Seleciona qual componente dos que estão cadastrados você quer monitorar

    print(f"\n{componente} - o que monitorar")
    for i in range(len(opcoes)):
        print(f"{i + 1} - {opcoes[i][1]} ({opcoes[i][4]})")
    print("0 - Voltar")

    escolha = input("Digite o que você quer: ").strip()

    if escolha == "0":
        return
    if escolha.isdigit() and 1 <= int(escolha) <= len(opcoes):
        monitorar(id_equipamento, opcoes[int(escolha) - 1])
    else:
        print("\nOpção inválida.")


def menu_componentes(id_equipamento):
    while True:
        cursor.execute(
            "SELECT SUBSTRING_INDEX(tipo, ' - ', 1) AS grupo FROM componente "
            "GROUP BY grupo ORDER BY MIN(id)")
        componentes = cursor.fetchall()

        print("\nMENU - Componentes")
        for i in range(len(componentes)):
            print(f"{i + 1} - {componentes[i][0]}")
        print("0 - Sair")
        print("-----------------------------")

        escolha = input("Qual componente você quer monitorar: ").strip()

        if escolha == "0":
            print("\nEncerrando programa...")
            break
        if escolha.isdigit() and 1 <= int(escolha) <= len(componentes):
            menu_opcoes(id_equipamento, componentes[int(escolha) - 1][0])
        else:
            print("\nOpção inválida.")


# Login e cadastro da maquina pelo MAC ADRESSS

def menu_login(mac):
    while True:
        print("\nSeja Bem-Vindo ao Programa de Captura de Dados de Hardware!")
        print(f"MAC desta máquina: {mac}")
        print("1 - Login")
        print("2 - Cadastrar máquina")
        print("3 - Sair")
        print("-----------------------------")

        opcao = input("Digite o que você quer: ").strip()

        if opcao == "1":
            id_equipamento = buscar_equipamento(mac)
            if id_equipamento is not None:
                print("\nAcesso Liberado!")
                menu_componentes(id_equipamento)
                break

            #Caso a maquina não esteja cadastrada pede para cadastrar
            print("\nMáquina não cadastrada.")
            resposta = input("Deseja cadastrar agora? (s/n): ").strip().lower()
            if resposta == "s":
                cadastrar_maquina(mac)
        elif opcao == "2":
            cadastrar_maquina(mac)

            #Caso não queria ele fecha o programa
        elif opcao == "3":
            print("\nPrograma Encerrado")
            break
        else:
            print("\nOpção inválida, digite um número de 1 a 3.")

try:
    mac = pegar_mac()
    if mac is None:
        print("Não foi possível identificar o MAC address desta máquina.")
    else:
        menu_login(mac)
finally:
    cursor.close()
    conexao.close()