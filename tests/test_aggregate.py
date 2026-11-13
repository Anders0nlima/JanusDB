import collections
import random
import pytest

from src.engine import Engine
from src.operadores import Operador
from src.aggregate import Aggregate


class OperadorLista(Operador):
    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.pos = 0
        self.aberto = False

    def abre(self):
        self.pos = 0
        self.aberto = True

    def proximo(self):
        if not self.aberto or self.pos >= len(self.linhas):
            return None
        linha = self.linhas[self.pos]
        self.pos += 1
        return linha

    def fecha(self):
        self.aberto = False


def test_aggregate_operador_unitario():
    # Tupla: (depto, salario)
    dados = [
        ("TI", 100),
        ("RH", 50),
        ("TI", 200),
        ("TI", 300),
        ("RH", 150),
    ]
    # Agregados: COUNT(*) -> ("COUNT", None), SUM(salario) -> ("SUM", 1)
    # Com GROUP BY na coluna 0 (depto)
    agg = Aggregate(
        OperadorLista(dados),
        agregados=[("COUNT", None), ("SUM", 1)],
        group_by_idx=0,
    )
    with agg:
        linhas = list(agg)

    # Converte em dict para comparação independente de ordem
    resultado = {r[0]: (r[1], r[2]) for r in linhas}
    assert resultado == {
        "TI": (3, 600),
        "RH": (2, 200),
    }

    # Sem GROUP BY: agregação global
    agg_global = Aggregate(
        OperadorLista(dados),
        agregados=[("COUNT", None), ("SUM", 1)],
        group_by_idx=None,
    )
    with agg_global:
        linhas_global = list(agg_global)
    assert linhas_global == [(5, 800)]


def test_aggregate_sql_count_e_sum_sem_group_by(tmp_path):
    caminho = str(tmp_path / "banco_agg.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE func (id INT, depto CHAR(10), salario INT)")
        db.executa("INSERT INTO func VALUES (1, 'TI', 5000)")
        db.executa("INSERT INTO func VALUES (2, 'TI', 6000)")
        db.executa("INSERT INTO func VALUES (3, 'RH', 4000)")

        # COUNT(*) global
        assert db.executa("SELECT COUNT(*) FROM func") == "3\n(1 linha)"

        # SUM(salario) global
        assert db.executa("SELECT SUM(salario) FROM func") == "15000\n(1 linha)"

        # COUNT(*) e SUM(salario) juntos
        assert db.executa("SELECT COUNT(*), SUM(salario) FROM func") == "3|15000\n(1 linha)"

        # Com WHERE
        assert db.executa("SELECT COUNT(*), SUM(salario) FROM func WHERE depto = 'TI'") == "2|11000\n(1 linha)"


def test_aggregate_sql_group_by(tmp_path):
    caminho = str(tmp_path / "banco_groupby.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE func (id INT, depto CHAR(10), salario INT)")
        db.executa("INSERT INTO func VALUES (1, 'TI', 5000)")
        db.executa("INSERT INTO func VALUES (2, 'TI', 7000)")
        db.executa("INSERT INTO func VALUES (3, 'RH', 4000)")
        db.executa("INSERT INTO func VALUES (4, 'Vendas', 3000)")
        db.executa("INSERT INTO func VALUES (5, 'RH', 4500)")

        # GROUP BY com ORDER BY
        res = db.executa("SELECT depto, COUNT(*), SUM(salario) FROM func GROUP BY depto ORDER BY depto ASC")
        linhas = res.splitlines()
        assert linhas[0] == "RH|2|8500"
        assert linhas[1] == "TI|2|12000"
        assert linhas[2] == "Vendas|1|3000"
        assert linhas[3] == "(3 linhas)"

        # Invertendo a ordem das colunas projetadas
        res_inv = db.executa("SELECT COUNT(*), depto FROM func GROUP BY depto ORDER BY depto DESC")
        linhas_inv = res_inv.splitlines()
        assert linhas_inv[0] == "1|Vendas"
        assert linhas_inv[1] == "2|TI"
        assert linhas_inv[2] == "2|RH"
        assert linhas_inv[3] == "(3 linhas)"

        # GROUP BY combinado com WHERE
        res_where = db.executa("SELECT depto, COUNT(*), SUM(salario) FROM func WHERE depto = 'TI' GROUP BY depto")
        assert res_where == "TI|2|12000\n(1 linha)"


def test_aggregate_tabela_vazia(tmp_path):
    caminho = str(tmp_path / "banco_vazio.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE func (id INT, depto CHAR(10), salario INT)")

        # Decisão 1: COUNT(*) sobre tabela vazia devolve 0 (1 linha)
        assert db.executa("SELECT COUNT(*) FROM func") == "0\n(1 linha)"

        # Decisão 2: SUM sobre conjunto vazio devolve 0 (1 linha)
        assert db.executa("SELECT SUM(salario) FROM func") == "0\n(1 linha)"

        # Juntos: 0|0 (1 linha)
        assert db.executa("SELECT COUNT(*), SUM(salario) FROM func") == "0|0\n(1 linha)"

        # Decisão 3: GROUP BY sobre tabela vazia devolve 0 linhas
        assert db.executa("SELECT depto, COUNT(*) FROM func GROUP BY depto") == "(0 linhas)"


def test_aggregate_sum_acima_de_32_bits(tmp_path):
    caminho = str(tmp_path / "banco_bigint.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE contas (id INT, valor INT)")
        # 3 bilhões cabe em uint32 (INT de 4 bytes sem sinal no minidb)
        # Ao somar duas vezes (3 bi + 3 bi = 6 bi), excede 32 bits (4.294.967.295)
        db.executa("INSERT INTO contas VALUES (1, 3000000000)")
        db.executa("INSERT INTO contas VALUES (2, 3000000000)")

        res = db.executa("SELECT SUM(valor) FROM contas")
        assert res == "6000000000\n(1 linha)"


def test_aggregate_dados_aleatorios(tmp_path):
    caminho = str(tmp_path / "banco_aleatorio.db")
    deptos = ["TI", "RH", "MKT", "FIN", "DIR"]
    random.seed(123)

    dados = []
    contagem_esperada = collections.Counter()
    soma_esperada = collections.defaultdict(int)

    with Engine(caminho) as db:
        db.executa("CREATE TABLE func (id INT, depto CHAR(10), salario INT)")
        for i in range(100):
            d = random.choice(deptos)
            sal = random.randint(1000, 10000)
            dados.append((i, d, sal))
            contagem_esperada[d] += 1
            soma_esperada[d] += sal
            db.executa(f"INSERT INTO func VALUES ({i}, '{d}', {sal})")

        res = db.executa("SELECT depto, COUNT(*), SUM(salario) FROM func GROUP BY depto")
        for linha in res.splitlines()[:-1]:  # Ignora rodapé (N linhas)
            d, cnt, sm = linha.split("|")
            assert int(cnt) == contagem_esperada[d]
            assert int(sm) == soma_esperada[d]
