from flask import Flask, jsonify, request, abort
import psycopg2
from psycopg2 import Error
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import os
from dotenv import find_dotenv, load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Find .env file
dotenv_path = find_dotenv()

# Load up the entries as environments variables
load_dotenv(dotenv_path)

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')  # Use uma chave secreta forte
app.config['JWT_EXPIRATION_DELTA'] = False
jwt = JWTManager(app)
CORS(app, resources={r"/*": {"origins": os.getenv("ORIGINS")}})

# Configuração da conexão com o PostgreSQL
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

def send_email(subject, message):
    from_email = os.getenv('EMAIL_USER')
    from_password = os.getenv('EMAIL_PASS')
    to_email = os.getenv('TO_EMAIL_USER')

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Rota para autenticação e obtenção de token
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    # Verifique as credenciais
    if username != os.getenv("SECRET_USER") or password != os.getenv("SECRET_PASS"):
        return jsonify({"msg": "Credenciais inválidas"}), 401

    # Crie um token de acesso
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

# Rota protegida que requer token
@app.route('/produtos', methods=['GET'])
@jwt_required()
def listar_produtos():
    # Só pode acessar se tiver um token válido
    current_user = get_jwt_identity()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lista_de_presentes;")
    produtos = cursor.fetchall()
    cursor.close()

    produtos_json = []
    for produto in produtos:
        produto_dict = {
            'id': produto[0],
            'categoria': produto[1],
            'nome': produto[2],
            'descricao': produto[3],
            'valor': float(produto[4]),
            'link_compra': produto[5],
            'comprado': produto[6]
        }
        produtos_json.append(produto_dict)

    return jsonify(produtos_json)

@app.route('/produtos/<int:id>', methods=['GET'])
@jwt_required()
def obter_produto_por_id(id):
    current_user = get_jwt_identity()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lista_de_presentes WHERE id = %s;", (id,))
    produto = cursor.fetchone()  # Retorna apenas um produto correspondente ao ID

    if not produto:
        abort(404, f'Produto com ID {id} não encontrado.')

    produto_dict = {
        'id': produto[0],
        'categoria': produto[1],
        'nome': produto[2],
        'descricao': produto[3],
        'valor': float(produto[4]),
        'link_compra': produto[5],
        'comprado': produto[6]
    }

    cursor.close()
    return jsonify(produto_dict), 200

@app.route('/produtos', methods=['POST'])
@jwt_required()
def criar_produto():
    current_user = get_jwt_identity()
    try:
        dados = request.json
        if 'nome' not in dados or 'descricao' not in dados or 'valor' not in dados or 'link_compra' not in dados:
            abort(400, 'Dados incompletos para criar o produto.')

        id = dados['id']
        categoria = dados['categoria']
        nome = dados['nome']
        descricao = dados['descricao']
        valor = dados['valor']
        link_compra = dados['link_compra']

        cursor = conn.cursor()
        cursor.execute("INSERT INTO lista_de_presentes (nome, descricao, valor, link_compra) VALUES (%s, %s, %s, %s)", (id, categoria, nome, descricao, valor, link_compra))
        conn.commit()
        cursor.close()

        return 'Produto criado com sucesso!', 201
    except Error as e:
        conn.rollback()  # Reverte transação em caso de erro
        abort(500, f'Erro ao criar o produto: {str(e)}')

@app.route('/produtos/<int:id>', methods=['PUT'])
@jwt_required()
def atualizar_produto(id):
    current_user = get_jwt_identity()
    try:
        # Obter o valor de 'comprado' da requisição JSON
        comprado = request.json.get('comprado')
        
        # Validar se 'comprado' é um valor booleano
        if comprado is None or not isinstance(comprado, bool):
            return jsonify({'error': 'O campo "comprado" é inválido'}), 400
        
        # Atualizar o campo 'comprado' do produto com o ID fornecido
        cursor = conn.cursor()
        cursor.execute("UPDATE lista_de_presentes SET comprado = %s WHERE id = %s", (comprado, id))
        conn.commit()
        cursor.close()

        return jsonify({'message': 'Produto atualizado com sucesso'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/produtos/<int:id>', methods=['DELETE'])
@jwt_required()
def deletar_produto(id):
    current_user = get_jwt_identity()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lista_de_presentes WHERE id = %s", (id,))
    conn.commit()
    cursor.close()

    return 'Produto deletado com sucesso!', 200

@app.route('/send-email', methods=['POST'])
@jwt_required()
def enviar_email():
    current_user = get_jwt_identity()
    try:
        dados = request.json
        if 'nome_usuario' not in dados or 'nome_produto' not in dados:
            abort(400, 'Dados incompletos para enviar o email.')

        nome_usuario = dados['nome_usuario']
        nome_produto = dados['nome_produto']

        subject = "Confirmação de Compra"
        message = f"Compra do produto {nome_produto} foi confirmada por {nome_usuario}."
        
        send_email(subject, message)

        return jsonify({'message': 'Email enviado com sucesso'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run()