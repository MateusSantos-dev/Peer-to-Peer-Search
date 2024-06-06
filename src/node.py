import sys
import utils
import socket
import threading
from typing import Optional
from enum import Enum, auto


class MessageType(Enum):
    """Categorias de mensagens que podem ser enviadas."""

    HELLO = auto()
    SEARCH_FLOODING = auto()
    SEARCH_RANDOM_WALK = auto()
    SEARCH_DEPTH_FIRST = auto()
    VALUE = auto()
    BYE = auto()


class MenuOptions(Enum):
    """Opções do menu de comandos disponíveis para o usuário."""

    LISTAR_VIZINHOS = 0
    HELLO = 1
    SEARCH_FLOODING = 2
    SEARCH_RANDOM_WALK = 3
    SEARCH_DEPTH_FIRST = 4
    ESTATISTICAS = 5
    ALTERAR_TTL = 6
    SAIR = 9


class Node:
    """Representa um nó da rede P2P."""

    def __init__(
            self,
            ip: str,
            port: int,
            neighbors: Optional[list[tuple[str, int]]],
            key_values: Optional[dict[str, str]]
    ) -> None:
        """Inicializa um novo nó da rede P2P."""

        # Se os parametros não forem passados, inicializa com valores padrão
        if neighbors is None:
            neighbors = []
        if key_values is None:
            key_values = {}

        self.ip = ip
        self.port = port
        self.sequence_number = 1  # numero de sequência da mensagem
        self.socket = Node.create_socket(ip, port)

        print(f"Servidor criado: {ip}:{port}\n")

        self.data = key_values

        for key, value in self.data.items():
            print(f"Adicionando ({key}, {value}) na tabela local")
        print()

        self.default_ttl = 100
        self.neighbors: dict[tuple[str, int], socket.socket] = self.connect_to_neighbors(neighbors)
        self.last_seen_messages: dict[str, int] = {}  # Salva o último número de sequência recebido de cada vizinho

    @staticmethod
    def create_socket(ip: str, port: int) -> socket.socket:
        """Cria um socket TCP IPv4 para o nó."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((ip, port))
        return sock

    def show_node(self) -> None:
        """Mostra as informações do nó."""
        print(f"IP: {self.ip}")
        print(f"Porta: {self.port}")
        self.show_neighbors()
        print("Chave_valor:")
        for key, value in self.data.items():
            print(f"    {key}: {value}")

    def show_neighbors(self) -> None:
        """Mostra os vizinhos do nó."""
        print(f"Há {len(self.neighbors)} vizinhos na tabela")
        for idx, (ip, port) in enumerate(self.neighbors.keys()):
            print(f"    [{idx}] {ip}:{port}")

    def receive_connections(self) -> None:
        """Recebe conexões de outros nós e inicia uma thread para lidar com a conexão."""
        self.socket.listen()
        while True:
            connection, _ = self.socket.accept()
            threading.Thread(target=self.receive_message, args=(connection,), daemon=True).start()

    def mark_message_as_seen(self, message: str) -> None:
        """Marca uma mensagem como vista."""
        # Não marca mensagens de confirmação ou mensagens já vistas
        if Node.is_message_confirmation(message) or message in self.last_seen_messages:
            return

        # Não marca mensagens enviadas pelo próprio nó
        if message.split(" ")[0] == f"{self.ip}:{self.port}":
            return

        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        self.last_seen_messages[origin] = int(sequence_number)

    @staticmethod
    def confirm_message(connection: socket.socket, message: str) -> None:
        """Confirma o recebimento de uma mensagem."""
        # Não confirma mensagens de confirmação
        if Node.is_message_confirmation(message):
            return

        operacao = message.split(" ")[3]
        connection.sendall(f"{operacao}_OK".encode())

    @staticmethod
    def is_message_confirmation(message: str) -> bool:
        """Verifica se uma mensagem é uma confirmação de recebimento."""
        return message[-3:] == "_OK"

    def receive_message(self, connection: socket.socket):
        """Recebe mensagens de um nó conectado."""
        try:
            while True:
                data = connection.recv(1024)
                if not data:
                    break
                message = data.decode()
                self.interpret_message(message, sender_ip=connection.getpeername()[0])
                if Node.is_message_confirmation(message) is False:
                    self.confirm_message(connection, message)
                    self.mark_message_as_seen(message)
        except ConnectionResetError:
            print("Connection reset")
        except ConnectionAbortedError:
            print("Connection aborted")
        finally:
            connection.close()
            print("Connection closed")

    def interpret_message(self, message: str, sender_ip: str) -> None:
        """Interpreta uma mensagem recebida."""
        if Node.is_message_confirmation(message):
            print(f'    Mensagem de confirmação recebida: "{message}"')
            return

        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        ttl = parts[2]
        operacao = parts[3]

        print(f'Mensagem recebida: "{message}"')

        if operacao == "HELLO":
            self.handle_message_hello(message)

        elif operacao == "BYE":
            self.handle_message_bye(message)

        elif operacao == "SEARCH":
            mode = parts[4]

            if mode == "FL":
                self.handle_message_flooding(message, sender_ip)

        elif operacao == "VAL":
            self.handle_value(message)

        else:
            raise ValueError(f"Operação inválida: {operacao}")

    def handle_message_hello(self, message: str) -> None:
        """Lida com uma mensagem HELLO."""
        origin = message.split(" ")[0]
        ip, port = utils.convert_str_to_ip_port(origin)
        self.add_neighbor(ip, port)

    def handle_message_bye(self, message: str) -> None:
        """Lida com uma mensagem BYE."""
        origin = message.split(" ")[0]
        ip, port = utils.convert_str_to_ip_port(origin)
        self.delete_neighbor(ip, port)

    def handle_message_flooding(self, message: str, sender_ip: str) -> None:
        """Lida com uma mensagem de busca por flooding."""

        parts = message.split(" ")
        origin = parts[0]
        ttl = parts[2]
        last_hop_port = parts[5]
        key = parts[6]
        hop_count = parts[7]

        # Verifica se a mensagem já foi vista ou se eu mesmo enviei
        if message in self.last_seen_messages or origin == f"{self.ip}:{self.port}":
            print("Flooding: Mensagem repetida")
            return

        if key in self.data:
            print("Chave encontrada")
            ip, port = utils.convert_str_to_ip_port(origin)
            if (ip, port) in self.neighbors:
                self.send_value(
                    self.neighbors[(ip, port)],
                    mode="FL",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count)

            else:
                # Cria conexão temporária para enviar o valor
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_value(
                    sock,
                    mode="FL",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count)
                sock.close()
            return

        ttl = int(ttl) - 1
        if ttl <= 0:
            print("TTL igual a zero, descartando mensagem")
            return

        hop_count = int(hop_count) + 1
        message = self.craft_message(MessageType.SEARCH_FLOODING,
                                     origin=origin,
                                     sequence_number=self.sequence_number,
                                     ttl=ttl,
                                     last_hop_port=self.port,
                                     key=key,
                                     hop_count=hop_count)

        # enviar para vizinhos exceto o transmissor da mensagem
        for (ip, port), neighbor in self.neighbors.items():
            if (ip, port) != (sender_ip, int(last_hop_port)):
                self.send_message(neighbor, message)

    def handle_value(self, message: str) -> None:
        """Lida com uma mensagem VALUE."""
        parts = message.split(" ")
        key = parts[5]
        value = parts[6]

        if key in self.data:
            print("Chave já existe na tabela")
            return

        print(f"Valor encontrado! Chave: {key} Valor: {value}")

    def send_message(self, sock: socket.socket, message: str) -> None:
        """Envia uma mensagem para um nó e."""
        ip, port = sock.getpeername()
        print(f'Encaminhando mensagem: "{message}" para {ip}:{port}')
        sock.sendall(message.encode())
        self.sequence_number += 1

    def send_hello(self, peer: socket.socket) -> None:
        """Envia uma mensagem HELLO para um vizinho."""
        message = self.craft_message(MessageType.HELLO)
        self.send_message(peer, message)

    def send_bye(self, peer: socket.socket) -> None:
        """Envia uma mensagem BYE para um vizinho."""
        message = self.craft_message(MessageType.BYE)
        self.send_message(peer, message)

    def start_search_flooding(self, key: str) -> None:
        """Inicia uma busca por flooding."""
        message = self.craft_message(
            MessageType.SEARCH_FLOODING,
            last_hop_port=self.port,
            key=key, hop_count=1)

        for neighbor in self.neighbors.values():
            self.send_message(neighbor, message)

    def send_value(self, peer: socket.socket, **kwargs) -> None:
        """Envia um valor para um nó."""
        mode = kwargs.get("mode")
        key = kwargs.get("key")
        value = kwargs.get("value")
        hop_count = kwargs.get("hop_count")

        message = self.craft_message(MessageType.VALUE, mode=mode, key=key, value=value, hop_count=hop_count)
        self.send_message(peer, message)

    def craft_message(self, message_type: MessageType, **kwargs):
        """Cria uma mensagem para ser enviada."""
        # Caso esteja reenviando mensagem, pega o endereço de origem e o número de sequência da mensagem
        origin = kwargs.get("origin", f"{self.ip}:{self.port}")
        sequence_number = kwargs.get("sequence_number", self.sequence_number)
        operacao = MessageType(message_type).name  # Converte o valor do Enum para o nome da operação

        ttl = kwargs.get("ttl", self.default_ttl)

        if message_type == MessageType.HELLO:
            ttl = 1
            return f"{origin} {sequence_number} {ttl} {operacao}"

        if message_type == MessageType.BYE:
            ttl = 1
            return f"{origin} {sequence_number} {ttl} {operacao}"

        if message_type == MessageType.SEARCH_FLOODING:
            operacao = "SEARCH"
            mode = "FL"
            last_hop_port = kwargs.get("last_hop_port")
            key = kwargs.get("key")
            hop_count = kwargs.get("hop_count")
            return f"{origin} {sequence_number} {ttl} {operacao} {mode} {last_hop_port} {key} {hop_count}"

        if message_type == MessageType.VALUE:
            operacao = "VAL"
            mode = kwargs.get("mode")
            key = kwargs.get("key")
            value = kwargs.get("value")
            hop_count = kwargs.get("hop_count")
            return f"{origin} {sequence_number} {ttl} {operacao} {mode} {key} {value} {hop_count}"

        else:
            raise ValueError(f"Operação inválida: {message_type}")

    def connect_to_neighbors(self, neighbors: list[tuple[str, int]]):
        """Conecta-se aos vizinhos do nó."""
        all_neighbors = {}
        for neighbor in neighbors:
            ip, port = neighbor
            print(f"Tentando adicionar vizinho {ip}:{port}")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_hello(sock)
                all_neighbors[neighbor] = sock
                threading.Thread(target=self.receive_message, args=(sock,), daemon=True).start()
            except ConnectionRefusedError:
                print("    Erro ao conectar!")
        return all_neighbors

    def add_neighbor(self, ip: str, port: int) -> None:
        """Adiciona um vizinho ao nó."""
        if (ip, port) in self.neighbors:
            print(f"Vizinho já está na tabela {ip}:{port}")
            return

        print(f"Tentando conectar com {ip}:{port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            self.neighbors[(ip, port)] = sock
            print(f"    Adicionando vizinho na tabela: {ip}:{port}")
            threading.Thread(target=self.receive_message, args=(sock,), daemon=True).start()
        except ConnectionRefusedError:
            print("    Erro ao conectar!")

    def delete_neighbor(self, ip: str, port: int) -> None:
        """Deleta um vizinho do nó."""
        if (ip, port) not in self.neighbors:
            print(f"Vizinho não está na tabela {ip}:{port}")
            return

        # Fecha a conexão com o vizinho
        self.neighbors[(ip, port)].close()
        del self.neighbors[(ip, port)]
        print(f"Removendo vizinho da tabela {ip}:{port}")

        # Remove o vizinho da lista de mensagens vistas
        if f"{ip}:{port}" in self.last_seen_messages:
            del self.last_seen_messages[f"{ip}:{port}"]

    def pick_neighbor(self):
        """Retorna o vizinho escolhido pelo usuário"""
        self.show_neighbors()

        if len(self.neighbors) == 0:
            return None

        neighbor_idx = int(input("\n"))
        if neighbor_idx < 0 or neighbor_idx >= len(self.neighbors):
            return None
        neighbor_chosen_key = list(self.neighbors.keys())[neighbor_idx]
        return self.neighbors[neighbor_chosen_key]

    def get_menu_option(self) -> None:
        """Pega opcao do menu escolhida pelo usuario."""
        menu_options = [menu_option.value for menu_option in MenuOptions]
        option = input("")

        if not option.isdigit() or int(option) not in menu_options:
            print("Opção inválida")
            return

        option = int(option)

        if option == MenuOptions.LISTAR_VIZINHOS.value:
            self.show_neighbors()

        elif option == MenuOptions.HELLO.value:
            peer = self.pick_neighbor()
            if not peer:
                print("Vizinho inválido")
                return
            self.send_hello(peer)

        elif option == MenuOptions.SEARCH_FLOODING.value:
            key = input("Digite a chave a ser buscada\n")
            if not Node.is_valid_key(key):
                print("Chave inválida")
                return

            if key in self.data:
                print("Valor na tabela local")
                print(f"    chave: {key} valor: {self.data[key]}")
            else:
                self.start_search_flooding(key)

        elif option == MenuOptions.ALTERAR_TTL.value:
            novo_ttl = input("Digite novo valor de TTL\n")
            if not novo_ttl.isdigit() or int(novo_ttl) <= 0:
                print("Valor de TTL inválido")
                return

            self.default_ttl = novo_ttl

        elif option == MenuOptions.SAIR.value:
            for peer in self.neighbors.values():
                self.send_bye(peer)

    @staticmethod
    def is_valid_key(key: str) -> bool:
        """Verifica se uma chave dada pelo usuário é válida"""
        return " " not in key

    @staticmethod
    def show_menu() -> None:
        """Mostra o menu de comandos disponiveis para o usuario."""
        print("""\nEscolha o comando
    [0] Listar vizinhos
    [1] HELLO
    [2] SEARCH (flooding)
    [3] SEARCH (random walk)
    [4] SEARCH (busca em profundidade)
    [5] Estatisticas
    [6] Alterar valor padrao de TTL
    [9] Sair"""
              )


def create_node() -> Node:
    """Cria um nó da rede P2P usando os argumentos passados na inicialização do programa."""
    # Se não houver argumentos suficientes, exibe uma mensagem de erro e encerra o programa
    if len(sys.argv) < 2:  # sys.argv[0] é o nome do arquivo
        raise SystemExit("Esperado no mínimo 1 argumento, recebido 0")

    neighbors = None
    data = None

    ip, port = utils.convert_str_to_ip_port(sys.argv[1])

    if not utils.is_valid_ip(ip) or not utils.is_valid_port(port):
        raise ValueError(f"IP ou porta inválidos {ip}:{port}")

    if len(sys.argv) >= 3:
        neighbors = utils.get_all_neighbors_from_file(sys.argv[2])

    if len(sys.argv) >= 4:
        data = utils.get_key_value_from_file(sys.argv[3])

    return Node(ip, port, neighbors, data)


if __name__ == '__main__':
    node = create_node()
    thread = threading.Thread(target=node.receive_connections, args=(), daemon=True)
    thread.start()
    node.show_menu()
    while True:
        node.get_menu_option()
