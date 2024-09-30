from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
import base64
import json

HOST = input("insert server IP: ")
PORT = 8000
SERVER = (HOST, PORT)

# Configuração do servidor
conn = socket(AF_INET, SOCK_STREAM)

conn.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
conn.bind(('0.0.0.0', PORT)) # listen on all interfaces
conn.listen(5)

with open("polichat_logo.png", "rb") as image_file:
   BASE64_IMAGE = base64.b64encode(image_file.read()).decode('utf-8')

with open("mouse.gif", "rb") as gif_file:
    CUTE_MOUSE = base64.b64encode(gif_file.read()).decode('utf-8')

print(f'Servidor ouvindo em {HOST}:{PORT}')

state = {'messages':['Admin:  Bem-vindo ao PoliChat!'], 
         'people': {'Admin': {'password': 'Admin', 'ip': HOST}}, 
         'blocked_users': set({})}

tcp_clients = []
running = True

js = '''
document.getElementById('chatForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('http://''' + HOST + ':' + str(PORT) + '''/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: document.getElementById('chatInput').value })
    })
    .then(r => r.json())
    .then(d => { console.log('Success:', d); setTimeout(() => document.location.reload(), 10) })
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
    .then(d => { console.log('Success:', d); setTimeout(() => document.location.reload(), 10) })
    .catch(err => console.error('Error:', err));
    document.getElementById('reportInput').value = '';
};
'''

def build_response(req, addr, state):

    ip, port = addr
    method = req.splitlines()[0].split()[0]
    route = req.splitlines()[0].split()[1]
    body = req.splitlines()[-1]
    auth = ''.join(filter(lambda s: 'Authorization' in s, req.splitlines()))
    unauthorized = 'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic\r\n\r\n {}\n'.encode('utf-8')

    rendered_messages = '\n'.join([f'<li>{x}</li>' for x in state['messages']])

    print('state', state)

    if len(auth) == 0:
        return unauthorized
    
    creds = base64.b64decode(auth.split(' ')[2]).decode('utf-8')
    user = creds.split(':')[0] 
    password = creds.split(':')[1] 

    if user in state['people']:
        if user in state['blocked_users']:
            return unauthorized
        if state['people'][user]['password'] != password:
            return unauthorized
        if state['people'][user]['ip'] != ip:
            return unauthorized
    else:
        state['people'][user] = {'password': password, 'ip': ip}


    if method == 'POST' and route == '/message':
        msg = json.loads(body)
        state['messages'].append(f"{user}: {msg['message']}")

        return 'HTTP/1.1 200 OK\r\nContent-type: application/json\r\n\r\n {}\n'.encode('utf-8')

    if method == 'POST' and route == '/ban':
        msg = json.loads(body)
        user2ban = msg['user']
        print('ban?', user2ban)
        if not (user2ban in state['blocked_users']) and user == 'Admin':
            state['blocked_users'].add(user2ban)

        return 'HTTP/1.1 200 OK\r\nContent-type: application/json\r\n\r\n {}\n'.encode('utf-8')

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
            background-color: #007bff;
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
    <script>{js}</script>
</body>
</html>

    \r\n\r\n
    '''.encode('utf-8')


def response(client, address):
    try:
        msg = client.recv(2048).decode()
        print(msg)

        response = build_response(msg, address, state)
        client.sendall(response)
        client.close()

    except Exception as e:
        print(f'Erro com o cliente: {e}')

def listen_for_tcp_clients():
    try:
        while True:
            client, address = conn.accept()
            print(f'Cliente {address} conectado')
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