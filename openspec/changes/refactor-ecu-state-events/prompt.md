Vamos ajustar a arquitetura do projeto, reestruturando a comunicação com a ECU, o estado do veículo e a comunicação de eventos.

Geral:
- ECU: separar a camada de transmissão do protocolo. Handshake é apenas o #D50, o restante deve ser feito sob demanda através do estado;
- Estado: deve ser o intermediário/meio de campo entre a conversa com a ECU <> UI/Componentes internos. Ele quem controla se irá obter dados da ECU e é ele quem envia os dados para ECU, sendo o ponto central de comunicação;
- Eventos: exceto eventos de tela, tudo deve passar pelo EventBus, permitindo que qualquer parte do projeto se inscreva para receber uma notificação de algo que ocorreu;

Eventos:
- ECU: emite eventos estruturados tanto dos envios quanto recebimentos;
- SignalProcessor: recebe os eventos da ECU, os converte e publica o seu próprio evento;
- Estado: avaliar a necessidade de publicar eventos de alteração de estado;
- UI: apenas eventos internos de pysignal, não passa pelo EventBus;
- UI: pode se inscrever no event bus.