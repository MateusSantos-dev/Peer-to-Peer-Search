# Peer-to-Peer Search

Este é um projeto que implementa três algoritmos de busca (flooding, random walk e busca por profundidade) em um sistema P2P não estruturado.

## Requisitos

Para rodar o projeto, é necessário possuir uma versão do Python 3.10 ou mais recente.

## Autores

Este projeto foi desenvolvido por Mateus Santos e Wellisson Santana, estudantes de Sistemas de Informação da USP.

## Como Executar

Para executar o código, siga as instruções abaixo:
```bash
python src/node.py <endereco>:<porta> [vizinhos.txt [lista_chave_valor.txt]]
```


- `endereco:porta`: Endereço IP e porta para iniciar o nó.
- `vizinhos.txt` (opcional): Arquivo contendo strings no formato `ip:porta` que representam os vizinhos do nó criado.
- `lista_chave_valor.txt` (opcional): Arquivo contendo os pares chave-valor que o nó criado possuirá em sua tabela local.

## Nota

Nenhuma dependência externa é necessária para executar este projeto.

