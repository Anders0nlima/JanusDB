import os

from src.storage import (
    escreve_pagina,
    le_pagina,
    PAGE_SIZE,
    HEADER_SIZE,
    RECORD_SIZE,
)


ARQUIVO_TESTE = "data/teste_registro.db"


def setup_module():
    os.makedirs("data", exist_ok=True)

    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)


def test_escreve_e_le_registro_da_pagina_2():
    pagina = 2
    slot = 0
    registro = b"ABCDEFGH"

    # cria uma pagina vazia
    dados = bytearray(PAGE_SIZE)

    # calcula onde o registro deve ficar dentro da página
    offset = HEADER_SIZE + (slot * RECORD_SIZE)

    # coloca o registro no slot 0
    dados[offset:offset + RECORD_SIZE] = registro

    # escreve a pagina 2 no arquivo
    escreve_pagina(ARQUIVO_TESTE, pagina, bytes(dados))

    # simula o encerramento e reabertura do processo:
    # a função escreve_pagina já fechou o arquivo.
    pagina_lida = le_pagina(ARQUIVO_TESTE, pagina)

    # le o registro que esta no slot 0
    registro_lido = pagina_lida[
        offset:offset + RECORD_SIZE
    ]

    assert registro_lido == registro


def test_registro_esta_no_byte_8208():
    pagina = 2
    slot = 0

    offset_pagina = pagina * PAGE_SIZE
    offset_registro = (
        offset_pagina
        + HEADER_SIZE
        + (slot * RECORD_SIZE)
    )

    assert offset_registro == 8208