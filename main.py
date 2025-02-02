from flask import Flask, request, render_template_string, redirect
import paramiko
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from io import StringIO
import requests
import os

app = Flask(__name__)

# Конфигурация Linode
LINODE_API_KEY = "ваш_api_ключ_linode"  # Замените на ваш API-ключ Linode
LINODE_INSTANCE_ID = "ваш_id_сервера"  # Замените на ID вашего сервера Linode
LINODE_USERNAME = "ваш_username"  # Замените на имя пользователя на сервере Linode

# HTML-шаблон для отображения формы
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSH Key Generator and Linode Login</title>
</head>
<body>
    <h1>Генерация SSH-ключа и подключение к Linode</h1>
    <form method="post">
        <input type="submit" name="generate" value="Сгенерировать SSH-ключи">
        <input type="submit" name="connect" value="Подключиться к Linode">
    </form>
    {% if private_key %}
    <h3>Приватный ключ:</h3>
    <textarea rows="10" cols="50">{{ private_key }}</textarea>
    {% endif %}
    {% if public_key %}
    <h3>Публичный ключ:</h3>
    <textarea rows="10" cols="50">{{ public_key }}</textarea>
    {% endif %}
    {% if error %}
    <h2 style="color: red;">Ошибка: {{ error }}</h2>
    {% endif %}
</body>
</html>
'''

def generate_ssh_keys():
    """Генерация SSH-ключей."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    ).decode('utf-8')

    return private_pem, public_key

def add_public_key_to_linode(public_key):
    """Добавление публичного ключа на сервер Linode."""
    url = f"https://api.linode.com/v4/linode/instances/{LINODE_INSTANCE_ID}/sshkeys"
    headers = {
        "Authorization": f"Bearer {LINODE_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "label": "Generated SSH Key",
        "ssh_key": public_key,
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Ошибка добавления ключа на Linode: {response.text}")

@app.route('/', methods=['GET', 'POST'])
def index():
    private_key = None
    public_key = None
    error = None

    if request.method == 'POST':
        if 'generate' in request.form:
            # Генерация SSH-ключей
            private_key, public_key = generate_ssh_keys()

        elif 'connect' in request.form:
            # Подключение к Linode
            private_key = request.form.get('private_key')
            if not private_key:
                error = "Приватный ключ не найден. Сначала сгенерируйте ключи."
            else:
                try:
                    # Добавление публичного ключа на Linode
                    public_key = request.form.get('public_key')
                    add_public_key_to_linode(public_key)

                    # Подключение к серверу Linode
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    private_key_obj = paramiko.RSAKey.from_private_key(StringIO(private_key))

                    # Получаем IP-адрес сервера Linode
                    url = f"https://api.linode.com/v4/linode/instances/{LINODE_INSTANCE_ID}"
                    headers = {"Authorization": f"Bearer {LINODE_API_KEY}"}
                    response = requests.get(url, headers=headers)
                    if response.status_code != 200:
                        raise Exception(f"Ошибка получения информации о сервере: {response.text}")
                    linode_ip = response.json()["ipv4"][0]

                    # Подключаемся к серверу
                    ssh.connect(linode_ip, username=LINODE_USERNAME, pkey=private_key_obj, timeout=10)
                    ssh.close()

                    # Перенаправляем на YouTube, если подключение успешно
                    return redirect("https://www.youtube.com")

                except Exception as e:
                    error = f"Ошибка: {str(e)}"

    return render_template_string(HTML, private_key=private_key, public_key=public_key, error=error)

if name == '__main__':
    app.run(debug=True)
