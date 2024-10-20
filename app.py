from flask import Flask, render_template, request, redirect, url_for, session, flash
import pyrebase
import json
from helpers import *
import firebase_admin
from firebase_admin import auth as admin_auth
from firebase_admin import credentials, initialize_app
from dotenv import load_dotenv
import os
from datetime import datetime

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')

# Credenciais do e-mail
sender_email= os.getenv('SENDER_EMAIL')
password = os.getenv('EMAIL_PASSWORD')

# Configuração do Firebase
with open('firebase_config.json') as f:
    firebase_config = json.load(f)

firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()  # Serviço de autenticação
db = firebase.database()

# Inicialização do Firebase Admin SDK
cred = credentials.Certificate('reservasacvoc-7a064-firebase-adminsdk-z9vad-3f191ac22b.json')  # Certificado do Firebase Admin
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Função de auditoria
def registrar_auditoria_reserva(acao, reserva, user_id):
    """
    Registra ações de auditoria no Firebase para operações com reservas.
    :param acao: Tipo de ação realizada (criação, edição, exclusão)
    :param reserva: Detalhes da reserva
    :param user_id: ID do usuário que fez a alteração
    """
    db = firebase.database()  # Acessar o banco de dados

    # Buscar as informações do usuário que fez a ação
    user_info = db.child("users").child(user_id).get().val()
    usuario = user_info.get('apelido', 'Desconhecido')

    # Dados do log de auditoria
    log = {
        "usuario": usuario,
        "user_id": user_id,
        "acao": acao,
        "detalhes_reserva": reserva,
        "data_hora": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Armazenar o log na coleção "auditoria_reservas"
    db.child("auditoria_reservas").push(log)

# Rota para página inicial protegida (somente usuários logados)
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    reservas = db.child("reservas").get().val()
    user_id = session['user_id']
    user_role = session.get('role', 'user')  # Pega o papel do usuário (admin ou user)

    # Mapear cores para todas as reservas (tanto passadas quanto futuras)
    todas_reservas = {}
    if reservas:
        todas_reservas = {
            key: {
                **reserva,  # Manter todos os dados da reserva
                'cor': get_reserva_color(reserva['tipo_reserva'])  # Adicionar a cor baseada no tipo de reserva
            }
            for key, reserva in reservas.items()  # Aqui mapeamos TODAS as reservas
        }


    # Data e hora atuais
    hoje = datetime.now().date()

    # Reservas filtradas (apenas do usuário logado se não for admin)
    reservas_filtradas = {}
    if reservas:
        reservas_filtradas = {key: reserva for key, reserva in reservas.items() 
                              if reserva.get('user_id') == user_id 
                              and datetime.strptime(reserva['data'], '%Y-%m-%d').date() >= hoje
                              }
    
    # Filtrar apenas reservas de hoje em diante (para admins)
    reservas_futuras = {}
    if user_role == 'admin' and reservas:
        reservas_futuras = {
            key: reserva for key, reserva in reservas.items()
            if datetime.strptime(reserva['data'], '%Y-%m-%d').date() >= hoje
        }

    return render_template('home.html', reservas_filtradas=reservas_filtradas, todas_reservas=todas_reservas, reservas_futuras=reservas_futuras, user_role=user_role)

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user_id'] = user['localId']
            session['email'] = email

            
            user_info = db.child("users").child(user['localId']).get().val()

            if user_info:  # Verifica se encontrou as informações do usuário
                session['apelido'] = user_info.get('apelido', 'Usuário')  # Salva o apelido na sessão
            else:
                session['apelido'] = 'Usuário'
            
            # Verificar se é admin
            if user_info and user_info.get('role') == 'admin':
                session['role'] = 'admin'
            else:
                session['role'] = 'user'

            return redirect(url_for('home'))
        except:
            flash("Login inválido. Verifique suas credenciais.")
            return redirect(url_for('login'))
    
    return render_template('login.html')


    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # admin ou user
        apelido = request.form['apelido']  # Novo campo para apelido

        try:
            # Criar o usuário no Firebase Auth
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']

            # Gerar ID sequencial
            contador_ref = db.child("contador_usuarios").get().val() or 0
            novo_id = contador_ref + 1  # Incrementa o contador

            # Atualizar o contador no banco de dados
            db.child("contador_usuarios").set(novo_id)

            # Salvar o papel do usuário (admin ou user) e o apelido no banco de dados
            db.child("users").child(user_id).set({
                "email": email,
                "role": role,
                "apelido": apelido,  # Armazena o apelido
                "id_sequencial": novo_id  # Armazena o ID sequencial gerado
            })

            flash("Usuário registrado com sucesso. Faça login.")
            return redirect(url_for('login'))
        except:
            flash("Erro no registro. Tente novamente.")
            return redirect(url_for('register'))

    return render_template('register.html')

# Rota de logout
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Limpa a sessão do usuário
    return redirect(url_for('login'))

# Rota para adicionar nova reserva (somente usuários logados)
@app.route('/nova-reserva', methods=['POST'])
def nova_reserva():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.form['data']
    hora_inicio = request.form['hora_inicio']
    hora_fim = request.form['hora_fim']
    tipo_reserva = request.form['tipo_reserva']  # Capturar o tipo de reserva
    user_id = session['user_id']  # Pega o ID do usuário logado

    # Buscar todas as reservas existentes
    reservas_existentes = db.child("reservas").get().val()

    # Verificar se há conflito de horário com as reservas existentes
    if reservas_existentes and verifica_conflito(data, hora_inicio, hora_fim, tipo_reserva, reservas_existentes):
        flash("RESERVA NÃO SALVA: Conflito de horário! Já existe uma reserva nesse horário, para a quadra, ou nesse dia, para o caso das churrasqueiras e do salão.")
        return redirect(url_for('home'))

    # Verificar se a hora de término é maior que a hora de início
    if hora_fim <= hora_inicio:
        flash("RESERVA NÃO SALVA: A hora de término deve ser maior que a hora de início.")
        return redirect(url_for('home'))

    # Verificar se é churrasqueiras ou salão de festas
    if tipo_reserva in ['ch_piscina', 'ch_estac', 'salao']:
        # Redirecionar para a página de checklist antes de confirmar a reserva
        return redirect(url_for('confirmar_reserva', data=data, hora_inicio=hora_inicio, hora_fim=hora_fim, tipo_reserva=tipo_reserva))

    # Se não for churrasqueira ou salão, salvar diretamente
    criar_reserva(data, hora_inicio, hora_fim, tipo_reserva, user_id)
    
    return redirect(url_for('home'))

# Função para salvar a reserva
def criar_reserva(data, hora_inicio, hora_fim, tipo_reserva, user_id):
    
    # Buscar o apelido do usuário no banco de dados
    user_info = db.child("users").child(user_id).get().val()
    apelido = user_info.get('apelido', 'Sem Apelido')
    receiver_email = user_info.get('email')  # Pegar o e-mail do usuário

    # Criar a nova reserva
    nova_reserva = {
        "nome": apelido,
        "data": data,
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "tipo_reserva": tipo_reserva,
        "user_id": user_id
    }

    # Adicionar a reserva ao banco de dados
    db.child("reservas").push(nova_reserva)

    # Registrar a ação de criação na auditoria
    registrar_auditoria_reserva("criação", nova_reserva, user_id)

    # Enviar o e-mail de confirmação
    sender_email = os.getenv('SENDER_EMAIL')  # Carregar o e-mail remetente das variáveis de ambiente
    #email_password = os.getenv('EMAIL_PASSWORD')  # Carregar a senha do e-mail das variáveis de ambiente
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))

    conteudo = f"""
    Olá {nova_reserva['nome']},
    
    Sua reserva foi confirmada com sucesso. Aqui estão os detalhes da sua reserva:

    - Tipo de Reserva: {nova_reserva['tipo_reserva'].capitalize()}
    - Data: {nova_reserva['data']}
    - Horário: {nova_reserva['hora_inicio']} às {nova_reserva['hora_fim']}

    Obrigado por usar nosso sistema!
    """

    subject = "Confirmação de Reserva - ACVOC"
    enviar_email(sender_email, receiver_email, conteudo, subject, sg)

    flash("Reserva confirmada com sucesso! Um e-mail de confirmação foi enviado.")

@app.route('/confirmar-reserva')
def confirmar_reserva():
    data = request.args.get('data')
    hora_inicio = request.args.get('hora_inicio')
    hora_fim = request.args.get('hora_fim')
    tipo_reserva = request.args.get('tipo_reserva')

    return render_template('confirmar_reserva.html', data=data, hora_inicio=hora_inicio, hora_fim=hora_fim, tipo_reserva=tipo_reserva)

# Rota para processar a confirmação
@app.route('/confirmar-reserva', methods=['POST'])
def processar_confirmacao():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Coletar dados do formulário
    data = request.form['data']
    hora_inicio = request.form['hora_inicio']
    hora_fim = request.form['hora_fim']
    tipo_reserva = request.form['tipo_reserva']
    user_id = session['user_id']

    # Verificar se todas as checkboxes foram marcadas
    if 'confirmacao_1' not in request.form or 'confirmacao_2' not in request.form or 'confirmacao_3' not in request.form:
        flash("Você deve confirmar todas as condições antes de concluir a reserva.")
        return redirect(url_for('confirmar_reserva', data=data, hora_inicio=hora_inicio, hora_fim=hora_fim, tipo_reserva=tipo_reserva))

    # Criar a reserva
    criar_reserva(data, hora_inicio, hora_fim, tipo_reserva, user_id)

    flash("Reserva confirmada com sucesso!")
    return redirect(url_for('home'))

# Rota para remover reserva
@app.route('/remover-reserva/<id>', methods=['POST'])
def remover_reserva(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Obter as informações da reserva antes de removê-la
    reserva = db.child("reservas").child(id).get().val()

    if not reserva:
        flash("Reserva não encontrada.")
        return redirect(url_for('home'))

    # Buscar as informações do usuário que criou a reserva
    user_id = reserva.get('user_id')
    user_info = db.child("users").child(user_id).get().val()
    receiver_email = user_info.get('email')  # E-mail do usuário

    # Configurar o conteúdo do e-mail de cancelamento
    conteudo = f"""
    Olá {reserva['nome']},
    
    Sua reserva foi cancelada. Aqui estão os detalhes da reserva cancelada:

    - Tipo de Reserva: {reserva['tipo_reserva'].capitalize()}
    - Data: {reserva['data']}
    - Horário: {reserva['hora_inicio']} às {reserva['hora_fim']}

    Se precisar de mais informações, entre em contato conosco.

    Obrigado por usar nosso sistema!
    """

    # Enviar o e-mail de cancelamento
    sender_email = os.getenv('SENDER_EMAIL')  # E-mail remetente
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))  # SendGrid API Client
    subject = "Cancelamento de Reserva - ACVOC"
    enviar_email(sender_email, receiver_email, conteudo, subject, sg)

    # Remover a reserva do banco de dados
    db.child("reservas").child(id).remove()

    # Registrar a ação de criação na auditoria
    registrar_auditoria_reserva("exclusão", reserva, session['user_id'])

    flash("Reserva removida com sucesso. Um e-mail de cancelamento foi enviado.")
    return redirect(url_for('home'))

# Rota para alterar a senha
@app.route('/alterar-senha', methods=['GET', 'POST'])
def alterar_senha():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        senha_atual = request.form['senha_atual']
        nova_senha = request.form['nova_senha']
        confirmar_nova_senha = request.form['confirmar_nova_senha']
        email = session['email']

        # Verificar se a nova senha e a confirmação são iguais
        if nova_senha != confirmar_nova_senha:
            flash("A nova senha e a confirmação não coincidem.")
            return redirect(url_for('alterar_senha'))

        try:
            # Reautenticar o usuário com a senha atual
            user = auth.sign_in_with_email_and_password(email, senha_atual)

            # Atualizar a senha do usuário com o Firebase Admin SDK
            admin_auth.update_user(user['localId'], password=nova_senha)
            
            flash("Senha alterada com sucesso!")
            return redirect(url_for('home'))

        except Exception as e:
            flash("Erro ao alterar a senha: " + str(e))
            return redirect(url_for('alterar_senha'))

    return render_template('alterar_senha.html')

# Rota para gerir usuários (apenas admins)
@app.route('/gerir-usuarios', methods=['GET', 'POST'])
def gerir_usuarios():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['role'] != 'admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Verificar se a ação é criar um novo usuário ou redefinir senha
        if 'email_novo' in request.form:
            # Criar novo usuário com senha padrão
            email_novo = request.form['email_novo']
            apelido_novo = request.form['apelido_novo']
            try:
                # Criar novo usuário no Firebase com a senha padrão
                user = admin_auth.create_user(
                    email=email_novo,
                    password="acvoc2024",
                )

                # Armazenar as informações adicionais no banco de dados
                db.child("users").child(user.uid).set({
                    "email": email_novo,
                    "apelido": apelido_novo,
                    "role": "user"
                })

                flash(f"Usuário {email_novo} criado com sucesso!")
            except Exception as e:
                flash(f"Erro ao criar o usuário: {str(e)}")
            return redirect(url_for('gerir_usuarios'))
        # Verificar se a ação é para redefinir senha e/ou atualizar o papel
        if 'email_redefinir' in request.form:
            email_redefinir = request.form['email_redefinir']
            novo_role = request.form.get('role_atualizar')  # Novo papel, se fornecido
            novo_apelido = request.form.get('apelido_atualizar')  # Pegar o novo apelido, se fornecido

            try:
                # Buscar o usuário pelo e-mail
                user = admin_auth.get_user_by_email(email_redefinir)

                # Redefinir a senha se a opção de redefinir for selecionada
                if request.form.get('redefinir_senha') == 'on':
                    admin_auth.update_user(user.uid, password="acvoc2024")
                    flash(f"Senha do usuário {email_redefinir} redefinida para a senha padrão.")

                # Atualizar o papel do usuário, se fornecido
                if novo_role:
                    db.child("users").child(user.uid).update({"role": novo_role})
                    flash(f"Papel do usuário {email_redefinir} atualizado para {novo_role}.")

                # Atualizar o apelido do usuário, se fornecido
                if novo_apelido:
                    db.child("users").child(user.uid).update({"apelido": novo_apelido})
                    flash(f"Apelido do usuário {email_redefinir} atualizado para {novo_apelido}.")

            except Exception as e:
                flash(f"Erro ao processar a solicitação: {str(e)}")
            return redirect(url_for('gerir_usuarios'))

    # Carregar a lista de usuários existentes para exibição na página
    usuarios = db.child("users").get().val()

    return render_template('gerir_usuarios.html', usuarios=usuarios)

# Rota para excluir um usuário (apenas admins)
@app.route('/excluir-usuario/<uid>', methods=['POST'])
def excluir_usuario(uid):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    try:
        # Excluir o usuário do Firebase Authentication
        admin_auth.delete_user(uid)
        
        # Remover o usuário do Realtime Database
        db.child("users").child(uid).remove()

        flash("Usuário excluído com sucesso!")
    except Exception as e:
        flash(f"Erro ao excluir o usuário: {str(e)}")

    return redirect(url_for('gerir_usuarios'))

@app.route('/reservas-futuras')
def reservas_futuras():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    # Busque as reservas futuras de todos os usuários
    hoje = datetime.now().date()
    reservas = db.child("reservas").get().val()

    reservas_futuras = {}
    if reservas:
        reservas_futuras = {
            key: reserva for key, reserva in reservas.items()
            if datetime.strptime(reserva['data'], '%Y-%m-%d').date() >= hoje
        }

    return render_template('reservas_futuras.html', reservas_futuras=reservas_futuras)

@app.route('/modelos')
def modelos():
    return render_template('modelos.html')

@app.route('/instalacoes')
def instalacoes():
    # Lista de instalações com os nomes e os caminhos das imagens
    instalacoes = [
        {"nome": "Quadra de Tênis", "imagem": "tenis.jpg"},
        {"nome": "Quadra Poliesportiva", "imagem": "poliesportiva.jpg"},
        {"nome": "Salão de Festas", "imagem": "salao.jpg"},
        {"nome": "Churrasqueira da Piscina", "imagem": "ch_piscina.jpg"},
        {"nome": "Churrasqueira do Estacionamento", "imagem": "ch_estac.jpg"},
    ]

    return render_template('instalacoes.html', instalacoes=instalacoes)

@app.context_processor
def inject_today_date():
    return {'date_today': datetime.now().strftime('%Y-%m-%d')}

if __name__ == '__main__':
    app.run(debug=True)