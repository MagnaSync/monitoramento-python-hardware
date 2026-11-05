import time as t
import os

import psutil as p
from mysql.connector import connection

INTERVALO_CAPTURA = 3     # segundos entre leituras
GB = 1024 ** 3
MB = 1000000

ARGUMENTOS = {"disk_usage": "/", "cpu_percent": 1}

CATEGORIAS = {"Atenção": 1, "Crítico": 2, "Bloqueio": 3}   # ids da tabela categoria_alerta

conexao = connection.MySQLConnection(
    host=os.environ.get("DB_HOST", "54.224.55.155"),
    user=os.environ.get("DB_USER", "aluno2"),
    password=os.environ.get("DB_PASSWORD", "sptech"),
    database=os.environ.get("DB_DATABASE", "magnasync"),
)
conexao.autocommit = True   # assim o menu enxerga o que for inserido no banco sem reiniciar
cursor = conexao.cursor()


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


# CADASTRO DA MÁQUINA

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

    cursor.execute("INSERT INTO equipamento (mac_adress, hospital_id) VALUES (%s, %s)", (mac, hospital_id))

    print("\nMáquina cadastrada! Faça o login acessando a Opção 1.")


# Componentes que não mudam da máquina (cadastra na tabela componente se ainda não existir)

def detectar_componentes():
    nucleos_logicos = p.cpu_count(logical=True)
    nucleos_fisicos = p.cpu_count(logical=False) or nucleos_logicos
    return [
        ("Ram", round(p.virtual_memory().total / GB), "GB"),
        ("Disco", round(p.disk_usage("/").total / GB), "GB"),
        ("Processador", nucleos_fisicos, "NucleosFisicos"),
        ("Processador", nucleos_logicos, "NucleosLogicos"),
    ]


def pegar_componente(tipo, valor, medida):
    cursor.execute(
        "SELECT c.id FROM componente c "
        "JOIN tipoComponente t ON t.id = c.fkTipo "
        "JOIN unidade u ON u.id = c.fkUnidade "
        "WHERE t.tipo = %s AND c.valor = %s AND u.medida = %s", (tipo, valor, medida))
    resultado = cursor.fetchone()
    if resultado is not None:
        return resultado[0]

    cursor.execute("SELECT id FROM tipoComponente WHERE tipo = %s", (tipo,))
    id_tipo = cursor.fetchone()
    cursor.execute("SELECT id FROM unidade WHERE medida = %s", (medida,))
    id_unidade = cursor.fetchone()

    if id_tipo is None or id_unidade is None:
        print(f"Não foi possível cadastrar {tipo} {valor} {medida}: tipo ou unidade não existe no banco.")
        return None

    cursor.execute(
        "INSERT INTO componente (valor, fkTipo, fkUnidade) VALUES (%s, %s, %s)",
        (valor, id_tipo[0], id_unidade[0]))
    print(f"Componente cadastrado: {tipo} - {valor} {medida}")
    return cursor.lastrowid


def verificar_componentes():
    print("\nVerificando os componentes da máquina...")
    ids = []
    for tipo, valor, medida in detectar_componentes():
        id_componente = pegar_componente(tipo, valor, medida)
        if id_componente is not None:
            ids.append(id_componente)
    return ids


def listar_componentes(ids):
    marcadores = ", ".join(["%s"] * len(ids))
    cursor.execute(
        "SELECT c.id, t.id, t.tipo, c.valor, u.medida "
        "FROM componente c "
        "JOIN tipoComponente t ON t.id = c.fkTipo "
        "JOIN unidade u ON u.id = c.fkUnidade "
        f"WHERE c.id IN ({marcadores}) ORDER BY c.id", ids)
    return cursor.fetchall()


def mostrar_componentes(componentes):
    for i in range(len(componentes)):
        c = componentes[i]
        print(f"{i + 1} - {c[2]} - {c[3]} {c[4]}")
    print("0 - Voltar")


def escolher(lista):
    escolha = input("Digite o que você quer: ").strip()
    if escolha.isdigit() and 1 <= int(escolha) <= len(lista):
        return lista[int(escolha) - 1]
    if escolha != "0":
        print("\nOpção inválida.")
    return None


# Leitura do valor o comando vem do banco

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
    # a tabela leitura exige uma linha em parametro (máquina + componente); aqui ela é criada sozinha, sem métrica
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


def classificar(tipo, valor):
    if tipo == "Ram":
        atencao, critico, bloqueio = 75, 85, 90
    elif tipo == "Disco" or tipo == "Processador":
        atencao, critico, bloqueio = 80, 90, 95
    else:
        return "Normal"

    if valor >= bloqueio:
        return "Bloqueio"
    elif valor >= critico:
        return "Crítico"
    elif valor >= atencao:
        return "Atenção"
    return "Normal"


def monitorar(id_equipamento, componente, opcao):
    id_componente = componente[0]
    id_parametro = None
    descricao, biblioteca, comando, medida = opcao[1], opcao[2], opcao[3], opcao[4]
    nome = f"{componente[2]} - {descricao}"
    status_anterior = "Normal"

    print(f"\nMonitorando {nome}. Pressione 'ctrl + c' para voltar ao menu.")
    while True:
        try:
            valor = ler_valor(biblioteca, comando, medida)

            if id_parametro is None:   # só cria o parâmetro depois que a leitura funcionou
                id_parametro = pegar_parametro(id_equipamento, id_componente)

            cursor.execute(
                "INSERT INTO leitura (fkEquipamento, fkComponente, fkMetrica, valor, data_hora) "
                "VALUES (%s, %s, %s, %s, NOW())",
                (id_equipamento, id_componente, id_parametro, valor))
            id_leitura = cursor.lastrowid

            if medida == "%":    # a discretização só vale para percentual
                status = classificar(componente[2], valor)
                print(f"{nome}: {valor} {medida} | {status}")
                if status != "Normal" and status != status_anterior:   # grava só quando o status muda
                    cursor.execute(
                        "INSERT INTO alerta (data_hora, leitura_id, categoria_alerta_id) VALUES (NOW(), %s, %s)",
                        (id_leitura, CATEGORIAS[status]))
                status_anterior = status
            else:
                print(f"{nome}: {valor} {medida}")

            t.sleep(INTERVALO_CAPTURA)
        except KeyboardInterrupt:
            print("\nMonitoramento interrompido. Voltando ao menu...")
            break
        except Exception as erro:
            print(f"\nNão foi possível monitorar {nome}: {erro}")
            break


def menu_monitorar(id_equipamento, ids):
    componentes = listar_componentes(ids)

    print("\nMONITORAR - escolha o componente")
    mostrar_componentes(componentes)
    componente = escolher(componentes)
    if componente is None:
        return

    cursor.execute(
        "SELECT cm.id, cm.descricao, cm.biblioteca, cm.comando, u.medida "
        "FROM comandos cm JOIN unidade u ON u.id = cm.fkUnidade "
        "WHERE cm.fkTipo = %s ORDER BY cm.id", (componente[1],))
    opcoes = cursor.fetchall()

    print(f"\n{componente[2]} - o que monitorar")
    for i in range(len(opcoes)):
        print(f"{i + 1} - {opcoes[i][1]} ({opcoes[i][4]})")
    print("0 - Voltar")

    opcao = escolher(opcoes)
    if opcao is not None:
        monitorar(id_equipamento, componente, opcao)


# MENU PRINCIPAL

def menu_principal(id_equipamento):
    ids = verificar_componentes()
    if len(ids) == 0:
        print("\nNenhum componente da máquina pôde ser cadastrado.")
        return

    while True:
        print("\nMENU")
        print("1 - Monitorar componentes")
        print("2 - Sair")
        print("-----------------------------")

        opcao = input("Digite o que você quer: ").strip()

        if opcao == "1":
            menu_monitorar(id_equipamento, ids)
        elif opcao == "2":
            print("\nEncerrando programa...")
            break
        else:
            print("\nOpção inválida, digite 1 ou 2.")


# LOGIN / CADASTRO

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
                menu_principal(id_equipamento)
                break

            print("\nMáquina não cadastrada.")
            resposta = input("Deseja cadastrar agora? (s/n): ").strip().lower()
            if resposta == "s":
                cadastrar_maquina(mac)
        elif opcao == "2":
            cadastrar_maquina(mac)
        elif opcao == "3":
            print("\nAté a próxima!")
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