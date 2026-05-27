Você é um orchestrator. Faça as ações abaixo:

1. Em um Agent Sonnet:
   1. Leia as seções de tarefas abaixo, elas podem estar em contradição ou mencionar comportamentos que impactem outras seções. Revise-as, ajuste conteúdos faltantes presentes em outras seções e leve em consideração que isto será utilizado para VibeCoding;
   2. Se existirem problemas identificados, liste ao usuário, permita que ele responda com os ajustes e fique em loop até que tudo seja resolvido;
   3. Documente elas num arquivo MD "0001-request-revision";
   4. Confronte estas especificações com as especificações do projeto. Procure por contradições, conflitos, itens faltantes e possíveis problemas;
   5. Se existirem problemas identificados, liste ao usuário, permita que ele responda com os ajustes e fique em loop até que tudo seja resolvido;
   6. Documente o resultado num arquivo MD "0002-spec-revision";

2. Em um Agent Sonnet:
   1. Leia o arquivo "0002-spec-revision" e quebre as mudanças em atividades com contexto, história de usuário, requisitos funcionais, requisitos não funcionais, specs, arquivos de referencia e tasks
   2. Gere um plano de execução que possa ser paralelizado;
   3. Documente o plano de execução no arquivo md "0003-execution-plan";
   4. Documente as atividades em arquivos md "XXXX-hist-XX";

3. Peça ao usuário confirmação para continuar. Após a confirmação, em um Agent Sonnet:
   1. Leia o "0003-execution-plan";
   2. Execute em Agents Sonnet o plano de ação.

4. Em um Agent Sonnet:
   1. Revise as entregas e gere um relatório MD.


Tarefas:
Comunicação com ECU:
- Precisa ser async;
- Read e Write devem acontecer em paralelo;
- Leituras realizadas sempre devem gerar eventos no Bus;
- Separar camada de transporte de camada de protocolo (session) da ECU;
- Na camada de Session, deve existir métodos para solicitar os dados da ECU (open_loop, close_loop, fetch_ve, fetch_ignition, etc.) para os comandos já definidos;
- A thread deve ser internalizada na Session, não sendo necessário instancia-la e sendo de controle da Session;
- Os comandos e respostas da ECU devem estar estruturados no projeto;
- Emitir evento "ECU_COMMAND_SEND" (Qualquer comando enviado)
- Emitir evento "ECU_COMMAND_RESPONSE" (Qualquer resposta, exceto MESS_FRAME)
- Emitir evento "ECU_MESS_FRAME" (D01, D02, D03", independente, um por recebimento)
- Todo envio de comando deve esperar por uma resposta da ECU que sempre será o mesmo código do comando enviado no início da linha. Ex: enviado "#F01;...", a ECU irá responder com "#F01;..." 
- Para comandos que definam dados na ECU, como definir o VE, deve ser esperada a resposta com os mesmos dados enviados (comando + args);
- Para comandos que recebem dados da ECU, como ler o VE, deve ser esperada a resposta com o comando + args;
- Para comandos que definam um estado na ECU, como definir open loop, deve ser esparada a resposta do mesmo comando enviado sem args;


Pipeline de dados (eventbus):
- Todo e qualquer evento deve passar pelo EventBus, com exceção das telas;
- Telas (UI) devem se increver nos eventos do EventBus desejados;
- Telas (UI) devem emitir eventos pelo EventBus que impactem em camadas fora da UI;
- Telas (UI) devem emitir eventos "locais", não misturando comportamentos de UI com o restante da aplicação;
- Revisar os eventos atuais, renomeando, criando ou excluindo desnecessários;
- LogWriter:
    - Deve acumular o mess frame 1 e 2, e então gravar uma nova linha do CSV;
    - Demais funcionalidades (timestamp, mark) devem continuar funcionando.
- SignalProcessor:
    - Não deve mais depender de receber o frame 1 e 2, deve processa-los individualmente, se inscrevendo no Bus para receber os ECU_MESS_FRAME;
    - Deve disparar os sinais pelo eventbus após o processamento, sempre permitindo envio parcial de dados (não todos os sinais).
- AlarmProcessor:
    - Deve conversar melhor com o VehicleState para popular o estado dos alertas, permitindo uma consulta em tempo real do estado do veículo através do VehicleState;
    - Não deve possuir uma thread rodando sempre sem necessidade, deve apenas conseguir tocar um áudio quando necessário.


VehicleState:
    - Deve ser desacoplado da tela e deve controlar o seu próprio estado independentemente;
    - Deve representar o estado atual do veículo, permitindo que qualquer camada da aplicação possa obter últimos sinais, estado de alerta, estado de lambda loop e etc. devem sempre estar presentes nele. 
