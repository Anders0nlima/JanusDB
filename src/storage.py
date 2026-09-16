PAGE_SIZE = 4096 
HEADER_SIZE = 16 
RECORD_SIZE = 8

def escreve_pagina(caminho_arquivo: str, n: int, dados: bytes) -> None:
    """grava dados (exatamente PAGE_SIZE bytes) na posição da pagina n"""

    if len(dados) != PAGE_SIZE:
        raise ValueError("A pagina deve ter exatamente PAGE_SIZE bytes.")
    
    try:
        arquivo = open(caminho_arquivo, "r+b")
    except FileNotFoundError:
        arquivo = open(caminho_arquivo, "w+b")

    with arquivo:
        offset = n * PAGE_SIZE
        arquivo.seek(offset)
        arquivo.write(dados)

def le_pagina(caminho_arquivo: str, n: int) -> bytes:
    """Devolve os PAGE_SIZE bytes da página n."""

    offset = n * PAGE_SIZE

    with open(caminho_arquivo, "rb") as arquivo:
        arquivo.seek(offset)
        dados = arquivo.read(PAGE_SIZE)
        if len(dados) != PAGE_SIZE:
            raise IOError(f"Página {n} truncada: esperava {PAGE_SIZE} bytes, veio {len(dados)}")
        return dados

def calcula_deslocamento(pagina: int, slot: int) -> int:
    """Calcula em qual byte absoluto do arquivo começa um registro."""
    return (pagina * PAGE_SIZE) + HEADER_SIZE + (slot * RECORD_SIZE)

