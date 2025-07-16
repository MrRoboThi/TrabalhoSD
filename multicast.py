import socket
import threading
import json
import sys
import time
import uuid
from datetime import datetime

# Configurações de confiabilidade UDP
RETRANSMISSION_TIMEOUT = 2.0  
RETRANSMISSION_INTERVAL = 0.5 

# Lock para acesso seguro a recursos compartilhados entre threads
lock = threading.Lock()

# Estado do processo
process_id = -1
peers = {}
lamport_clock = 0

# Estruturas para Confiabilidade UDP
pending_acks = {}
received_messages_history = set()

# Funções de Rede UDP

def send_udp_message(target_id, message_data):
    """Envia uma mensagem UDP para um destino específico."""
    target_host, target_port = peers[target_id]
    
    # Cria um socket UDP
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        message_bytes = json.dumps(message_data).encode('utf-8')
        udp_socket.sendto(message_bytes, (target_host, target_port))
    except Exception as e:
        with lock:
            print(f"[ERRO] Falha ao enviar UDP para {target_id}: {e}")
    finally:
        udp_socket.close()

# Tratamento de Mensagens

def handle_ack(message):
    """Processa um ACK recebido, removendo a pendência de confirmação."""
    ack_sender_id = message['sender_id']
    acked_message_id = message['payload'] 

    with lock:
        if acked_message_id in pending_acks:
            if ack_sender_id in pending_acks[acked_message_id]['acks_needed']:
                pending_acks[acked_message_id]['acks_needed'].remove(ack_sender_id)
                
                if not pending_acks[acked_message_id]['acks_needed']:
                    del pending_acks[acked_message_id]
                    # print(f"[DEBUG] Todos os ACKs recebidos para {acked_message_id[:8]}")

def handle_message(message, sender_addr):
    #Processa uma mensagem de dados recebida.
    global lamport_clock
    
    message_id = message['message_id']
    sender_id = message['sender_id']

    send_ack(sender_id, message_id)

    # Detecção de Duplicatas
    with lock:
        if message_id in received_messages_history:
            # print(f"[DEBUG] Mensagem duplicada recebida de {sender_id}. Ignorando.")
            return 

        received_clock = message['lamport_clock']
        lamport_clock = max(lamport_clock, received_clock) + 1
        
        
        received_messages_history.add(message_id)

        print(f"\n--- Mensagem Recebida [LC: {lamport_clock}] ---")
        print(f"  De: Processo {sender_id}")
        print(f"  Conteúdo: '{message['payload']}'")
        print(f"  ID: {message_id[:8]}...")
        print(f"  Timestamp de Lamport (Remetente): {message['lamport_clock']}")
        print(f"--------------------------------------")
        print(f"\n[Processo {process_id}] Digite sua mensagem: ", end="", flush=True)

def send_ack(target_id, original_message_id):
    #Envia um ACK para confirmar o recebimento de uma mensagem.
    ack_message = {
        "type": "ACK",
        "sender_id": process_id,
        "payload": original_message_id, 
    }
    send_udp_message(target_id, ack_message)

# Threads de Execução

def listener_thread_func():
    #Escuta por mensagens UDP 
    my_host, my_port = peers[process_id]
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((my_host, my_port))

    # print(f"[Processo {process_id}] Escutando UDP em {my_host}:{my_port}")

    while True:
        try:
            data, addr = server_socket.recvfrom(4096) 
            if data:
                message = json.loads(data.decode('utf-8'))
                
                if message['type'] == 'MESSAGE':
                    handle_message(message, addr)
                elif message['type'] == 'ACK':
                    handle_ack(message)
        except Exception as e:
            print(f"[ERRO Listener] {e}")


def retransmission_thread_func():
    
    #Verifica periodicamente as mensagens pendentes e as retransmite se o timeout ocorrer. Aqui será verificado a confiabilidade.
    
    while True:
        time.sleep(RETRANSMISSION_INTERVAL)
        now = time.time()
        
        with lock:
            pending_ids = list(pending_acks.keys())
        
        for msg_id in pending_ids:
            with lock:

                if msg_id not in pending_acks:
                    continue
                
                pending = pending_acks[msg_id]

            if now - pending['last_sent'] > RETRANSMISSION_TIMEOUT:
                with lock:
                    print(f"\n[RETRANSMISSÃO] Timeout para msg {msg_id[:8]}... Reenviando para {pending['acks_needed']}")
                    print(f"\n[Processo {process_id}] Digite sua mensagem: ", end="", flush=True)

                for peer_id in pending['acks_needed']:
                    send_udp_message(peer_id, pending['message'])
                
                with lock:
                    if msg_id in pending_acks: 
                         pending_acks[msg_id]['last_sent'] = now

# Envia uma reliable multicast para todos os outros processos

def multicast(payload):
    
    global lamport_clock

    # Lista de processos que devem confirmar o recebimento
    acks_needed = set(peers.keys())
    acks_needed.discard(process_id) 

    if not acks_needed:
        print("Nenhum outro processo na rede para enviar.")
        return

    with lock:
        # Lógica do Relógio de Lamport (Envio)
        lamport_clock += 1
        
        message_id = str(uuid.uuid4())
        message = {
            "type": "MESSAGE",
            "sender_id": process_id,
            "payload": payload,
            "message_id": message_id,
            "lamport_clock": lamport_clock,
            "wall_clock": datetime.now().isoformat()
        }

        # Registra a mensagem como pendente de ACKs antes de enviar
        pending_acks[message_id] = {
            'message': message,
            'acks_needed': acks_needed.copy(),
            'last_sent': time.time()
        }
        
        print(f"\n--- Enviando Multicast [LC: {lamport_clock}] ---")
        print(f"  Conteúdo: '{payload}' | ID: {message_id[:8]}...")
        print(f"------------------------------------")

    # Envio inicial para todos os peers
    for peer_id in acks_needed:
        send_udp_message(peer_id, message)

def main():
    global process_id, total_processes, peers

    if len(sys.argv) != 3:
        print("Uso: python processo_udp.py <ID_DO_PROCESSO> <N_TOTAL_DE_PROCESSOS>")
        sys.exit(1)

    process_id = int(sys.argv[1])
    total_processes = int(sys.argv[2])
    BASE_PORT = 9000 
    
    for i in range(total_processes):
        peers[i] = ('localhost', BASE_PORT + i)

    # Inicia a thread de escuta
    listener = threading.Thread(target=listener_thread_func, daemon=True)
    listener.start()

    # Inicia a thread de retransmissão
    retransmitter = threading.Thread(target=retransmission_thread_func, daemon=True)
    retransmitter.start()

    print(f"[Processo {process_id}] Online (UDP Confiável). N={total_processes}.")
    time.sleep(1)

    # Loop principal para envio de mensagem
    while True:
        try:
            message_payload = input(f"[Processo {process_id}] Digite sua mensagem: ")
            if message_payload:
                multicast(message_payload)
        except KeyboardInterrupt:
            print(f"\n[Processo {process_id}] Encerrando...")
            sys.exit(0)

if __name__ == "__main__":
    main()