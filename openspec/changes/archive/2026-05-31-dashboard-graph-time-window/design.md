## Context

Os gráficos atualmente usam `graph_x_size` (número de amostras) como tamanho do deque e como largura do eixo X. Com o eixo X agora baseado em `time.monotonic` (mudança `synchronize-frame-graph-updates`), o X range é definido como `[ts[0], ts[-1]]` — ou seja, ele se expande conforme o buffer enche e depois estabiliza, mas não tem largura fixa em tempo real.

O problema visível: sinais calculados (POWER, TORQUE, VE_LAMBDA) são incluídos em `parsed_data` a cada frame (D01, D02, D03), acumulando 3× mais amostras por ciclo que sinais raw. Com `graph_x_size=150`, o buffer de POWER esgota em ~2.5s enquanto RPM leva ~7.5s — as curvas no mesmo gráfico exibem janelas de tempo diferentes.

Pontos de mudança no código:
- `app/config.py` → `AppConfigDashboard.graph_x_seconds` (lido de config), `graph_x_size` vira propriedade derivada
- `app/ui/window.py` → repassa `graph_x_seconds` ao construtor de `DashboardScreen`
- `app/ui/dashboard/screen.py` → construtor recebe `graph_x_seconds`; `update_graph` usa janela temporal fixa

## Goals / Non-Goals

**Goals:**
- Todos os gráficos exibem sempre exatamente a janela `[t_now - graph_x_seconds, t_now]`
- Curvas de sinais com densidades de amostragem diferentes ficam visualmente comparáveis
- Um único parâmetro de config (`graph_x_seconds`) controla a janela temporal
- Deque grande o suficiente para nunca perder dados dentro da janela visível

**Non-Goals:**
- Corrigir o root cause do over-sampling dos sinais calculados (problema separado)
- Permitir zoom/pan temporal pelo usuário
- Mostrar marcadores de tempo no eixo X (eixo permanece oculto)

## Decisions

### `graph_x_seconds` no config; `graph_x_size` como derivado

**Decisão**: `config.json` passa a ter `graph_x_seconds` (int, default 30). `AppConfigDashboard` calcula `graph_x_size = graph_x_seconds * 60` internamente — suficiente para 60 Hz de amostragem por sinal sem configuração adicional.

**Rationale**: O usuário pensa em "quantos segundos quero ver", não em "quantas amostras". O fator 60 cobre qualquer taxa razoável (ECU a 20 Hz × 3 frames = 60 amostragens/s para sinais calculados). Manter `graph_x_size` como derivado preserva o resto do código que usa o deque sem mudança.

Alternativa considerada: manter `graph_x_size` configurável separadamente. Rejeitado — dois parâmetros inter-dependentes criam confusão.

### X range fixo calculado no `update_graph` a partir do último timestamp

**Decisão**: Em `update_graph`, para cada sinal com buffer não-vazio, usar:
```
t_now = ts[-1]
base_view.setXRange(t_now - graph_x_seconds, t_now, padding=0)
```

**Rationale**: `ts[-1]` é o dado mais recente disponível para aquele sinal — não `time.monotonic()` puro — evitando um gap visual no lado direito quando o ECU pausa. `padding=0` garante que a janela seja exatamente `graph_x_seconds`.

Alternativa: usar `time.monotonic()` como `t_now`. Rejeitado — causaria gap crescente no lado direito se o ECU parar de enviar dados.

### Renomear parâmetro do construtor de `DashboardScreen`

**Decisão**: O parâmetro `graph_x_size` do construtor passa a ser `graph_x_seconds`. O deque é criado com `maxlen = graph_x_seconds * 60` internamente.

**Rationale**: Mantém o contrato do construtor alinhado com o config — nenhum chamador precisa calcular maxlen externamente.

## Risks / Trade-offs

- **Over-sampling de sinais calculados ainda existe**: a janela fixa torna o problema *visível* mas não o resolve. Sinais calculados aparecem com curva mais densa no mesmo período. → Aceitável como ferramenta de investigação; a correção vem em change separado.
- **Deque maior em memória**: `graph_x_seconds=30 × 60 = 1800` amostras por sinal vs. 150 antes. A ~8 bytes/float × 1800 × ~15 sinais = ~216 KB — desprezível.
- **Primeiro render mostra janela parcialmente vazia**: antes de `graph_x_seconds` de dados acumulados, o lado esquerdo do gráfico ficará em branco. → Comportamento correto e esperado.
