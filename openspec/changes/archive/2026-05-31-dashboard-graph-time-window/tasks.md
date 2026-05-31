## 1. Config — novo campo graph_x_seconds

- [x] 1.1 Em `AppConfigDashboard.__init__`, adicionar `self.graph_x_seconds: int = config_dict.get('graph_x_seconds', 30)`
- [x] 1.2 Em `AppConfigDashboard.__init__`, derivar `self.graph_x_size: int = self.graph_x_seconds * 60` (remover o `config_dict.get('graph_x_size', 150)` atual)
- [x] 1.3 Em `config.json`, substituir `"graph_x_size": 150` por `"graph_x_seconds": 30`

## 2. AppWindow — repassar graph_x_seconds ao DashboardScreen

- [x] 2.1 Em `app/ui/window.py`, trocar `graph_x_size=config.dashboard.graph_x_size` por `graph_x_seconds=config.dashboard.graph_x_seconds`

## 3. DashboardScreen — aceitar graph_x_seconds e calcular maxlen internamente

- [x] 3.1 Em `DashboardScreen.__init__`, renomear parâmetro `graph_x_size` para `graph_x_seconds`
- [x] 3.2 Em `DashboardScreen.__init__`, calcular `graph_x_size = graph_x_seconds * 60` e armazenar em `self.graph_x_seconds = graph_x_seconds`
- [x] 3.3 Passar `graph_x_size` (derivado) para `_create_graphs` — a assinatura de `_create_graphs` não muda

## 4. DashboardScreen — janela temporal fixa no update_graph

- [x] 4.1 Em `update_graph`, substituir `self.base_views[signal].setXRange(ts[0], ts[-1], padding=0.01)` por `self.base_views[signal].setXRange(ts[-1] - self.graph_x_seconds, ts[-1], padding=0)` quando `ts` não estiver vazio
