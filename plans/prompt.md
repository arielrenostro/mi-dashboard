Monte planejamentos para cada um dos tópicos abaixo e os escrevas em arquivos separados para serem executados. Faça a analise paralelizando agentes de análise usando o Sonnet e depois valide ao final utilizando o SOnnet também. 

ECU: 
- Entradas e saídas (Commands e Responses) muito bem definidas e estruturadas. Hoje existem as Enums que precisam ser reestruturadas e precisa de um serializador por instrução da ECU, permitindo que um serializador processe o comando para ECU, mas mantendo o comando estruturado dentro da aplicação em classes;
- Camada de conexão deve gerenciar apenas a conexão (serial ou mock). Os comportamentos, handshake, envio de comando, recebimento de dados e etc. devem estar em outra camada. Permitindo que a conexão seja trocada sem grandes alterações;

Pipeline de dados (eventbus):
- ECU deve emitir 2 tipos de eventos: COMMAND_RESPONSE e MESS_FRAME (1, 2 e 3);
- LogWriter:
    - Deve acumular o mess frame 1 e 2, e ai gravar uma nova linha do CSV;
    - Demais funcionalidades (timestamp, mark) devem continuar funcionando.
- SignalProcessor:
    - Não deve mais depender de receber o frame 1 e 2, deve processa-los individualmente;
    - Deve disparar os sinais pelo eventbus após o processamento, sempre permitindo envio parcial de dados (não todos os sinais).
- AlarmProcessor, deve conversar melhor com o VehicleState para popular o estado dos alertas, permitindo uma consulta em tempo real do estado do veículo através do VehicleState
- Telas (UI) devem se increver nos eventos desejados;
- Telas (UI) devem possuir eventos "locais", não misturando comportamentos de UI com o restante da aplicação.

Eventos:
- SCREEN_REQUESTED, remover. Ajustar o código para um comportamento mais localizado;
- ECU_COMMAND_REQUESTED, manter igual;
- ALARM_FIRED, manter igual;
- VEHICLE_STATE_CHANGED, remover;
- EVENT_MARK_REQUESTED, renomear para "LOG_EVENT_MARK_REQUEST";
- SIGNALS_RECEIVED, deve suportar o envio parcial de sinais (somente os alterados);

VehicleState: deve uma consulta em tempo real do estado do veículo, portanto, últimos sinais, estado de alerta, estado de lambda loop e etc. devem sempre estar presentes nele.

