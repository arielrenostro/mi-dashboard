## 1. SignalsReceivedEvent — campo timestamp

- [x] 1.1 Importar `time` em `app/event/app_events.py`
- [x] 1.2 Adicionar `timestamp: float = field(default_factory=time.monotonic)` em `SignalsReceivedEvent`

## 2. DashboardScreen — deques de timestamp e base_views

- [x] 2.1 Adicionar `self.timestamps: Dict[Signal, deque]` em `__init__`, inicializado junto com `self.buffers`
- [x] 2.2 Adicionar `self.base_views: Dict[Signal, pg.ViewBox]` em `__init__`
- [x] 2.3 Em `_create_graphs`, após criar `base_view`, armazenar `self.base_views[signal] = base_view` para cada sinal do plot
- [x] 2.4 Em `_create_graphs`, remover o `curve.getViewBox().setXRange(0, graph_x_size + 1, padding=0)` estático
- [x] 2.5 Em `_create_graphs`, inicializar `self.timestamps[signal] = deque(maxlen=graph_x_size)` junto com `self.buffers[signal]`

## 3. DashboardScreen — recepção do evento com timestamp

- [x] 3.1 Em `on_activated`, trocar `lambda e: self.on_signal_received(e.data)` por `lambda e: self.on_signal_received(e)`
- [x] 3.2 Alterar assinatura de `on_signal_received` para receber o evento completo (`event: SignalsReceivedEvent`)
- [x] 3.3 Em `on_signal_received`, ao fazer `buff.append(data.value)`, também fazer `self.timestamps[signal].append(event.timestamp)`

## 4. DashboardScreen — renderização com eixo X de tempo

- [x] 4.1 Em `update_graph`, trocar `data = list(self.buffers[signal])` para extrair `ts = list(self.timestamps[signal])` e `ys = list(self.buffers[signal])`
- [x] 4.2 Trocar `curve.setData(data)` por `curve.setData(ts, ys)`
- [x] 4.3 Ao calcular posição do marcador de pico/mín, trocar `value_index` por `ts[value_index]` em `setData` e `setPos`
- [x] 4.4 Adicionar atualização dinâmica do X range: se `ts` não estiver vazio, chamar `self.base_views[signal].setXRange(ts[0], ts[-1], padding=0.01)`; se vazio, não chamar `setXRange`
