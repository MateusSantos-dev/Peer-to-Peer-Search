import sys
import utils
import socket
import threading
import random
from typing import Optional, Any
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

        # Dicionário de chave-valor
        self.data = key_values

        for key, value in self.data.items():
            print(f"Adicionando ({key}, {value}) na tabela local")
        print()

        self.default_ttl = 100
        self.neighbors: dict[tuple[str, int], socket.socket] = self.connect_to_neighbors(neighbors)

        self.last_seen_messages: dict[str, int] = {}  # Salva o último número de sequência recebido de cada vizinho

        # Salva valores para busca em profundidade
        self.info_busca_em_profundidade: dict[str, Any] = {
            "no_mae": None,  # ip porta
            "vizinho_ativo": None,  # socket
            "vizinhos_candidatos": []
        }
        # Armazena número de mensagens vistas e hop_count até encontrar chave
        self.num_messages_seen_flooding = 0
        self.num_messages_seen_random_walk = 0
        self.num_messages_seen_depth_first = 0
        self.hop_count_flooding: list[int] = []
        self.hop_count_random_walk: list[int] = []
        self.hop_count_depth_first: list[int] = []

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

    def show_statistics(self) -> None:
        """Imprime média e desvio padrão do hop_count de todas mensagens de busca vistas pelo nó"""
        print(f"Total de mensagens de flooding vistas: {self.num_messages_seen_flooding}")
        print(f"Total de mensagens de random walk vistas: {self.num_messages_seen_random_walk}")
        print(f"Total de mensagens de busca em profundidade vistas: {self.num_messages_seen_depth_first}")
        print(
            f"Media de saltos ate encontrar destino por flooding: "
            f"{utils.calculate_mean(self.hop_count_flooding)}"
            f" (dp {utils.calculate_standard_deviation(self.hop_count_flooding)})")
        print(
            f"Media de saltos ate encontrar destino por random walk: "
            f"{utils.calculate_mean(self.hop_count_random_walk)} "
            f"(dp {utils.calculate_standard_deviation(self.hop_count_random_walk)})")
        print(
            f"Media de saltos ate encontrar destino por busca em profundidade:"
            f" {utils.calculate_mean(self.hop_count_depth_first)} "
            f"(dp {utils.calculate_standard_deviation(self.hop_count_depth_first)})")

    def receive_connections(self) -> None:
        """Recebe conexões de outros nós e inicia uma thread para lidar com a conexão."""
        self.socket.listen()
        while True:
            connection, _ = self.socket.accept()
            threading.Thread(target=self.receive_message, args=(connection,), daemon=True).start()

    def connect_to_neighbors(self, neighbors: list[tuple[str, int]]) -> dict[tuple[str, int], socket.socket]:
        """Conecta-se aos vizinhos do nó."""
        all_neighbors = {}
        for neighbor in neighbors:
            ip, port = neighbor
            print(f"Tentando adicionar vizinho {ip}:{port}")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                sock.settimeout(0.5)  # Se socket não conectar em 0.5, provavelmente não esta online
                sock.connect((ip, port))
                sock.settimeout(None)  # Reseta o timeout para não interferir com o resto
                self.send_hello(sock)
                all_neighbors[neighbor] = sock

                threading.Thread(target=self.receive_message, args=(sock,), daemon=True).start()
            except (ConnectionRefusedError, TimeoutError):
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

    def mark_message_as_seen(self, message: str) -> None:
        """Marca uma mensagem como vista."""
        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        # Não marca mensagens de confirmação ou mensagens já vistas
        if Node.is_confirmation_message(message) or self.message_already_seen(message):
            return

        # Não marca mensagens enviadas pelo próprio nó
        if origin == f"{self.ip}:{self.port}":
            return

        self.last_seen_messages[origin] = int(sequence_number)

    def message_already_seen(self, message: str) -> bool:
        """Verifica se uma mensagem já foi vista."""
        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        return origin in self.last_seen_messages and int(sequence_number) <= self.last_seen_messages[origin]

    @staticmethod
    def confirm_message(connection: socket.socket, message: str) -> None:
        """Confirma o recebimento de uma mensagem."""
        # Não confirma mensagens de confirmação
        if Node.is_confirmation_message(message):
            return

        operacao = message.split(" ")[3]
        connection.sendall(f"{operacao}_OK".encode())

    @staticmethod
    def is_confirmation_message(message: str) -> bool:
        """Verifica se uma mensagem é uma confirmação de recebimento."""
        return message[-3:] == "_OK"

    def receive_message(self, connection: socket.socket) -> None:
        """Recebe mensagens de um nó conectado."""
        try:
            while True:
                data = connection.recv(1024)
                if not data:
                    break
                message = data.decode()
                self.interpret_message(message, sender_ip=connection.getpeername()[0])
                if not Node.is_confirmation_message(message):
                    self.confirm_message(connection, message)
                    self.mark_message_as_seen(message)
        except ConnectionResetError:
            pass  # Isso vai ocorrer quando um dos peers forem fechados, seja voluntariamente ou não
        except ConnectionAbortedError:
            pass
        finally:
            connection.close()

    def interpret_message(self, message: str, sender_ip: str) -> None:
        """Interpreta uma mensagem recebida."""
        if Node.is_confirmation_message(message):
            print(f'    Mensagem de confirmação recebida: "{message}"')
            return

        parts = message.split(" ")
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

            elif mode == "RW":
                self.handle_message_random_walk(message, sender_ip)

            elif mode == "BP":
                self.handle_message_depth_first(message, sender_ip)

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
        sequence_number = parts[1]
        ttl = parts[2]
        last_hop_port = parts[5]
        key = parts[6]
        hop_count = parts[7]

        self.num_messages_seen_flooding += 1

        # Verifica se a mensagem já foi vista ou se eu mesmo enviei
        if self.message_already_seen(message) or origin == f"{self.ip}:{self.port}":
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
                    hop_count=hop_count
                )

            else:
                # Cria conexão temporária para enviar o valor
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_value(
                    sock,
                    mode="FL",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count
                )
                sock.close()
            return

        ttl = int(ttl) - 1
        if ttl <= 0:
            print("TTL igual a zero, descartando mensagem")
            return

        hop_count = int(hop_count) + 1
        message = self.craft_message(
            MessageType.SEARCH_FLOODING,
            origin=origin,
            sequence_number=sequence_number,
            ttl=ttl,
            key=key,
            hop_count=hop_count
        )

        # enviar para vizinhos exceto o transmissor da mensagem
        for (ip, port), neighbor in self.neighbors.items():
            if (ip, port) != (sender_ip, int(last_hop_port)):
                Node.send_message(neighbor, message)

    def handle_message_random_walk(self, message: str, sender_ip: str) -> None:
        """Lida com uma mensagem de busca por random walk."""
        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        ttl = parts[2]
        last_hop_port = parts[5]
        key = parts[6]
        hop_count = parts[7]

        self.num_messages_seen_random_walk += 1

        if key in self.data:
            print("Chave encontrada")
            ip, port = utils.convert_str_to_ip_port(origin)
            if (ip, port) in self.neighbors:
                self.send_value(
                    self.neighbors[(ip, port)],
                    mode="RW",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count
                )

            else:
                # Cria conexão temporária para enviar o valor
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_value(
                    sock,
                    mode="RW",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count
                )
                sock.close()
            return

        ttl = int(ttl) - 1
        if ttl <= 0:
            print("TTL igual a zero, descartando mensagem")
            return

        hop_count = int(hop_count) + 1
        message = self.craft_message(
            MessageType.SEARCH_RANDOM_WALK,
            origin=origin,
            sequence_number=sequence_number,
            ttl=ttl,
            key=key,
            hop_count=hop_count
        )

        all_neighbors = list(self.neighbors.values())
        # Mensagem só volta pelo mesmo caminho se não houver outros vizinhos
        if len(all_neighbors) > 1:
            all_neighbors.remove(self.neighbors[(sender_ip, int(last_hop_port))])
        Node.send_message(random.choice(all_neighbors), message)

    def handle_message_depth_first(self, message: str, sender_ip: str) -> None:
        """Lida com uma mensagem de busca em profundidade."""
        parts = message.split(" ")
        origin = parts[0]
        sequence_number = parts[1]
        ttl = parts[2]
        last_hop_port = parts[5]
        key = parts[6]
        hop_count = parts[7]

        self.num_messages_seen_depth_first += 1

        no_anterior = f"{sender_ip}:{last_hop_port}"
        socket_no_anterior = self.neighbors[(sender_ip, int(last_hop_port))]

        if key in self.data:
            print("Chave encontrada")
            ip, port = utils.convert_str_to_ip_port(origin)
            if (ip, port) in self.neighbors:
                self.send_value(
                    self.neighbors[(ip, port)],
                    mode="BP",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count
                )

            else:
                # Cria conexão temporária para enviar o valor
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_value(
                    sock,
                    mode="BP",
                    key=key,
                    value=self.data[key],
                    hop_count=hop_count
                )
                sock.close()
            return

        ttl = int(ttl) - 1
        if ttl <= 0:
            print("TTL igual a zero, descartando mensagem")
            return

        if not self.message_already_seen(message):
            self.info_busca_em_profundidade["no_mae"] = no_anterior
            self.info_busca_em_profundidade["vizinhos_candidatos"] = list(self.neighbors.values())

        self.info_busca_em_profundidade["vizinhos_candidatos"].remove(socket_no_anterior)

        # Condicão de parada
        if self.info_busca_em_profundidade["no_mae"] == f"{self.ip}:{self.port}" and \
                self.info_busca_em_profundidade["vizinho_ativo"] == socket_no_anterior and \
                len(self.info_busca_em_profundidade["vizinhos_candidatos"]) == 0:
            print(f"BP: Não foi possível localizar a chave {key}")
            return

        if self.info_busca_em_profundidade["vizinho_ativo"] is not None and \
                self.info_busca_em_profundidade["vizinho_ativo"] != socket_no_anterior:
            print("BP: ciclo detectado, devolvendo a mensagem...")
            proximo_socket = socket_no_anterior
        elif len(self.info_busca_em_profundidade["vizinhos_candidatos"]) == 0:
            print("BP: nenhum vizinho encontrou a chave, retrocedendo...")
            ip_mae, port_mae = utils.convert_str_to_ip_port(self.info_busca_em_profundidade["no_mae"])
            socket_no_mae = self.neighbors[(ip_mae, port_mae)]
            proximo_socket = socket_no_mae
        else:
            proximo_socket = random.choice(self.info_busca_em_profundidade["vizinhos_candidatos"])
            self.info_busca_em_profundidade["vizinho_ativo"] = proximo_socket
            self.info_busca_em_profundidade["vizinhos_candidatos"].remove(proximo_socket)

        hop_count = int(hop_count) + 1
        message = self.craft_message(
            MessageType.SEARCH_DEPTH_FIRST,
            origin=origin,
            sequence_number=sequence_number,
            ttl=ttl,
            key=key,
            hop_count=hop_count
        )
        Node.send_message(proximo_socket, message)

    def handle_value(self, message: str) -> None:
        """Lida com uma mensagem VALUE."""
        parts = message.split(" ")
        mode = parts[4]
        key = parts[5]
        value = parts[6]
        hop_count = parts[7]

        if key in self.data:
            print("Chave já existe na tabela")
            return

        print(f"Valor encontrado! Chave: {key} Valor: {value}")

        if mode == "FL":
            self.hop_count_flooding.append(int(hop_count))
        if mode == "RW":
            self.hop_count_random_walk.append(int(hop_count))
        if mode == "BP":
            self.hop_count_depth_first.append(int(hop_count))

    @staticmethod
    def send_message(sock: socket.socket, message: str) -> None:
        """Envia uma mensagem para um nó e."""
        ip, port = sock.getpeername()
        print(f'Encaminhando mensagem: "{message}" para {ip}:{port}')
        sock.sendall(message.encode())

    def send_hello(self, peer: socket.socket) -> None:
        """Envia uma mensagem HELLO para um vizinho."""
        message = self.craft_message(MessageType.HELLO)
        Node.send_message(peer, message)
        self.sequence_number += 1

    def send_bye(self, peer: socket.socket) -> None:
        """Envia uma mensagem BYE para um vizinho."""
        message = self.craft_message(MessageType.BYE)
        Node.send_message(peer, message)
        self.sequence_number += 1

    def send_value(self, peer: socket.socket, **kwargs) -> None:
        """Envia um valor para um nó."""
        mode = kwargs.get("mode")
        key = kwargs.get("key")
        value = kwargs.get("value")
        hop_count = kwargs.get("hop_count")

        message = self.craft_message(
            MessageType.VALUE,
            mode=mode,
            key=key,
            value=value,
            hop_count=hop_count)
        Node.send_message(peer, message)
        self.sequence_number += 1

    def start_search_flooding(self, key: str) -> None:
        """Inicia uma busca por flooding."""
        message = self.craft_message(
            MessageType.SEARCH_FLOODING,
            key=key,
            hop_count=1)

        for neighbor in self.neighbors.values():
            Node.send_message(neighbor, message)
        self.sequence_number += 1

    def start_search_random_walk(self, key: str) -> None:
        """Inicia uma busca por random walk."""
        message = self.craft_message(
            MessageType.SEARCH_RANDOM_WALK,
            key=key,
            hop_count=1)
        neighbor = random.choice(list(self.neighbors.values()))
        Node.send_message(neighbor, message)
        self.sequence_number += 1

    def start_search_depth_first(self, key: str) -> None:
        """Inicia uma busca em profundidade."""
        self.info_busca_em_profundidade["no_mae"] = f"{self.ip}:{self.port}"
        self.info_busca_em_profundidade["vizinhos_candidatos"] = list(self.neighbors.values())
        self.info_busca_em_profundidade["vizinho_ativo"] = \
            random.choice(self.info_busca_em_profundidade["vizinhos_candidatos"])

        self.info_busca_em_profundidade["vizinhos_candidatos"].remove(
            self.info_busca_em_profundidade["vizinho_ativo"])

        message = self.craft_message(
            MessageType.SEARCH_DEPTH_FIRST,
            last_hop_port=self.port,
            key=key,
            hop_count=1)

        Node.send_message(self.info_busca_em_profundidade["vizinho_ativo"], message)
        self.sequence_number += 1

    def craft_message(self, message_type: MessageType, **kwargs) -> str:
        """Cria uma mensagem para ser enviada."""
        origin = kwargs.get("origin", f"{self.ip}:{self.port}")
        sequence_number = kwargs.get("sequence_number", self.sequence_number)
        key = kwargs.get("key")
        hop_count = kwargs.get("hop_count")
        ttl = kwargs.get("ttl", self.default_ttl)

        if message_type == MessageType.HELLO:
            return self.craft_message_hello()

        if message_type == MessageType.BYE:
            return self.craft_message_bye()

        if message_type == MessageType.SEARCH_FLOODING:
            return self.craft_message_search_flooding(
                origin=origin,
                sequence_number=sequence_number,
                ttl=ttl,
                key=key,
                hop_count=hop_count
            )

        if message_type == MessageType.SEARCH_RANDOM_WALK:
            return self.craft_message_search_random_walk(
                origin=origin,
                sequence_number=sequence_number,
                ttl=ttl,
                key=key,
                hop_count=hop_count
            )

        if message_type == MessageType.SEARCH_DEPTH_FIRST:
            return self.craft_message_search_depth_first(
                origin=origin,
                sequence_number=sequence_number,
                ttl=ttl,
                key=key,
                hop_count=hop_count
            )

        if message_type == MessageType.VALUE:
            return self.craft_message_value(
                mode=kwargs.get("mode"),
                key=key,
                value=kwargs.get("value"),
                hop_count=hop_count
            )

        # Só entra aqui se esquecer de implementar alguma opção
        raise ValueError(f"Operação inválida: {message_type}")

    def craft_message_hello(self) -> str:
        """
        Cria uma mensagem HELLO.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> <OPERACAO>
        """
        return f"{self.ip}:{self.port} {self.sequence_number} {1} HELLO"

    def craft_message_bye(self) -> str:
        """
        Cria uma mensagem BYE.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> <OPERACAO>
        """
        return f"{self.ip}:{self.port} {self.sequence_number} {1} BYE"

    def craft_message_search_flooding(
            self,
            origin: str,
            sequence_number: int,
            ttl: int,
            key: str,
            hop_count: int
    ) -> str:
        """
        Cria uma mensagem de busca por flooding.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> SEARCH <MODE> <LAST_HOP_PORT> <KEY> <HOP_COUNT>
        """
        # OBS: Informações são passadas por parâmetro para facilitar a criação de mensagens de reenvio
        return f"{origin} {sequence_number} {ttl} SEARCH FL {self.port} {key} {hop_count}"

    def craft_message_search_random_walk(
            self,
            origin: str,
            sequence_number: int,
            ttl: int,
            key: str,
            hop_count: int
    ) -> str:
        """
        Cria uma mensagem de busca por random walk.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> SEARCH <MODE> <LAST_HOP_PORT> <KEY> <HOP_COUNT>
        """
        # OBS: Informações são passadas por parâmetro para facilitar a criação de mensagens de reenvio
        return f"{origin} {sequence_number} {ttl} SEARCH RW {self.port} {key} {hop_count}"

    def craft_message_search_depth_first(
            self,
            origin: str,
            sequence_number: int,
            ttl: int,
            key: str,
            hop_count: int
    ) -> str:
        """
        Cria uma mensagem de busca em profundidade.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> SEARCH <MODE> <LAST_HOP_PORT> <KEY> <HOP_COUNT>
        """
        # OBS: Informações são passadas por parâmetro para facilitar a criação de mensagens de reenvio
        return f"{origin} {sequence_number} {ttl} SEARCH BP {self.port} {key} {hop_count}"

    def craft_message_value(
            self,
            mode: str,
            key: str,
            value: str,
            hop_count: int
    ) -> str:
        """
        Cria uma mensagem VALUE.
        Formato da mensagem <ORIGIN> <SEQNO> <TTL> VAL <MODE> <KEY> <VALUE> <HOP_COUNT>
        """
        return f"{self.ip}:{self.port} {self.sequence_number} {self.default_ttl} VAL {mode} {key} {value} {hop_count}"

    def pick_neighbor(self) -> socket.socket | None:
        """Retorna o vizinho escolhido pelo usuário"""
        print("Escolha o vizinho:")
        self.show_neighbors()

        if len(self.neighbors) == 0:
            return None

        neighbor_idx = int(input(""))
        if neighbor_idx < 0 or neighbor_idx >= len(self.neighbors):
            return None
        neighbor_chosen_key = list(self.neighbors.keys())[neighbor_idx]
        return self.neighbors[neighbor_chosen_key]

    def handle_menu_action(self) -> None:
        """Lida com a opção escolhida pelo usuário no menu."""
        option = Node.get_user_menu_option()
        if option is None:
            print("Opção inválida")
            return

        if option == MenuOptions.LISTAR_VIZINHOS.value:
            self.show_neighbors()
        elif option == MenuOptions.HELLO.value:
            self.handle_menu_hello()
        elif option == MenuOptions.SEARCH_FLOODING.value:
            self.handle_menu_search_flooding()
        elif option == MenuOptions.SEARCH_RANDOM_WALK.value:
            self.handle_menu_search_random_walk()
        elif option == MenuOptions.SEARCH_DEPTH_FIRST.value:
            self.handle_menu_search_depth_first()
        elif option == MenuOptions.ESTATISTICAS.value:
            self.show_statistics()
        elif option == MenuOptions.ALTERAR_TTL.value:
            self.handle_menu_alterar_ttl()
        elif option == MenuOptions.SAIR.value:
            self.handle_menu_quit()

    @staticmethod
    def get_user_menu_option() -> int | None:
        """
        Pega a opção do menu escolhida pelo usuário.
        Retorna None se a opção não for válida.
        """
        menu_options = [menu_option.value for menu_option in MenuOptions]
        option = input("")

        if not option.isdigit() or int(option) not in menu_options:
            return None

        return int(option)

    def handle_menu_hello(self) -> None:
        """Lida com a opção do menu de enviar uma mensagem HELLO."""
        peer = self.pick_neighbor()
        if peer is None:
            print("Vizinho inválido")
            return
        self.send_hello(peer)

    def handle_menu_search_flooding(self) -> None:
        """Lida com a opção do menu de iniciar uma busca por flooding."""
        key = input("Digite a chave a ser buscada\n")
        if not Node.is_valid_key(key):
            print("Chave inválida")
            return

        if key in self.data:
            print("Valor na tabela local")
            print(f"    chave: {key} valor: {self.data[key]}")
        else:
            self.start_search_flooding(key)

    def handle_menu_search_random_walk(self) -> None:
        """Lida com a opção do menu de iniciar uma busca por random walk."""
        key = input("Digite a chave a ser buscada\n")
        if not Node.is_valid_key(key):
            print("Chave inválida")
            return

        if key in self.data:
            print("Valor na tabela local")
            print(f"    chave: {key} valor: {self.data[key]}")
        else:
            self.start_search_random_walk(key)

    def handle_menu_search_depth_first(self) -> None:
        """Lida com a opção do menu de iniciar uma busca em profundidade."""
        key = input("Digite a chave a ser buscada\n")
        if not Node.is_valid_key(key):
            print("Chave inválida")
            return

        if key in self.data:
            print("Valor na tabela local")
            print(f"    chave: {key} valor: {self.data[key]}")
        else:
            self.start_search_depth_first(key)

    def handle_menu_alterar_ttl(self) -> None:
        """Lida com a opção do menu de alterar o valor padrão de TTL."""
        novo_ttl = input("Digite novo valor de TTL\n")
        if not novo_ttl.isdigit() or int(novo_ttl) <= 0:
            print("Valor de TTL inválido")
            return

        self.default_ttl = novo_ttl

    def handle_menu_quit(self) -> None:
        """Lida com a opção do menu de sair."""
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
        node.handle_menu_action()
