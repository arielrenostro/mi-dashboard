# Plano 01 — ECU: Commands/Responses e Separação de Camadas

## Objetivo

Reestruturar a camada ECU para que:
- Comandos e respostas sejam classes com serializer próprio, mantendo tipagem forte
- A camada de conexão (transport) gerencie apenas bytes
- Comportamentos (handshake, fila de comandos, streaming) vivam em uma camada de sessão separada

---

## Arquitetura Proposta

```
EcuTransport (ABC) ← só bytes: open/close/readline/writeline
    ├── SerialTransport        ← pyserial
    └── MockTransport          ← lê CSV, injeta respostas via fila interna

EcuSession                     ← handshake, fila de comandos, framing, streaming
    └── usa EcuTransport (injetado)

EcuCommand (dataclass + registry)  ← substitui Enum atual, tem serialize()
EcuResponse (dataclass + registry) ← substitui Enum atual, tem matches() e parse_*()

EcuSessionThread (QThread)     ← substitui EcuConnectionThread, wraps EcuSession
```

---

## 1. Novos Arquivos e Estrutura

```
app/
├── ecu_protocol/              ← NOVO módulo
│   ├── __init__.py
│   ├── commands.py            ← EcuCommand dataclass + CommandRegistry
│   └── responses.py           ← EcuResponse dataclass + ResponseRegistry
│
├── ecu_connection/
│   ├── transport.py           ← NOVO: EcuTransport (ABC puro de bytes)
│   ├── transport_serial.py    ← NOVO: SerialTransport
│   ├── transport_mock.py      ← NOVO: MockTransport (substitui mock_log.py)
│   ├── session.py             ← NOVO: EcuSession (substitui serial.py)
│   ├── thread.py              ← ATUALIZADO: EcuSessionThread
│   ├── ecu_connection.py      ← MANTER: EcuConnectionStatus
│   └── __init__.py            ← ATUALIZADO: register_ecu_session
│
└── masterinjection/
    └── protocol.py            ← DELETAR após migração
```

---

## 2. `EcuCommand` — Dataclass com `serialize()`

**`app/ecu_protocol/commands.py`:**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass(frozen=True)
class EcuCommand:
    name: str
    wire: str          # string de protocolo: "#D50", "#F01", etc.
    description: str

    def serialize(self, args: Optional[List[Any]] = None) -> str:
        """Formata o comando para envio — sem '\n' (adicionado pelo transport)."""
        if args:
            return f"{self.wire};{';'.join(str(a) for a in args)}"
        return self.wire

    def __eq__(self, other):
        if isinstance(other, EcuCommand):
            return self.wire == other.wire
        return NotImplemented

    def __hash__(self):
        return hash(self.wire)


class _CommandRegistry:
    """Registry com acesso por atributo e por nome — ergonomia idêntica ao Enum."""

    def __init__(self):
        self._by_name: dict[str, EcuCommand] = {}
        self._by_wire: dict[str, EcuCommand] = {}

    def _register(self, name: str, wire: str, description: str) -> EcuCommand:
        cmd = EcuCommand(name=name, wire=wire, description=description)
        self._by_name[name] = cmd
        self._by_wire[wire] = cmd
        return cmd

    def __getattr__(self, name: str) -> EcuCommand:
        try:
            return self._by_name[name]
        except KeyError:
            raise AttributeError(f"Comando ECU desconhecido: {name!r}")

    def __getitem__(self, name: str) -> EcuCommand:
        return self._by_name[name]

    def get_by_wire(self, wire: str) -> Optional[EcuCommand]:
        return self._by_wire.get(wire)


commands = _CommandRegistry()

commands._register("ECU_INFO",          "#D50", "Get ECU Info")
commands._register("STREAMING_STOP",    "#D00", "Stop Streaming")
commands._register("STREAMING_START",   "#D01", "Start Streaming")
commands._register("WRITE_ON_MEMORY",   "#D04", "Write on Memory")
commands._register("LAMBDA_LOOP_CLOSE", "#D05", "Close Lambda Loop")
commands._register("LAMBDA_LOOP_OPEN",  "#D06", "Open Lambda Loop")
commands._register("RPM_BREAKPOINTS",   "#I20", "RPM Breakpoints")
commands._register("MAP_BREAKPOINTS",   "#I21", "MAP Breakpoints")

for _i in range(1, 17):
    commands._register(f"VE_ROW_{_i}", f"#F{_i:02d}", f"VE {_i} line")
```

---

## 3. `EcuResponse` — Dataclass com `matches()` e `parse_*()`

**`app/ecu_protocol/responses.py`:**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EcuResponse:
    name: str
    wire_prefix: str   # "#D01", "#I20", etc.

    def matches(self, line: str) -> bool:
        return line.startswith(self.wire_prefix)

    def parse_values(self, line: str) -> list[str]:
        return line.split(";")[1:]

    def parse_ints(self, line: str) -> list[int]:
        return [int(v) for v in self.parse_values(line)]

    def __eq__(self, other):
        if isinstance(other, EcuResponse):
            return self.wire_prefix == other.wire_prefix
        return NotImplemented

    def __hash__(self):
        return hash(self.wire_prefix)


class _ResponseRegistry:
    def __init__(self):
        self._by_name: dict[str, EcuResponse] = {}
        self._by_prefix: dict[str, EcuResponse] = {}

    def _register(self, name: str, wire_prefix: str) -> EcuResponse:
        r = EcuResponse(name=name, wire_prefix=wire_prefix)
        self._by_name[name] = r
        self._by_prefix[wire_prefix] = r
        return r

    def __getattr__(self, name: str) -> EcuResponse:
        try:
            return self._by_name[name]
        except KeyError:
            raise AttributeError(f"Resposta ECU desconhecida: {name!r}")

    def __getitem__(self, name: str) -> EcuResponse:
        return self._by_name[name]

    def get_by_prefix(self, line: str) -> Optional[EcuResponse]:
        for prefix, r in self._by_prefix.items():
            if line.startswith(prefix):
                return r
        return None


responses = _ResponseRegistry()

responses._register("ECU_INFO",        "#D50")
responses._register("MESS_DATA_1",     "#D01")
responses._register("MESS_DATA_2",     "#D02")
responses._register("MESS_DATA_3",     "#D03")
responses._register("RPM_BREAKPOINTS", "#I20")
responses._register("MAP_BREAKPOINTS", "#I21")

for _i in range(1, 17):
    responses._register(f"VE_ROW_{_i}", f"#F{_i:02d}")
```

---

## 4. `EcuTransport` — Camada de Bytes Puros

**`app/ecu_connection/transport.py`:**

```python
from abc import ABC, abstractmethod


class EcuTransport(ABC):
    """Abstração de baixo nível: abre/fecha conexão e lê/escreve linhas.
    NÃO conhece comandos, handshake ou estado da aplicação."""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def readline(self) -> str:
        """Lê uma linha decodificada sem '\\n'. Timeout retorna ''."""
        ...

    @abstractmethod
    def writeline(self, data: str) -> None:
        """Escreve data + '\\n' em utf-8."""
        ...
```

**`app/ecu_connection/transport_serial.py`:**

```python
import serial
from app.ecu_connection.transport import EcuTransport


class SerialTransport(EcuTransport):

    def __init__(self, port: str, baudrate: int):
        self._serial = serial.Serial(baudrate=baudrate, timeout=1, write_timeout=1)
        self._serial.port = port

    def open(self) -> None:
        self._serial.open()

    def close(self) -> None:
        try:
            self._serial.close()
        except Exception:
            pass

    def is_open(self) -> bool:
        return self._serial.is_open

    def readline(self) -> str:
        return self._serial.readline().decode("utf-8").strip()

    def writeline(self, data: str) -> None:
        self._serial.write(f"{data}\n".encode("utf-8"))
```

**`app/ecu_connection/transport_mock.py`:** lê CSV, injeta respostas de breakpoints/VE via fila interna quando `writeline()` for chamado com os prefixos conhecidos (#I20, #I21, #F01..#F16). A lógica de timing do `EcuConnectionMock` atual migra para `_feed_loop()`.

---

## 4.1 Concorrência no Transport (pyserial)

`readline()` no pyserial 3.x é implementado via `read_until()` que chama `read(1)` em loop — **sem nenhum lock interno**. `write()` também não tem lock. O comportamento por cenário:

| Cenário | Seguro? | Motivo |
|---|---|---|
| `readline` + `write` simultâneos (threads diferentes) | **Sim** | SO mantém buffers RX e TX separados; sem estado Python compartilhado entre os caminhos |
| Dois `readline` simultâneos | **Não** | Bytes do mesmo frame seriam consumidos por threads diferentes |
| Dois `write` simultâneos | **Não** | Bytes de comandos distintos poderiam se intercalar |

**Conclusão:** uma única thread de leitura e um `threading.Lock` cobrindo todos os `writeline()` eliminam os dois riscos. Não é necessário lock para leitura simultânea à escrita.

---

## 5. `EcuSession` — Camada de Protocolo/Comportamento

**Design de concorrência:**

```
┌──────────────────────────────────────────────────────────────┐
│ EcuSessionThread (QThread)                                   │
│   run(): loop de reconexão usando isInterruptionRequested()  │
│     └─► session.start()                                      │
│             transport.open()                                 │
│             _reader_thread.start()  ← único leitor           │
│             _connect()  ← usa send_and_wait normalmente      │
│         session.wait_until_disconnected()                    │
│                                                              │
│ _reader_thread (daemon thread):                              │
│   read_loop() — loop enquanto transport.is_open()            │
│     ├── waiter registrado → waiter queue  (sequenciamento)   │
│     └── TODA linha        → on_line  (sempre, sem exceção)   │
│                                                              │
│ Qualquer thread (VeWriteController, _connect, etc.):         │
│   send_command()  → _write_lock → writeline()                │
│   send_and_wait() → registra waiter (só para sequenciar)     │
│                     _write_lock → writeline()                │
│                     bloqueia em queue.get(timeout)           │
└──────────────────────────────────────────────────────────────┘
```

**`app/ecu_connection/session.py`:**

```python
import queue
import threading
from typing import Callable, Optional

from app.ecu_connection.transport import EcuTransport
from app.ecu_protocol.commands import EcuCommand
from app.ecu_protocol.responses import EcuResponse
from app.ecu_connection.ecu_connection import EcuConnectionStatus


class EcuSession:
    """Gerencia o protocolo de comunicação.

    Responsabilidades: handshake, fetch de breakpoints/VE map, streaming,
    envio de comandos (fire-and-forget e send_and_wait).
    NÃO gerencia conexão física (delegado ao EcuTransport).
    NÃO faz framing, filtragem ou agrupamento de frames — repassa todas as
    linhas recebidas via on_line para que o consumidor decida o que fazer.

    Threading:
      - _reader_thread é o ÚNICO ponto que chama transport.readline().
      - _reader_thread inicia ANTES de _connect(), portanto send_and_wait()
        funciona da mesma forma durante handshake/fetch e durante streaming.
      - Todos os writeline() passam por _write_lock.
      - Ciclo de vida controlado pelo EcuSessionThread; a sessão não mantém
        flag próprio de "running".
    """

    def __init__(self, transport: EcuTransport):
        self._transport = transport
        self._write_lock = threading.Lock()
        self._pending: dict[str, queue.Queue] = {}
        self._pending_lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._status = EcuConnectionStatus.DISCONNECTED
        self.on_line: Optional[Callable[[str], None]] = None  # injetado pelo thread

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def send_command(self, cmd: EcuCommand, args=None) -> None:
        """Envia comando sem aguardar resposta. Thread-safe."""
        with self._write_lock:
            self._transport.writeline(cmd.serialize(args or None))

    def send_and_wait(self, cmd: EcuCommand, expected: list[EcuResponse], timeout: float = 5.0) -> Optional[str]:
        """Envia comando e aguarda a primeira linha que case com algum prefixo esperado.

        Pode ser chamado de qualquer thread (inclusive durante _connect).
        Linhas não esperadas continuam sendo despachadas para on_line normalmente.
        Retorna a linha de resposta ou None se timeout expirar.
        """
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._pending_lock:
            for exp in expected:
                self._pending[exp.wire_prefix] = q
        try:
            with self._write_lock:
                self._transport.writeline(cmd.serialize())
            return q.get(timeout=timeout)
        except queue.Empty:
            return None
        finally:
            with self._pending_lock:
                for exp in expected:
                    self._pending.pop(exp.wire_prefix, None)

    def start(self) -> None:
        """Abre o transport, inicia o reader thread e executa o handshake/fetch.

        Retorna após _connect() concluir (streaming já iniciado).
        Se _connect() falhar, fecha o transport e propaga a exceção
        (o reader thread encerra sozinho quando transport fecha).
        """
        self._transport.open()
        self._reader_thread = threading.Thread(target=self.read_loop, daemon=True)
        self._reader_thread.start()
        try:
            self._connect()
        except Exception:
            self._transport.close()
            raise

    def wait_until_disconnected(self) -> None:
        """Bloqueia até o reader thread encerrar (transport fechado ou erro)."""
        if self._reader_thread:
            self._reader_thread.join()

    def stop(self) -> None:
        """Fecha o transport — read_loop encerra naturalmente ao detectar is_open() == False."""
        self._transport.close()

    def read_loop(self) -> None:
        """Loop de leitura contínua — executa no _reader_thread.

        É o ÚNICO ponto que chama transport.readline(). TODA linha recebida
        é publicada via on_line, sem exceção. Se houver um waiter registrado
        para o prefixo da linha (send_and_wait), a linha também é colocada na
        fila do waiter — apenas para fins de sequenciamento em _connect().
        Framing, filtragem e agrupamento de frames são responsabilidade do
        consumidor (ex: SignalProcessor).
        """
        while self._transport.is_open():
            line = self._transport.readline()
            if not line:
                continue

            with self._pending_lock:
                waiter = next(
                    (q for prefix, q in self._pending.items() if line.startswith(prefix)),
                    None,
                )
            if waiter is not None:
                waiter.put(line)

            if self.on_line:
                self.on_line(line)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        self._handshake()
        self._fetch_breakpoints()
        self._fetch_ve_map()
        self._start_streaming()

    def _handshake(self) -> None:
        from app.ecu_protocol.commands import commands
        from app.ecu_protocol.responses import responses
        self.send_and_wait(commands.ECU_INFO, [responses.ECU_INFO])

    def _fetch_breakpoints(self) -> None:
        from app.ecu_protocol.commands import commands
        from app.ecu_protocol.responses import responses
        self.send_and_wait(commands.RPM_BREAKPOINTS, [responses.RPM_BREAKPOINTS])
        self.send_and_wait(commands.MAP_BREAKPOINTS, [responses.MAP_BREAKPOINTS])

    def _fetch_ve_map(self) -> None:
        from app.ecu_protocol.commands import commands
        from app.ecu_protocol.responses import responses
        for i in range(1, 17):
            self.send_and_wait(commands[f"VE_ROW_{i}"], [responses[f"VE_ROW_{i}"]])

    def _start_streaming(self) -> None:
        from app.ecu_protocol.commands import commands
        with self._write_lock:
            self._transport.writeline(commands.STREAMING_START.serialize())
```

---

## 5.1 API de Comandos da ECU

`EcuSession` expõe métodos nomeados para cada operação que módulos externos precisam realizar. Nenhum consumidor precisa importar `commands` ou `responses` diretamente — a sessão encapsula o mapeamento comando/resposta.

### Comandos fire-and-forget (sem resposta esperada)

```python
# em EcuSession:

def close_lambda_loop(self) -> None:
    from app.ecu_protocol.commands import commands
    self.send_command(commands.LAMBDA_LOOP_CLOSE)

def open_lambda_loop(self) -> None:
    from app.ecu_protocol.commands import commands
    self.send_command(commands.LAMBDA_LOOP_OPEN)

def write_ve_row(self, row: int, values: list[int]) -> None:
    """Envia uma linha do mapa VE durante streaming ativo (sem aguardar ACK)."""
    from app.ecu_protocol.commands import commands
    self.send_command(commands[f"VE_ROW_{row}"], values)
```

### Comandos com resposta síncrona (padrão para futuros comandos)

Quando um comando precisar de resposta durante o streaming, o padrão é:

```python
def meu_comando(self) -> Optional[str]:
    from app.ecu_protocol.commands import commands
    from app.ecu_protocol.responses import responses
    return self.send_and_wait(commands.MEU_CMD, [responses.MEU_CMD], timeout=3.0)
```

`send_and_wait` registra o waiter, escreve o comando e bloqueia em `queue.get(timeout)`. O `read_loop` continua despachando todas as outras linhas para `on_line` enquanto aguarda — o streaming não é interrompido.

### Quadro completo — comandos × callers

| Método na sessão | Caller atual | Fire-and-forget? |
|---|---|---|
| `close_lambda_loop()` | `LambdaToggle` | Sim |
| `open_lambda_loop()` | `LambdaToggle` | Sim |
| `write_ve_row(row, values)` | `VeWriteController` | Sim |
| *(internos: `_handshake`, `_fetch_breakpoints`, `_fetch_ve_map`)* | `_connect()` | Não — usam `send_and_wait` |

> **Nota:** `LambdaToggle` continua publicando `EcuCommandRequestedEvent` no bus antes de chamar o método da sessão — a responsabilidade de notificar outros módulos (ex: `LambdaLoopStateProcessor`) permanece no caller, não na sessão.

---

## 6. `EcuSessionThread` e Registry

**`app/ecu_connection/thread.py`:**

```python
class EcuSessionThread(QThread):
    emitter = pyqtSignal(str)

    def __init__(self, session: EcuSession):
        super().__init__()
        self._session = session
        self._session.on_line = self.emitter.emit

    def run(self):
        while not self.isInterruptionRequested():
            try:
                self._session.start()
                self._session.wait_until_disconnected()
            except Exception:
                pass  # loga e tenta reconectar

    def stop(self):
        self.requestInterruption()
        self._session.stop()
        self.wait()
```

**`app/ecu_connection/__init__.py`:**

```python
def register_ecu_session(session: EcuSession): ...
def get_ecu_connection() -> EcuSession: ...        # nome mantido para retrocompat
def get_ecu_connection_thread() -> EcuSessionThread: ...
```

---

## 7. Impacto em Outros Módulos

| Arquivo | O que muda |
|---------|-----------|
| `app/masterinjection/signal_processor.py` | Recebe linhas individuais via `on_line`; passa a acumular D01 e só processar ao receber D02 (framing migra do transport para cá). Também trata `#I20`/`#I21` e `#F01–#F16`, publicando eventos de breakpoints e VE map no bus |
| `app/state/state.py` (`VehicleState`) | Passa a receber breakpoints e VE map via eventos do bus (publicados pelo `SignalProcessor`), não mais via chamada direta da sessão |
| `app/event/lambda_toggle.py` | `send_command(EcuCommand.LAMBDA_LOOP_*)` → `session.close_lambda_loop()` / `open_lambda_loop()` |
| `app/ui/ve_calibration/ve_write_controller.py` | `send_command(EcuCommand[VE_ROW_N], values)` → `session.write_ve_row(n, values)` |
| `app/state/processors/lambda_loop_state.py` | Sem mudança — continua ouvindo `ECU_COMMAND_REQUESTED` no bus |
| `main.py` | `register_ecu_connection(EcuConnectionSerial(...))` → `register_ecu_session(EcuSession(SerialTransport(...)))` |
| `app/ecu_connection/serial.py` | Deletar após migração |
| `app/ecu_connection/mock_log.py` | Deletar após migração |
| `app/masterinjection/protocol.py` | Deletar após migração |

---

## 8. Passos de Implementação

```
FASE 1 — Criar nova infraestrutura (zero breaking changes)
  [1a] Criar app/ecu_protocol/commands.py + responses.py + __init__.py
  [1b] Criar app/ecu_connection/transport.py
       ← [1a] e [1b] em paralelo

FASE 2 — Implementar transportes
  [2a] Criar transport_serial.py              ← depende de [1b]
  [2b] Criar transport_mock.py                ← depende de [1b]
       ← [2a] e [2b] em paralelo

FASE 3 — Implementar EcuSession
  [3]  Criar session.py                       ← depende de [1a], [1b], [2a], [2b]

FASE 4 — Atualizar thread e registry
  [4]  Atualizar thread.py (EcuSessionThread) ← depende de [3]
  [5]  Atualizar __init__.py (register_ecu_session) ← depende de [3]

FASE 5 — Migrar consumidores (paralelo entre si, todos dependem de [1a])
  [6a] signal_processor.py   — responses.MESS_DATA_1.wire_prefix
  [6b] lambda_toggle.py      — commands.LAMBDA_LOOP_*
  [6c] ve_write_controller.py — commands[VE_ROW_N]
  [6d] lambda_loop_state.py  — commands.*

FASE 6 — Atualizar main.py
  [7]  main.py: trocar register_ecu_connection → register_ecu_session ← depende de [4], [5]

FASE 7 — Limpeza
  [8]  Deletar serial.py, mock_log.py, protocol.py
```

---

## 9. Decisões de Design

**Por que `_CommandRegistry` e não Enum?**
`Enum` não suporta herança de valores, geração em loop sem hacks, nem métodos com lógica por instância. A `dataclass + registry` entrega ergonomia idêntica (`commands.VE_ROW_1`, `commands["VE_ROW_1"]`) sem limitações.

**Por que `MockTransport.writeline()` injeta respostas via fila?**
`EcuSession.send_and_wait()` funciona identicamente para serial e mock: escreve → espera resposta. O mock injeta a resposta esperada na `_rx_queue` do seu `read_loop`. Isso elimina a duplicação da lógica de fetch que hoje existe no `EcuConnectionMock`.

**Por que `EcuSession` não conhece `VehicleState`?**
Toda linha recebida da ECU é publicada via `on_line` — inclusive as respostas a `send_and_wait`. O `SignalProcessor` trata `#I20`/`#I21` (breakpoints) e `#F01–#F16` (VE map) e publica eventos no bus. `VehicleState` assina esses eventos e atualiza seu estado. A sessão não precisa saber sobre estado de aplicação.

**Por que `send_and_wait` existe se tudo já vai para `on_line`?**
`send_and_wait` serve exclusivamente para sequenciamento em `_connect()`: garante que o handshake complete antes de buscar breakpoints, que breakpoints estejam prontos antes de buscar o VE map, e assim por diante. Não é um mecanismo de entrega de dados — é uma barreira de sincronização.

**Por que `_write_lock` e não fila de comandos?**
A fila de comandos da versão anterior acoplava escrita ao ciclo de leitura (drenada após cada frame). Com leitura em loop contínuo, uma fila exigiria polling ou um `select()` adicional. O `Lock` é mais simples: escritas são curtas e raras; contenção é desprezível.
