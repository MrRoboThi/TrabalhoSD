# TrabalhoMulticast

Esse código é referente ao trabalho prático da Disciplina Fundamentos de Sistemas Distribuídos da Universidade Federal da Bahia, semestre 2025.1

Como usar o script:
Para fazer o teste é necessário abrir janelas de terminal referentes a quantidade de processos que serão testados. A forma de utilização do script será: python multicast.py {Processo ativado (referente ao número de processos -1)} {Número de processos}

Digamos que o teste seja feito com 3 processos ativos, então a aplicação deve ser aberta em 3 terminais iniciando o processo da seguinte forma: 
Terminal 1: python multicast.py 0 3 / Terminal 2: python multicast.py 1 3 / Terminal 3: python multicast.py 2 3
Feito isso, você pode enviar uma mensagem que será recebida pelos outros processos. Caso uma mensagem seja enviada, porém não haja a quantidade correta de processos ativos, haverá a tentativa de retransmissão.

Arquitetura do sistema:
O sistema é composto por N processos. Cada processo possui um ID que vai de 0 a N-1 e conhece o endereço de todos os outros processos no sistema. Essa informação é fornecida no momento da inicialização.

O sistema implementa um reliable multicast sobre uma rede de processos distribuídos em python. Os processos são autonomos e idênticos em sua funcionalidade, sem um coordenador central. 

O multicast é simulado em nível de aplicação. Quando o processo é enviado deseja enviar uma mensagem multicast, ele itera sobre a lista de outros processos e envia uma cópia da mensagem para cada um deles. 

Arquitetura:

1- Multicast:
A comunicação é feita via socket UDP. Ele não é um protocolo confiável por padrão já que os pacotes podem se perder durante o envio, então é feita uma sanitização para permitir que haja uma entrega confiável das mensagens.

A confiabilidade para alcançar o reliable multicast é feita a partir de confirmação de recebimento (ACK), assim quando um processo Nx recebe uma mensagem de uma processo Ny, ele envia de volta uma mensagem de confirmação(ACK) para Ny, assim o remetente sabe que a mensagem foi entregue com sucesso. Além disso há a utilização de pending_acks que registram as mensagens enviadas que aguardam confirmação.

Caso os ACKs não sejam recebidos de volta durante um certo período de tempo(timeout), é utilizada uma thread de retransmissão para verificar os pending_acks e retransmitir a mensagem que expirou. Por exemplo, caso um processo Ny envie uma mensagem para Nx, porém o processo Nx não esteja ativo, caso o timeout tenha expirado a mensagem é reenviada para garantir o recebimento.

Para garantir que as mensagens não sejam duplicadas(Já que o ACK pode ter se perdido graças a falta de confiabilidade do protocolo UDP, ou de alguma forma seja feita uma retransmissão desnecessária) é utilizado uma estrutura para detectar as duplicatas. Se uma duplicata chegar ela é ignorada, porém um novo ACK é enviado para caso o ACK anterior tenha se perdido.

2- Relógio lógico:
O sistema usa o relógio de lamport para implementar a ordem causal dos eventos, com cada processo mantendo um contador lógico.

Antes de enviar uma mensagem um processo incrementa o valor do relógio atual +1

A mensagem é enviada com o valor atualizado do relógio.

Quando o processo recebe uma mensagem, ele também atualiza seu próprio relógio com +1, levando em consideração o relógio da mensagem enviada. Ou seja, se evento A causa evento B, B será incrementado de forma em que seja maior que o A após sua atualização. Assim, A será menor que B.

O relógio não é incrementado com uma retransmissão. Então se por exemplo a mensagem tenha sido retransmitida pelo processo Ny com valor de relógio 1, ele mantém o valor que possui caso os outros processos não estejam ativos. Isso garante uma causalidade eficiente dos eventos identificando o timestamp original.

As mensagens carregam timestamp de tempo real.

Imagem do funcionamento e explicação:
![Multicast](https://github.com/user-attachments/assets/c38a9703-b88a-4ef7-b54b-0116b5c6ee3c)

Como explicado no começo desse documento, foram abertos três terminais para verificar a quantidade mínima de processos ativos e funcionais (3). 

1- Processo 0 começa enviando uma mensagem para ambos os processos ativos. Porém eles são ativados apenas após o envio inicial, fazendo que haja uma retransmissão. Assim que um dos processos(2) é ativado, ele mantém a tentativa de transmissão apenas para o processo inativo(1) até que ambos sejam ativados e o envio seja finalizado. Daí é enviada a mensagem que contém a timestamp e o relógio atualizado para os processos(LC=1 após o envio do processo 1, e LC=2 para todos os processos após recebimento). 

2- O mesmo é feito com o processo 2. Porém como todos os processos estão ativos não há necessidade de retransmissão. É possível verificar que o relógio é novamente atualizado para o LC=3 após o envio. Quando as mensagens são recebidas, todos os processos são atualizados para o timestamp 4.

3- Por último é feito o teste com o processo 1. Ele é incrementado para o timestamp 5 e após todos os processos receberem a mensagem, todos são incrementados para timestamp 6.

Com isso, é verificada a ordem causal de cada processo.
