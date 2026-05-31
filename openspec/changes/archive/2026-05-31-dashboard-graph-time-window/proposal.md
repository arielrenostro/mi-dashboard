## Why

O eixo X dos gráficos atualmente mostra os últimos `graph_x_size` amostras, mas com sinais calculados acumulando amostras a taxas diferentes dos sinais raw (3× mais por ciclo ECU), a janela visível varia por sinal — tornando a comparação entre curvas inconsistente e dificultando investigação de problemas de sincronização.

## What Changes

- `config.json` ganha o campo `dashboard.graph_x_seconds` (padrão `30`) definindo a largura da janela de tempo visível nos gráficos
- `DashboardScreen` usa `graph_x_seconds` para fixar o range do eixo X em `[t_now - graph_x_seconds, t_now]` a cada render do timer, em vez de se ajustar ao extent dos dados do buffer
- `graph_x_size` (tamanho do deque) é calculado automaticamente como `graph_x_seconds × 60` (suficiente para até 60 Hz de amostragem por sinal) em vez de ser configurado diretamente — **BREAKING** para quem usava `graph_x_size` no config
- `AppConfig` e o carregamento de config refletem o novo campo

## Capabilities

### New Capabilities

### Modified Capabilities
- `dashboard-layout`: O comportamento do eixo X dos gráficos muda de "últimas N amostras" para "últimos N segundos"; `graph_x_size` deixa de ser campo de config e passa a ser derivado de `graph_x_seconds`

## Impact

- `config.json`: substituir `graph_x_size` por `graph_x_seconds`
- `app/config.py`: novo campo `graph_x_seconds`, remoção de `graph_x_size` (ou manutenção como derivado)
- `app/ui/dashboard/screen.py`: `update_graph` passa a usar janela temporal fixa; construtor recebe `graph_x_seconds` em vez de `graph_x_size`
- `main.py`: passar `graph_x_seconds` ao criar `DashboardScreen`
