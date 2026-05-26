# Plano 01 — Refatoração da Camada ECU

## Objetivo

Separar a camada de **transporte** (serial/mock) da camada de **protocolo** (handshake, serialização, parsing de respostas), e introduzir serializadores por instrução para que cada comando ECU saiba como se serializar/deserializar independentemente.

---

## Estado Atual

### Problemas Identificados

1. **Handshake acoplado ao transporte** — `EcuConnectionSerial.connect()` executa toda a sequência de handshake (`_start_communication`, `_fetch_breakpoints`, `_fetch_ve_map`, `_start_streaming`). O mock repete dados hardcoded em vez de simular o handshake.

2. **Sem serializadores por instrução** — O formato `cmd;arg1;arg2;...\n` está hardcoded em `_drain_command_queue()` sem validação de aridade ou tipo por comando.

3. **Acumulação de frames D01/D02 no transporte** — `serial.py` usa `self.d01` e `self.d02` para acumular e emitir frame combinado. Isso pertence ao protocolo, não ao transporte.

4. **`vehicle_state` atualizado dentro da conexão** — `serial.py` chama `vehicle_state.set_map_breakpoints()`, `set_rpm_breakpoints()`, `set_ve_map()` durante o handshake, acoplando transporte ao estado da aplicação.

5. **Injeção de `emitter` pós-construção** — `EcuConnectionThread` injeta o `pyqtSignal` no `EcuConnection` após a construção. Conexão não sabe de PyQt6 mas recebe um objeto PyQt6.

---

## Arquitetura Proposta

```
┌──────────────────────────────────────────────────────────┐
│                   EcuProtocol                            │
│  - handshake sequence                                    │
│  - command/response dispatch                             │
│  - frame accumulation (D01 + D02)                        │
│  - emite EcuFrameEvent / EcuCommandResponseEvent         │
│                                                          │
│  usa ──► EcuTransport (ABC)                              │
│              ├── EcuSerialTransport                      │
│              └── EcuMockTransport                        │
└──────────────────────────────────────────────────────────┘
```

---

## Novas Classes e Responsabilidades

### `EcuTransport` (ABC) — `app/ecu_connection/transport.py`

Responsável **apenas** por enviar e receber bytes/strings brutas.

```python
class EcuTransport(ABC):
    @abstractmethod
    def connect(self) -> None: ...          # Abre porta/arquivo
    @abstractmethod
    def disconnect(self) -> None: ...       # Fecha porta/arquivo
    @abstractmethod
    def write_line(self, line: str) -> None: ...   # Envia string + '\n'
    @abstractmethod
    def read_line(self) -> str: ...         # Lê linha (bloqueante, timeout)
    @abstractmethod
    def is_open(self) -> bool: ...
```

**Implementações:**
- `EcuSerialTransport` — encapsula `serial.Serial`, sem lógica de protocolo
- `EcuMockTransport` — lê arquivo CSV, sem inicialização de `vehicle_state`

### `EcuCommandSerializer` (ABC) — `app/ecu_connection/serializers.py`

```python
class EcuCommandSerializer(ABC):
    @abstractmethod
    def serialize(self, args: list) -> str:
        """Retorna string pronta para envio (sem '\n')."""
        ...
    
    @abstractmethod
    def expected_responses(self) -> list[str]:
        """Prefixos de resposta esperados para este comando."""
        ...
    
    @abstractmethod
    def parse_response(self, line: str) -> dict:
        """Transforma a linha de resposta em dados estruturados."""
        ...
```

**Implementações concretas:**
- `SimpleCommandSerializer` — comandos sem args e sem resposta de dados (`#D05`, `#D06`)
- `BreakpointsSerializer` — `#I20`/`#I21` com 16 valores; `parse_response` retorna `list[int]`
- `VeRowSerializer` — `#F01..#F16` com 16 valores; valida aridade
- `StreamingSerializer` — `#D01`/`#D02`/`#D03` — sem args, resposta é stream contínuo

### `EcuCommand` — Atualização

Cada entrada do enum aponta para seu serializer:

```python
class EcuCommand(enum.Enum):
    ECU_INFO          = CommandDef("#D50", "Get ECU Info",      SimpleCommandSerializer("#D50"))
    STREAMING_STOP    = CommandDef("#D00", "Stop Streaming",    SimpleCommandSerializer("#D00"))
    STREAMING_START   = CommandDef("#D01", "Start Streaming",   SimpleCommandSerializer("#D01"))
    LAMBDA_LOOP_CLOSE = CommandDef("#D05", "Close Lambda Loop", SimpleCommandSerializer("#D05"))
    LAMBDA_LOOP_OPEN  = CommandDef("#D06", "Open Lambda Loop",  SimpleCommandSerializer("#D06"))
    RPM_BREAKPOINTS   = CommandDef("#I20", "RPM Breakpoints",   BreakpointsSerializer("#I20"))
    MAP_BREAKPOINTS   = CommandDef("#I21", "MAP Breakpoints",   BreakpointsSerializer("#I21"))
    VE_ROW_1          = CommandDef("#F01", "VE 1 line",         VeRowSerializer("#F01"))
    # ... VE_ROW_2..VE_ROW_16
    
    @property
    def cmd(self) -> str:          return self.value.cmd
    @property
    def description(self) -> str:  return self.value.description
    @property
    def serializer(self) -> EcuCommandSerializer: return self.value.serializer
```

```python
@dataclass(frozen=True)
class CommandDef:
    cmd: str
    description: str
    serializer: EcuCommandSerializer
```

### `EcuProtocol` — `app/ecu_connection/protocol_handler.py`

Responsável pela sequência de handshake, acumulação de frames e despacho de respostas.

```python
class EcuProtocol:
    def __init__(self, transport: EcuTransport):
        self._transport = transport
        self._d01: str | None = None
        self._d02: str | None = None
        self._command_queue: queue.Queue = queue.Queue()
        
        # Callbacks (injetados por quem usa)
        self.on_mess_frame: Callable[[int, str], None] | None = None
        self.on_command_response: Callable[[EcuCommand, dict], None] | None = None
    
    def connect(self) -> None:
        """Executa handshake completo."""
        self._transport.connect()
        self._handshake()
        self._fetch_breakpoints()
        self._fetch_ve_map()
        self._start_streaming()
    
    def send_command(self, cmd: EcuCommand, args: list | None = None) -> None:
        """Thread-safe: enfileira para envio após próximo frame."""
        self._command_queue.put((cmd, args or []))
    
    def run_once(self) -> None:
        """Lê uma linha e processa. Chamado em loop por EcuConnectionThread."""
        line = self._transport.read_line()
        if not line:
            return
        
        if line.startswith("#D01"):
            self._d01 = line
        elif line.startswith("#D02"):
            self._d02 = line
            # Quando D02 chega, D01 já deve existir
            if self._d01:
                self._emit_mess_frame(1, self._d01)
                self._emit_mess_frame(2, self._d02)
                self._d01 = None
                self._d02 = None
                self._drain_command_queue()
        elif line.startswith("#D03"):
            self._emit_mess_frame(3, line)
        else:
            self._handle_other_response(line)
    
    def _emit_mess_frame(self, frame_num: int, line: str) -> None:
        if self.on_mess_frame:
            self.on_mess_frame(frame_num, line)
    
    def _drain_command_queue(self) -> None:
        while not self._command_queue.empty():
            cmd, args = self._command_queue.get_nowait()
            serialized = cmd.serializer.serialize(args)
            self._transport.write_line(serialized)
    
    def _send_and_wait(self, cmd: EcuCommand) -> str | None:
        """Envia e aguarda resposta (usado no handshake). Reenvia a cada 3 leituras vazias."""
        expected = cmd.serializer.expected_responses()
        count = 0
        while self._transport.is_open():
            if count % 3 == 0:
                serialized = cmd.serializer.serialize([])
                self._transport.write_line(serialized)
            count += 1
            line = self._transport.read_line()
            if not line:
                continue
            for prefix in expected:
                if line.startswith(prefix):
                    return line
        return None
    
    def _fetch_breakpoints(self) -> None:
        """Busca RPM e MAP breakpoints e invoca on_command_response."""
        for cmd in (EcuCommand.MAP_BREAKPOINTS, EcuCommand.RPM_BREAKPOINTS):
            line = self._send_and_wait(cmd)
            if line and self.on_command_response:
                data = cmd.serializer.parse_response(line)
                self.on_command_response(cmd, data)
    
    def _fetch_ve_map(self) -> None:
        """Busca as 16 linhas do mapa VE."""
        for row in range(1, 17):
            cmd = EcuCommand[f"VE_ROW_{row}"]
            line = self._send_and_wait(cmd)
            if line and self.on_command_response:
                data = cmd.serializer.parse_response(line)
                self.on_command_response(cmd, data)
```

### `EcuConnectionThread` — Simplificado

```python
class EcuConnectionThread(QThread):
    mess_frame_received = pyqtSignal(int, str)      # (frame_num, raw_line)
    command_response_received = pyqtSignal(object)  # EcuCommandResponseEvent
    
    def __init__(self, protocol: EcuProtocol):
        super().__init__()
        self._protocol = protocol
        self._protocol.on_mess_frame = self._on_mess_frame
        self._protocol.on_command_response = self._on_command_response
    
    def _on_mess_frame(self, frame_num: int, line: str):
        self.mess_frame_received.emit(frame_num, line)
    
    def run(self):
        while self.running:
            try:
                self._protocol.run_once()
            except Exception:
                logger.exception("Erro no loop ECU")
```

---

## Emissão de Eventos pelo EventBus

Quem conecta os sinais Qt ao event_bus é o `main.py`:

```python
ecu_thread.mess_frame_received.connect(
    lambda num, line: event_bus.publish(MessFrameEvent(frame=num, line=line))
)
ecu_thread.command_response_received.connect(
    lambda e: event_bus.publish(e)
)
```

Novos tipos de evento (`app/event/app_events.py`):

```python
class AppEventType(Enum):
    MESS_FRAME              = auto()   # Frame de dados da ECU (1, 2 ou 3)
    COMMAND_RESPONSE        = auto()   # Resposta a um comando enviado
    # ... demais eventos

@dataclass(frozen=True)
class MessFrameEvent(AppEvent):
    frame: int      # 1, 2 ou 3
    line: str       # linha raw
    type_: AppEventType = field(default=AppEventType.MESS_FRAME, init=False)

@dataclass(frozen=True)
class CommandResponseEvent(AppEvent):
    command: EcuCommand
    data: dict
    type_: AppEventType = field(default=AppEventType.COMMAND_RESPONSE, init=False)
```

---

## Arquivos a Criar/Modificar

| Ação | Arquivo |
|------|---------|
| **Criar** | `app/ecu_connection/transport.py` — ABC + Serial + Mock |
| **Criar** | `app/ecu_connection/serializers.py` — ABC + implementações |
| **Criar** | `app/ecu_connection/protocol_handler.py` — `EcuProtocol` |
| **Modificar** | `app/masterinjection/protocol.py` — `CommandDef`, `EcuCommand` atualizado |
| **Modificar** | `app/ecu_connection/thread.py` — usa `EcuProtocol`, emite `mess_frame_received` |
| **Modificar** | `app/ecu_connection/__init__.py` — registra `EcuProtocol` em vez de `EcuConnection` |
| **Remover** | `app/ecu_connection/serial.py` — absorvido por `EcuSerialTransport` + `EcuProtocol` |
| **Remover** | `app/ecu_connection/mock_log.py` — absorvido por `EcuMockTransport` |
| **Remover** | `app/ecu_connection/ecu_connection.py` — substituído por `EcuTransport` |
| **Modificar** | `app/event/app_events.py` — adiciona `MessFrameEvent`, `CommandResponseEvent` |
| **Modificar** | `app/event/bus.py` — adiciona signals para novos eventos |
| **Modificar** | `main.py` — conecta `mess_frame_received` ao event_bus; **remove** `get_ecu_connection().emitter.connect(signal_processor.process_line)` e `get_ecu_connection().emitter.connect(log_writer.write)` (linhas 77-78 atuais) |

---

## Ordem de Execução

1. Criar `CommandDef` e atualizar `EcuCommand` (sem quebrar nada ainda — compatibilidade via `cmd` property)
2. Criar `EcuCommandSerializer` ABC e implementações (sem usar ainda)
3. Criar `EcuTransport` ABC, `EcuSerialTransport`, `EcuMockTransport` (extraindo lógica de serial.py e mock_log.py)
4. Criar `EcuProtocol` com handshake e loop principal
5. Atualizar `EcuConnectionThread` para usar `EcuProtocol`
6. Adicionar `MessFrameEvent` e `CommandResponseEvent` ao event_bus
7. Atualizar `main.py` para conectar sinais aos eventos
8. Remover arquivos antigos (`serial.py`, `mock_log.py`, `ecu_connection.py`)

---

## Critérios de Aceite

- [ ] Mock executa handshake simulado (emite respostas de breakpoints e VE map)
- [ ] `vehicle_state` não é mais atualizado dentro da camada de transporte/protocolo
- [ ] Cada `EcuCommand` tem serializer associado que valida aridade de args
- [ ] `EcuSerialTransport` não contém lógica de protocolo (apenas `write_line`/`read_line`)
- [ ] Frames D01 e D02 são emitidos individualmente via `MessFrameEvent(frame=1, ...)` e `MessFrameEvent(frame=2, ...)`
- [ ] Todos os locais que chamavam `send_command` continuam funcionando sem alteração
