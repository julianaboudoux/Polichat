from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
import base64
import json

# Definimos o IP (inserido pelo usuário) e a porta.
HOST = input("insert server IP: ")
PORT = 8000
SERVER = (HOST, PORT)

# Cria um socket TCP
conn = socket(AF_INET, SOCK_STREAM)
# Permite a reutilização do endereço após o socket ser fechado.
conn.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
# Liga o socket a todas as interfaces de rede disponíveis no servidor, escutando na porta especificada.
conn.bind(('0.0.0.0', PORT)) 
# Coloca o socket em modo de escuta, permitindo até 5 conexões simultâneas.
conn.listen(5)

# Codificamos imagens que serão utilizadas
with open("polichat_logo.png", "rb") as image_file:
   BASE64_IMAGE = base64.b64encode(image_file.read()).decode('utf-8')
with open("side-image.png", "rb") as image_file:
   SIDE_IMAGE= base64.b64encode(image_file.read()).decode('utf-8')
with open("mouse.gif", "rb") as gif_file:
    CUTE_MOUSE = base64.b64encode(gif_file.read()).decode('utf-8')

print(f'Servidor ouvindo em {HOST}:{PORT}')

# Aqui definimos o estado inicial do servidor.
state = {'messages':['Admin:  Bem-vindo ao PoliChat!'], 
         'people': {'Admin': {'password': 'Admin', 'ip': HOST}}, 
         'blocked_users': set({})}

# Lista para armazenar as conexões de clientes.
tcp_clients = []
running = True

# fetch() faz um POST para a URL http://[HOST]:[PORT]/message. Essa URL é usada pelo servidor para processar novas mensagens. 
# then() o primeiro converte a resposta para JSON e o segundo exibe um log de sucesso.
# Após o envio da mensagem, o campo de entrada do chat (chatInput) é limpo.
js = '''
document.getElementById('chatForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('http://''' + HOST + ':' + str(PORT) + '''/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: document.getElementById('chatInput').value })
    })
    .then(r => r.json())
    .then(d => { console.log('Success:', d); setTimeout(() => document.location.reload(), 15) })
    .catch(err => console.error('Error:', err));
    document.getElementById('chatInput').value = '';
};

document.getElementById('reportForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('http://''' + HOST + ':' + str(PORT) + '''/ban', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: document.getElementById('reportInput').value })
    })
    .then(r => r.json())
    .then(d => { console.log('Success:', d); setTimeout(() => document.location.reload(), 15) })
    .catch(err => console.error('Error:', err));
    document.getElementById('reportInput').value = '';
};
'''
# Parte responsável por construir a resposta ao cliente com base na requisição HTTP.
# Valida se o usuário está autenticado, lida com mensagens e banimentos
def build_response(req, addr, state):
# Obtemos o método, a rota e o body da requisição.
    ip, port = addr
    method = req.splitlines()[0].split()[0]
    route = req.splitlines()[0].split()[1]
    body = req.splitlines()[-1]
    # Filtra as linhas da requisição que contêm o cabeçalho Authorization.
    auth = ''.join(filter(lambda s: 'Authorization' in s, req.splitlines()))
    # Prepara a mensagem de erro HTTP 401 para clientes não autorizados, pedindo autenticação.
    unauthorized = 'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic\r\n\r\n {}\n'.encode('utf-8')
    #: Transforma a lista de mensagens armazenadas no estado do servidor em uma lista HTML para exibição no front-end .
    rendered_messages = '\n'.join([f'<li>{x}</li>' for x in state['messages']])

    print('state', state)
    # Se a requisição não contém o cabeçalho de autenticação, o servidor responde com o status 401 Unauthorized.
    if len(auth) == 0:
        return unauthorized
    # Decodifica as credenciais enviadas no cabeçalho de autenticação, que estão no formato Base64.
    creds = base64.b64decode(auth.split(' ')[2]).decode('utf-8')
    # Após a decodificação, separa o nome de usuário da senha, que estão no formato username:password.
    user = creds.split(':')[0] 
    password = creds.split(':')[1] 

    # Verifica se o usuário já está registrado no dicionário state['people']
    if user in state['people']:
        # Se o usuário está na lista de usuários bloqueados, retorna o erro 401.
        if user in state['blocked_users']:
            return unauthorized
        # Se a senha enviada não corresponde à senha armazenada, retorna o erro 401 Unauthorized.
        if state['people'][user]['password'] != password:
            return unauthorized
        # Se o IP atual do cliente for diferente do registrado no estado, o acesso é negado.
        if state['people'][user]['ip'] != ip:
            return unauthorized
    else:
        # Usuário é adicionado.
        state['people'][user] = {'password': password, 'ip': ip}

    # Se o request for POST com a rota /message:
    # O corpo da requisição é decodificado de JSON para um dicionário Python.
    # A mensagem enviada pelo usuário é adicionada à lista de mensagens do estado.
    # Retorna um código HTTP 200 OK para o cliente, indicando que a mensagem foi processada com sucesso.
    if method == 'POST' and route == '/message':
        msg = json.loads(body)
        state['messages'].append(f"{user}: {msg['message']}")

        return 'HTTP/1.1 200 OK\r\nContent-type: application/json\r\n\r\n {}\n'.encode('utf-8')

    # Se o request for POST com a rota /ban:
    if method == 'POST' and route == '/ban':
        msg = json.loads(body) # Decodifica o corpo da requisição JSON.
        user2ban = msg['user'] # Extrai o nome do usuário a ser banido.
        print('ban?', user2ban)
        #Verifica se o usuário a ser banido ainda não está na lista de bloqueados e se a solicitação foi feita pelo admin.
        if not (user2ban in state['blocked_users']) and user == 'Admin':
            state['blocked_users'].add(user2ban)

        return 'HTTP/1.1 200 OK\r\nContent-type: application/json\r\n\r\n {}\n'.encode('utf-8')
    # Se a rota não for /message ou /ban, o servidor responde com uma página HTML.
    # O HTML inclui também imagens carregadas em formato Base64 e um script JS.
    return f'''HTTP/1.1 200 OK\r\nContent-type: text/html\r\r\n
<!DOCTYPE html>
<head>
<meta http-equiv="refresh" content="5">
    <title>PolyChat</title>
    <style>
        body {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #000000;
        }}
        .container {{
            text-align: center;
            background-color: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            width: 60%;
            max-width: 600px;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        #img2 {{
            max-width: 20%;
            height: auto;
        }}
        ul {{
            list-style-type: none;
            padding: 0;
        }}
        li {{
            margin: 5px 0;
        }}
        input[type="text"] {{
            padding: 10px;
            width: 80%;
            border-radius: 5px;
            border: 1px solid #ccc;
            margin: 10px 0;
        }}
        button {{
            padding: 10px 15px;
            border-radius: 5px;
            background-color: #123993;
            color: white;
            border: none;
            cursor: pointer;
        }}
        button:hover {{
            background-color: #0056b3;
        }}
    </style>
</head>
<body>
    <div class="column">
        <img src="data:image/png;base64,{SIDE_IMAGE}" alt="Left Image">
    </div>

    <div class="container">
        <img src="data:image/png;base64,{BASE64_IMAGE}" alt="PolyChat Logo">
        <ul>{rendered_messages}</ul>
        <form id="chatForm">
            <input type="text" id="chatInput" placeholder="Digite sua mensagem." required>
            <button type="submit">Enviar</button>
        </form>
        <form id="reportForm">
            <input type="text" id="reportInput" placeholder="Quem deve ser banido?" required>
            <button type="s12ubmit">Banir</button>
        </form>
        <img id="img2" src="data:image/gif;base64,{CUTE_MOUSE}" alt="Mouse GIF"> 
    </div>
    <div class="column">
        <img src="data:image/png;base64,{SIDE_IMAGE}" alt="Right Image">
    </div>
    <script>{js}</script>
</body>
</html>

    \r\n\r\n
    '''.encode('utf-8')

# Lida com a comunicação entre o servidor e um cliente
# client representa a conexão socket estabelecida com o cliente.
# address contém o endereço IP e a porta do cliente conectado.
def response(client, address):
    try:
        # Recebe até 2048 bytes de dados do cliente. Decodifica os dados recebidos de bytes para uma string.
        msg = client.recv(2048).decode()
        print(msg)
        # Chama a função build_response, que processa a mensagem recebida e gera uma resposta HTTP apropriada.
        response = build_response(msg, address, state)
        client.sendall(response)
        # Envia a resposta gerada pela função build_response de volta para o cliente.
        client.close()

    except Exception as e:
        print(f'Erro com o cliente: {e}')

#  Aceita conexões de clientes no servidor e criar uma nova thread para cada cliente que se conecta,
def listen_for_tcp_clients():
    try:
        while True:
            # conn.accept() aguarda até que um cliente tente se conectar ao servidor
            client, address = conn.accept()
            print(f'Cliente {address} conectado')
            # Cria uma nova thread para lidar com o cliente. 
            # A função response será chamada nessa thread, passando como argumentos o socket do cliente e seu endereço.
            # daemon significa que ela será automaticamente encerrada quando o programa principal terminar.
            Thread(target=response, args=[client, address], daemon=True).start()
    except Exception as e:
        print(f"Erro ao aceitar conexão: {e}")
        global running
        running = False

Thread(target=listen_for_tcp_clients, daemon=True).start()

try:
    while running:
        pass
except KeyboardInterrupt:
    print("Servidor sendo encerrado")