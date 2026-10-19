# ETL Portuário – CSV → DW
# Integra viagens e atualiza dimensões a partir do ficheiro dados.csv.

import os
import csv
from datetime import datetime
import pyodbc

# -----------------------------------------------------------
# 1. Configuração
# -----------------------------------------------------------

CSV_PATH = os.getenv("CSV_DADOS_PORTO", r"dados.csv")

MSSQL_HOST   = os.getenv("MSSQL_HOST", "127.0.0.1")
MSSQL_PORT   = int(os.getenv("MSSQL_PORT", "1433"))
MSSQL_USER   = os.getenv("MSSQL_USER", "sa")
MSSQL_PWD    = os.getenv("MSSQL_PWD",  "1234")
MSSQL_DB     = os.getenv("MSSQL_DB",   "Trabalho")
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")

conn = None
cursor = None

# Caches em memória
cache_tempo = {}
cache_detalhes = {}
cache_condutor = {}
cache_barco = {}
cache_localizacao = {}


# -----------------------------------------------------------
# 2. Ligação ao SQL Server
# -----------------------------------------------------------

def get_mssql_conn():
    conn_str = (
        f"DRIVER={{{MSSQL_DRIVER}}};"
        f"SERVER={MSSQL_HOST},{MSSQL_PORT};"
        f"DATABASE={MSSQL_DB};"
        f"UID={MSSQL_USER};PWD={MSSQL_PWD};"
        "TrustServerCertificate=Yes;"
    )
    return pyodbc.connect(conn_str)


# -----------------------------------------------------------
# 3. Funções auxiliares das dimensões
# -----------------------------------------------------------

def get_or_create_tempo(data_chegada_str):
    data_chegada_str = data_chegada_str.strip()

    if data_chegada_str in cache_tempo:
        return cache_tempo[data_chegada_str]

    data = datetime.strptime(data_chegada_str, "%d/%m/%Y").date()

    ano, mes, dia = data.year, data.month, data.day
    semestre = 1 if mes <= 6 else 2
    trimestre = 1 if mes <= 3 else 2 if mes <= 6 else 3 if mes <= 9 else 4

    id_tempo = ano * 10000 + mes * 100 + dia

    cursor.execute("SELECT id_tempo FROM dim_tempo WHERE id_tempo = ?", id_tempo)
    if cursor.fetchone():
        cache_tempo[data_chegada_str] = id_tempo
        return id_tempo

    cursor.execute("""
        INSERT INTO dim_tempo (id_tempo, data, ano, semestre, trimestre, mes, dia_semana)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        id_tempo, data, ano, semestre, trimestre, mes, data.strftime("%A")
    ))

    cache_tempo[data_chegada_str] = id_tempo
    return id_tempo


def get_or_create_detalhes():
    key = ("Marítima", "Concluída", "")

    cursor.execute("""
        SELECT id_detalhes FROM dim_detalhes
        WHERE tipo_viagem = ? AND status_viagem = ? AND observacoes = ?
    """, key)

    r = cursor.fetchone()
    if r:
        return r[0]

    cursor.execute("SELECT ISNULL(MAX(id_detalhes),0)+1 FROM dim_detalhes")
    novo = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO dim_detalhes (id_detalhes, tipo_viagem, status_viagem, observacoes)
        VALUES (?, ?, ?, '')
    """, (novo, key[0], key[1]))

    return novo


def get_or_create_condutor(nome, certificacao, idade, sexo):
    nome = nome.strip()
    cursor.execute("SELECT id_condutor FROM dim_condutor WHERE nome_condutor = ?", nome)

    r = cursor.fetchone()
    if r:
        return r[0]

    try: idade = int(idade)
    except: idade = None

    cursor.execute("""
        INSERT INTO dim_condutor (
            id_condutor, nome_condutor, certificacao,
            perfil_condutor, idade, genero
        )
        VALUES ((SELECT ISNULL(MAX(id_condutor),0)+1 FROM dim_condutor),
                ?, ?, ?, ?, ?)
    """, (nome, certificacao, None, idade, sexo))

    cursor.execute("SELECT id_condutor FROM dim_condutor WHERE nome_condutor = ?", nome)
    return cursor.fetchone()[0]


def get_or_create_barco(nome, tipo, capacidade):
    nome = nome.strip()
    cursor.execute("SELECT id_barco FROM dim_barco WHERE nome_barco = ?", nome)

    r = cursor.fetchone()
    if r:
        return r[0]

    try:
        cap_int = int(str(capacidade).replace("h", "").replace("m", "").strip())
    except:
        cap_int = None

    cursor.execute("SELECT ISNULL(MAX(id_barco),0)+1 FROM dim_barco")
    novo = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO dim_barco (
            id_barco, nome_barco, tipo_barco, tamanho,
            pais_registo, nome_empresa_barco,
            pais_empresa_barco, email_empresa_barco, capacidade_teu
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (novo, nome, tipo, None, None, None, None, None, cap_int))

    return novo


def get_or_create_localizacao(cidade, pais):
    cidade = cidade.strip()
    pais = pais.strip()

    cursor.execute("""
        SELECT id_localizacao FROM dim_localizacao
        WHERE nome_porto = ? AND pais = ?
    """, (cidade, pais))

    r = cursor.fetchone()
    if r:
        return r[0]

    cursor.execute("SELECT ISNULL(MAX(id_localizacao),0)+1 FROM dim_localizacao")
    novo = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO dim_localizacao (id_localizacao, nome_porto, pais, tipo_localizacao)
        VALUES (?, ?, ?, 'Porto Comercial')
    """, (novo, cidade, pais))

    return novo


# -----------------------------------------------------------
# 4. Main – ETL Fact_Viagem
# -----------------------------------------------------------

def main():
    global conn, cursor

    print("1 - Ligação ao SQL Server")
    conn = get_mssql_conn()
    cursor = conn.cursor()

    try:
        print("2 - A abrir CSV...")

        cursor.execute("SELECT ISNULL(MAX(id_viagem), 0) FROM fact_viagem;")
        next_id_viagem = cursor.fetchone()[0] + 1

        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")

            count = 0

            for row in reader:

                cidade_dest = (row["cidade_destino"] or "").strip().lower()
                pais_dest   = (row["pais_destino"] or "").strip().lower()

                if cidade_dest not in ("figueira da foz", "figfoz", "figueiradafoz"):
                    continue
                if pais_dest != "portugal":
                    continue

                id_viagem = next_id_viagem
                next_id_viagem += 1

                id_tempo    = get_or_create_tempo(row["datachegada"])
                id_detalhes = get_or_create_detalhes()
                id_condutor = get_or_create_condutor(row["nomecondutor"], row["certificacao"], row["idadecondutor"], row["sexo"])
                id_barco    = get_or_create_barco(row["nomebarco"], row["tipobarco"], row["capacidadeteu"])
                id_origem   = get_or_create_localizacao(row["cidade_origem"], row["pais_origem"])
                id_destino  = get_or_create_localizacao(row["cidade_destino"], row["pais_destino"])

                taxa_str = str(row.get("taxa", "0")).replace(",", ".")
                try: valor = float(taxa_str)
                except: valor = 0.0

                receita = valor * 0.87

                cursor.execute("""
                    INSERT INTO fact_viagem (
                        id_viagem, id_tempo, id_barco, id_condutor,
                        id_detalhes, id_origem, id_destino,
                        receita_total_taxas, num_contentores, peso_total, teu_total
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_viagem, id_tempo, id_barco, id_condutor,
                    id_detalhes, id_origem, id_destino,
                    receita, 0, 0.0, 0.0
                ))

                count += 1
                if count % 100 == 0:
                    conn.commit()

        conn.commit()
        print(f"ETL concluído! Linhas inseridas: {count}")

    except Exception as e:
        print("ERRO no ETL:", e)
        conn.rollback()

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
