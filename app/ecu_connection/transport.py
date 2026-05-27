from abc import ABC, abstractmethod


class EcuTransport(ABC):
    """Interface abstrata para transporte físico de dados com a ECU.

    Implementações: SerialTransport (porta serial real) e MockTransport (replay CSV).
    """

    @abstractmethod
    def connect(self) -> None:
        """Abre a conexão física (abre porta serial ou inicia replay do CSV).

        Deve bloquear até a conexão estar estabelecida ou lançar exceção em caso de falha.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Fecha a conexão física de forma limpa."""
        ...

    @abstractmethod
    def readline(self) -> str:
        """Leitura bloqueante de uma linha.

        Retorna a linha sem o caractere de newline final.
        Retorna string vazia se o timeout expirar sem dados.
        Timeout deve ser configurável na implementação concreta (sugestão: 1-3 segundos).
        """
        ...

    @abstractmethod
    def write(self, line: str) -> None:
        """Escreve uma linha no transporte, adicionando '\\n' ao final.

        Deve ser thread-safe ou documentar que não é.
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Retorna True se a conexão física está estabelecida."""
        ...
