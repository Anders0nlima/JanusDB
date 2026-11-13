import pytest
from src.engine import Engine
from src.catalog import ErroSemantico


def test_combinada_where_group_by_order_by_asc(tmp_path):
    caminho = str(tmp_path / "banco_comb.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE vendas (id INT, vendedor CHAR(10), valor INT, regiao CHAR(10))")
        db.executa("INSERT INTO vendas VALUES (1, 'Alice', 100, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (2, 'Bob', 200, 'Norte')")
        db.executa("INSERT INTO vendas VALUES (3, 'Alice', 300, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (4, 'Carlos', 400, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (5, 'Bob', 500, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (6, 'Carlos', 600, 'Norte')")

        # Filtra apenas regiao = 'Sul', agrupa por vendedor e ordena ASC
        res = db.executa(
            "SELECT vendedor, COUNT(*), SUM(valor) FROM vendas WHERE regiao = 'Sul' GROUP BY vendedor ORDER BY vendedor ASC"
        )
        linhas = res.splitlines()
        # Alice: 100 + 300 = 400 (2 vendas)
        assert linhas[0] == "Alice|2|400"
        # Bob: 500 (1 venda no Sul)
        assert linhas[1] == "Bob|1|500"
        # Carlos: 400 (1 venda no Sul)
        assert linhas[2] == "Carlos|1|400"
        assert linhas[3] == "(3 linhas)"
        assert db.cache.pin_count == 0


def test_combinada_where_group_by_order_by_desc(tmp_path):
    caminho = str(tmp_path / "banco_comb_desc.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE vendas (id INT, vendedor CHAR(10), valor INT, regiao CHAR(10))")
        db.executa("INSERT INTO vendas VALUES (1, 'Alice', 100, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (2, 'Bob', 200, 'Sul')")
        db.executa("INSERT INTO vendas VALUES (3, 'Carlos', 300, 'Sul')")

        # Inverte projeção e ordena DESC
        res = db.executa(
            "SELECT SUM(valor), vendedor, COUNT(*) FROM vendas WHERE regiao = 'Sul' GROUP BY vendedor ORDER BY vendedor DESC"
        )
        linhas = res.splitlines()
        assert linhas[0] == "300|Carlos|1"
        assert linhas[1] == "200|Bob|1"
        assert linhas[2] == "100|Alice|1"
        assert linhas[3] == "(3 linhas)"
        assert db.cache.pin_count == 0


def test_combinada_where_sem_correspondencia_com_group_by(tmp_path):
    caminho = str(tmp_path / "banco_zero.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE vendas (id INT, vendedor CHAR(10), valor INT, regiao CHAR(10))")
        db.executa("INSERT INTO vendas VALUES (1, 'Alice', 100, 'Sul')")

        # WHERE que não bate com nada deve devolver 0 linhas quando houver GROUP BY
        res = db.executa(
            "SELECT vendedor, COUNT(*) FROM vendas WHERE regiao = 'Oeste' GROUP BY vendedor ORDER BY vendedor"
        )
        assert res == "(0 linhas)"
        assert db.cache.pin_count == 0


def test_combinada_multiplas_paginas_com_filtro_e_agrupamento(tmp_path):
    caminho = str(tmp_path / "banco_multi_comb.db")
    with Engine(caminho) as db:
        # Registro: 4 + 10 + 4 + 10 = 28 bytes. Capacidade por página = 145 linhas.
        db.executa("CREATE TABLE vendas (id INT, vendedor CHAR(10), valor INT, regiao CHAR(10))")
        # Inserindo 240 linhas (ultrapassa 1 página)
        for i in range(1, 241):
            vendedor = "Alice" if i % 2 == 0 else "Bob"
            regiao = "Sul" if i <= 120 else "Norte"
            db.executa(f"INSERT INTO vendas VALUES ({i}, '{vendedor}', 10, '{regiao}')")

        # Filtra apenas regiao = 'Sul' (linhas 1 a 120): 60 Alice (600) e 60 Bob (600)
        res = db.executa(
            "SELECT vendedor, COUNT(*), SUM(valor) FROM vendas WHERE regiao = 'Sul' GROUP BY vendedor ORDER BY vendedor ASC"
        )
        linhas = res.splitlines()
        assert linhas[0] == "Alice|60|600"
        assert linhas[1] == "Bob|60|600"
        assert linhas[2] == "(2 linhas)"
        assert db.cache.pin_count == 0


def test_erros_semanticos_em_consultas_combinadas(tmp_path):
    caminho = str(tmp_path / "banco_erros.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE vendas (id INT, vendedor CHAR(10), valor INT, regiao CHAR(10))")
        db.executa("INSERT INTO vendas VALUES (1, 'Alice', 100, 'Sul')")

        # ORDER BY em coluna que não está no GROUP BY
        with pytest.raises(ErroSemantico):
            db.executa("SELECT vendedor, COUNT(*) FROM vendas GROUP BY vendedor ORDER BY valor")
        assert db.cache.pin_count == 0

        # Coluna projetada fora do GROUP BY
        with pytest.raises(ErroSemantico):
            db.executa("SELECT vendedor, regiao, COUNT(*) FROM vendas GROUP BY vendedor")
        assert db.cache.pin_count == 0

        # WHERE em coluna inexistente
        with pytest.raises(ErroSemantico):
            db.executa("SELECT vendedor, COUNT(*) FROM vendas WHERE fantasma = 1 GROUP BY vendedor")
        assert db.cache.pin_count == 0
