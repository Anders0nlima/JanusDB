import pytest
from src.operadores import Operador
from src.sort import CodecLinha, Sort


class OperadorLista(Operador):
    """Operador simples para alimentar testes a partir de uma lista em memória."""

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


def test_codec_linha_codifica_e_decodifica():
    esquema = [("id", "INT", 4), ("nome", "CHAR", 10), ("total", "BIGINT", 8)]
    codec = CodecLinha(esquema)
    assert codec.tamanho_registro == 22

    linha = (42, "Janus", 9876543210)
    bytes_codificados = codec.codifica(linha)
    assert len(bytes_codificados) == 22

    recuperado = codec.decodifica(bytes_codificados)
    assert recuperado == (42, "Janus", 9876543210)


def test_codec_linha_validacoes():
    codec = CodecLinha([("id", "INT", 4), ("sigla", "CHAR", 3)])
    with pytest.raises(ValueError):
        codec.codifica((1,))  # Poucos valores
    with pytest.raises(ValueError):
        codec.codifica((1, "MUITOLONGO"))  # Excede CHAR(3)
    with pytest.raises(ValueError):
        codec.decodifica(b"\x00" * 3)  # Menos bytes que o tamanho_registro


def test_sort_em_memoria_asc_e_desc():
    dados = [(3, "Carlos"), (1, "Ana"), (2, "Bruno")]
    fonte = OperadorLista(dados)

    # Teste ASC por id (coluna 0)
    sort_asc = Sort(fonte, coluna_idx=0, direcao="ASC")
    with sort_asc:
        res_asc = list(sort_asc)
    assert res_asc == [(1, "Ana"), (2, "Bruno"), (3, "Carlos")]

    # Teste DESC por id (coluna 0)
    sort_desc = Sort(fonte, coluna_idx=0, direcao="DESC")
    with sort_desc:
        res_desc = list(sort_desc)
    assert res_desc == [(3, "Carlos"), (2, "Bruno"), (1, "Ana")]

    # Teste ASC por nome (coluna 1)
    sort_nome_asc = Sort(fonte, coluna_idx=1, direcao="ASC")
    with sort_nome_asc:
        assert list(sort_nome_asc) == [(1, "Ana"), (2, "Bruno"), (3, "Carlos")]

    # Teste DESC por nome (coluna 1)
    sort_nome_desc = Sort(fonte, coluna_idx=1, direcao="DESC")
    with sort_nome_desc:
        assert list(sort_nome_desc) == [(3, "Carlos"), (2, "Bruno"), (1, "Ana")]


def test_sort_estabilidade():
    # Chaves repetidas devem preservar a ordem relativa original
    dados = [(1, "Primeiro"), (2, "Outro"), (1, "Segundo"), (1, "Terceiro")]
    fonte = OperadorLista(dados)

    sort_estavel = Sort(fonte, coluna_idx=0, direcao="ASC")
    with sort_estavel:
        res = list(sort_estavel)

    assert res == [(1, "Primeiro"), (1, "Segundo"), (1, "Terceiro"), (2, "Outro")]


def test_sort_casos_borda():
    # Entrada vazia
    sort_vazio = Sort(OperadorLista([]), coluna_idx=0)
    with sort_vazio:
        assert list(sort_vazio) == []

    # Entrada de um único item
    sort_um = Sort(OperadorLista([(10, "X")]), coluna_idx=0)
    with sort_um:
        assert list(sort_um) == [(10, "X")]

    # mem_paginas menor que 3 é rejeitado
    with pytest.raises(ValueError):
        Sort(OperadorLista([]), coluna_idx=0, mem_paginas=2)

    # Direção inválida
    with pytest.raises(ValueError):
        Sort(OperadorLista([]), coluna_idx=0, direcao="INVALIDO")


def test_sort_externo_dados_aleatorios_m_minimo(tmp_path):
    import random
    # Cada linha: INT (4) + CHAR(100) = 104 bytes.
    # Linhas por página = 4080 // 104 = 39. Capacidade do run (M=3) = 3 * 39 = 117 linhas.
    esquema = [("id", "INT", 4), ("nome", "CHAR", 100)]
    random.seed(42)
    dados = [(random.randint(1, 1000), f"Nome_{i}") for i in range(250)]

    caminho_tmp = str(tmp_path / "sort_ext.tmp")
    sort_op = Sort(
        OperadorLista(dados),
        coluna_idx=0,
        direcao="ASC",
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )

    with sort_op:
        resultado = list(sort_op)

    esperado = sorted(dados, key=lambda x: x[0])
    assert resultado == esperado
    # Garante que o arquivo temporário foi removido
    import os
    assert not os.path.exists(caminho_tmp)

    # Teste DESC com estabilidade
    sort_desc = Sort(
        OperadorLista(dados),
        coluna_idx=0,
        direcao="DESC",
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )
    with sort_desc:
        res_desc = list(sort_desc)

    esperado_desc = sorted(dados, key=lambda x: x[0], reverse=True)
    assert res_desc == esperado_desc


def test_sort_cabe_em_memoria_nao_cria_arquivo_temporario(tmp_path):
    import os
    esquema = [("id", "INT", 4), ("nome", "CHAR", 100)]
    # Capacidade do run (M=3) = 117 linhas
    dados_pequenos = [(i, f"Aluno_{i}") for i in range(50)]
    caminho_tmp = str(tmp_path / "temp_nao_deve_existir.tmp")

    sort_op = Sort(
        OperadorLista(dados_pequenos),
        coluna_idx=0,
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )
    with sort_op:
        res = list(sort_op)
    assert len(res) == 50
    assert not os.path.exists(caminho_tmp)

    # Borda: exatamente a capacidade de um run (117 linhas)
    dados_borda = [(i, f"Aluno_{i}") for i in range(117)]
    sort_borda = Sort(
        OperadorLista(dados_borda),
        coluna_idx=0,
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )
    with sort_borda:
        res_borda = list(sort_borda)
    assert len(res_borda) == 117
    assert not os.path.exists(caminho_tmp)


def test_sort_externo_multiplas_passadas_e_contador_io(tmp_path):
    # CHAR(1000): 4 linhas por página. M=3 -> run de 12 linhas.
    # 40 linhas geram 4 runs. Fan-in = 2.
    # Passada 1 reduz de 4 para 3 runs.
    # Passada 2 reduz de 3 para 2 runs.
    # Passada final intercala os 2 runs entregando na saída sem gravar.
    esquema = [("id", "INT", 4), ("payload", "CHAR", 1000)]
    dados = [(40 - i, f"Dado_{i}") for i in range(40)]

    caminho_tmp = str(tmp_path / "multi_pass.tmp")
    sort_op = Sort(
        OperadorLista(dados),
        coluna_idx=0,
        direcao="ASC",
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )

    with sort_op:
        assert sort_op.temp_pager is not None
        # Verifica que houve escritas durante a geração de runs e passadas intermediárias
        assert sort_op.temp_pager.escritas > 0
        res = list(sort_op)

    assert res == sorted(dados, key=lambda x: x[0])


def test_sort_arquivo_temporario_removido_mesmo_com_erro(tmp_path):
    import os
    esquema = [("id", "INT", 4), ("nome", "CHAR", 100)]
    dados = [(i, f"X_{i}") for i in range(200)]
    caminho_tmp = str(tmp_path / "erro.tmp")

    sort_op = Sort(
        OperadorLista(dados),
        coluna_idx=0,
        mem_paginas=3,
        esquema=esquema,
        caminho_temp=caminho_tmp,
    )

    try:
        with sort_op:
            sort_op.proximo()
            raise RuntimeError("Falha intencional no meio da consulta")
    except RuntimeError:
        pass

    assert not os.path.exists(caminho_tmp)

