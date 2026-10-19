# ETL Portuário – MySQL → DW
# Carrega dimensões base e tabela de factos a partir da BD operacional.

import os
import sys
import mysql.connector as mysql
import pyodbc
from datetime import datetime

# -----------------------------------------------------------
# 1. Configuração das ligações aos SGBD
# -----------------------------------------------------------

# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PWD  = os.getenv("MYSQL_PWD",  "1234")
MYSQL_DB   = os.getenv("MYSQL_DB",   "Trabalho")

# SQL Server
MSSQL_HOST   = os.getenv("MSSQL_HOST", "127.0.0.1")
MSSQL_PORT   = int(os.getenv("MSSQL_PORT", "1433"))
MSSQL_USER   = os.getenv("MSSQL_USER", "sa")
MSSQL_PWD    = os.getenv("MSSQL_PWD",  "1234")
MSSQL_DB     = os.getenv("MSSQL_DB",   "Trabalho")
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")


# -----------------------------------------------------------
# 2. Ligações aos SGBD
# -----------------------------------------------------------

def get_mysql_conn():
    return mysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        autocommit=True,
        charset="utf8mb4"
    )

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
# 3. ETL das Dimensões
# -----------------------------------------------------------

def carregar_dim_barco(mysql_cur, sqlsrv_cur):
    print("  - A carregar Dim_Barco...")
    sqlsrv_cur.execute("DELETE FROM dim_barco;")

    mysql_cur.execute("""
        SELECT
            b.idbarco, b.nomebarco, b.tipobarco, b.tamanhobarco,
            b.paisbarco, b.capacidadeteu,
            e.nomeempresabarco, e.paisempresabarco, e.emailempresabarco
        FROM barco b
        JOIN empresabarco e ON b.empresabarco_idempresabarco = e.idempresabarco
        ORDER BY b.idbarco;
    """)

    rows = mysql_cur.fetchall()
    print(f"    Registos lidos (barco): {len(rows)}")

    for r in rows:
        tamanho = float(r["tamanhobarco"]) if r["tamanhobarco"] is not None else None

        sqlsrv_cur.execute("""
            INSERT INTO dim_barco (
                id_barco, nome_barco, tipo_barco, tamanho,
                pais_registo, nome_empresa_barco,
                pais_empresa_barco, email_empresa_barco, capacidade_teu
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["idbarco"], r["nomebarco"], r["tipobarco"], tamanho,
            r["paisbarco"], r["nomeempresabarco"],
            r["paisempresabarco"], r["emailempresabarco"], r["capacidadeteu"]
        ))


def carregar_dim_localizacao(mysql_cur, sqlsrv_cur):
    print("  - A carregar Dim_Localizacao...")
    sqlsrv_cur.execute("DELETE FROM dim_localizacao;")

    mysql_cur.execute("""
        SELECT idlocalizacao, cidade, pais
        FROM localizacao
        ORDER BY idlocalizacao;
    """)

    rows = mysql_cur.fetchall()
    print(f"    Registos lidos (localizacao): {len(rows)}")

    for r in rows:
        sqlsrv_cur.execute("""
            INSERT INTO dim_localizacao (
                id_localizacao, nome_porto, pais, tipo_localizacao
            )
            VALUES (?, ?, ?, ?)
        """, (
            r["idlocalizacao"],
            r["cidade"],
            r["pais"],
            "Porto Comercial"
        ))


def carregar_dim_condutor(mysql_cur, sqlsrv_cur):
    print("  - A carregar Dim_Condutor...")
    sqlsrv_cur.execute("DELETE FROM dim_condutor;")

    mysql_cur.execute("""
        SELECT idcondutor, nomecondutor, certificacao, idadecondutor
        FROM condutor
        ORDER BY idcondutor;
    """)

    rows = mysql_cur.fetchall()
    print(f"    Registos lidos (condutor): {len(rows)}")

    for r in rows:
        idade = int(r["idadecondutor"]) if r["idadecondutor"] is not None else None

        sqlsrv_cur.execute("""
            INSERT INTO dim_condutor (
                id_condutor, nome_condutor, certificacao,
                perfil_condutor, idade, genero
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            r["idcondutor"],
            r["nomecondutor"],
            r["certificacao"],
            None,
            idade,
            None
        ))


# -----------------------------------------------------------
# 4. Funções auxiliares para dimensões geradas
# -----------------------------------------------------------

def get_or_create_tempo(sqlsrv_cur, data_chegada):
    if data_chegada is None:
        return None

    id_tempo = data_chegada.year * 10000 + data_chegada.month * 100 + data_chegada.day
    sqlsrv_cur.execute("SELECT id_tempo FROM dim_tempo WHERE id_tempo = ?", (id_tempo,))

    if sqlsrv_cur.fetchone():
        return id_tempo

    semestre = 1 if data_chegada.month <= 6 else 2
    trimestre = (data_chegada.month - 1)//3 + 1

    sqlsrv_cur.execute("""
        INSERT INTO dim_tempo (id_tempo, data, ano, semestre, trimestre, mes, dia_semana)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        id_tempo, data_chegada, data_chegada.year, semestre,
        trimestre, data_chegada.month, data_chegada.strftime("%A")
    ))
    return id_tempo


def get_or_create_detalhes(sqlsrv_cur, tipo, status):
    sqlsrv_cur.execute("""
        SELECT id_detalhes
        FROM dim_detalhes
        WHERE tipo_viagem = ? AND status_viagem = ?
    """, (tipo, status))
    
    r = sqlsrv_cur.fetchone()
    if r:
        return r[0]

    sqlsrv_cur.execute("SELECT ISNULL(MAX(id_detalhes),0)+1 FROM dim_detalhes")
    novo_id = sqlsrv_cur.fetchone()[0]

    sqlsrv_cur.execute("""
        INSERT INTO dim_detalhes (id_detalhes, tipo_viagem, status_viagem, observacoes)
        VALUES (?, ?, ?, '')
    """, (novo_id, tipo, status))
    return novo_id


# -----------------------------------------------------------
# 5. ETL da Fact_Viagem
# -----------------------------------------------------------

def carregar_fact_viagem(mysql_cur, sqlsrv_cur):
    print("\n  - A carregar FACT_VIAGEM a partir do MySQL...")
    sqlsrv_cur.execute("DELETE FROM fact_viagem;")

    mysql_cur.execute("""
        SELECT
            idviagem, datachegada, status, tipoviagem,
            localizacao_idlocalizacao AS origem,
            localizacao_idlocalizacao1 AS destino,
            barco_idbarco AS barco,
            condutor_idcondutor AS condutor
        FROM viagem
        WHERE status = 'concluida'
    """)

    viagens = mysql_cur.fetchall()
    print(f"    Viagens encontradas: {len(viagens)}")

    for v in viagens:
        data = datetime.combine(v["datachegada"], datetime.min.time()) if v["datachegada"] else None
        id_tempo = get_or_create_tempo(sqlsrv_cur, data)
        id_detalhes = get_or_create_detalhes(sqlsrv_cur, v["tipoviagem"], v["status"])

        sqlsrv_cur.execute("""
            INSERT INTO fact_viagem (
                id_viagem, id_tempo, id_barco, id_condutor,
                id_detalhes, id_origem, id_destino,
                receita_total_taxas, num_contentores, peso_total, teu_total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            v["idviagem"], id_tempo, v["barco"], v["condutor"],
            id_detalhes, v["origem"], v["destino"],
            0.0, 0, 0.0, 0.0
        ))


# -----------------------------------------------------------
# 6. Main
# -----------------------------------------------------------

def main():
    print("1 - Ligação ao MySQL")
    mysql_conn = get_mysql_conn()
    mysql_cur = mysql_conn.cursor(dictionary=True)

    print("2 - Ligação ao SQL Server")
    sqlsrv_conn = get_mssql_conn()
    sqlsrv_cur = sqlsrv_conn.cursor()

    try:
        print("\n3 - ETL das Dimensões")
        carregar_dim_barco(mysql_cur, sqlsrv_cur)
        carregar_dim_localizacao(mysql_cur, sqlsrv_cur)
        carregar_dim_condutor(mysql_cur, sqlsrv_cur)

        print("\n4 - ETL da Fact")
        carregar_fact_viagem(mysql_cur, sqlsrv_cur)

        sqlsrv_conn.commit()
        print("\n5 - ETL concluído com sucesso!")

    except Exception as e:
        print("ERRO no ETL:", e)
        sqlsrv_conn.rollback()

    finally:
        mysql_conn.close()
        sqlsrv_conn.close()


if __name__ == "__main__":
    sys.exit(main())
