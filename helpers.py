#from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
#import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email


def enviar_email(sender_email,receiver_email, conteudo, assunto, sg):
   

    # Criar o objeto de e-mail
    message = Mail(
        from_email=sender_email,  # E-mail remetente verificado no SendGrid
        to_emails=[receiver_email, sender_email],  # E-mail do destinatário
        subject=assunto,
        plain_text_content=conteudo
    )

    try:
        # Enviar o e-mail via SendGrid
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f"E-mail enviado com sucesso! Status code: {response.status_code}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Função para verificar conflito de horário
def verifica_conflito(data, hora_inicio_nova, hora_fim_nova, tipo_reserva_nova, user_id_nova, reservas):
    for reserva in reservas.values():
        # Verifica se a reserva é no mesmo dia
        if reserva['data'] == data:
            hora_inicio_existente = reserva['hora_inicio']
            hora_fim_existente = reserva['hora_fim']
            
            # Restrições específicas para churrasqueiras e salão de festas
            if tipo_reserva_nova in ['ch_piscina', 'ch_estac', 'salao']:
                # Se já houver uma reserva do mesmo tipo no mesmo dia, impede a nova reserva
                if reserva['tipo_reserva'] == tipo_reserva_nova:
                    return True  # Conflito: uma reserva por dia nesses tipos

           # Verificar se a mesma pessoa está reservando tanto para churrasqueira da pisina quanto para salão de festas e
            # verificar se a mesma pessoa está reservando tanto para churrasqueira da piscina quanto a churrasqueira do estacionamento
            if reserva['user_id'] == user_id_nova and user_id_nova != 'D12PCNwgz9WmNFafMwtnFlzwvNb2':
                if reserva['tipo_reserva'] in ['salao', 'ch_estac'] and tipo_reserva_nova == 'ch_piscina':
                    return True  # Conflito: mesma pessoa reservando paraa salão ou churrasq estac e churrasqueira da piscina
                elif reserva['tipo_reserva'] == 'ch_piscina' and tipo_reserva_nova in ['salao', 'ch_estac']:
                    return True  # Conflito: mesma pessoa reservando para churrasqueira da piscina e salão ou churrasqueira do estacionamento

            # Verificar conflito de horário para outras instalações (quadras, etc.)
            if reserva['tipo_reserva'] == tipo_reserva_nova:
                # Verifica se os horários se sobrepõem
                if (hora_inicio_nova < hora_fim_existente) and (hora_fim_nova > hora_inicio_existente):
                    return True  # Conflito de horário
    return False

# Mapeia as cores de fundo do calendário de acordo com o tipo de reserva
def get_reserva_color(tipo_reserva):
    cores = {
        'tenis': '#90EE90',  # Verde claro
        'poliesportiva': '#FACACA',  # Vermelho claro
        'salao': '#F0CCA1',  # Amarelo claro
        'ch_piscina': '#ADD8E6',  # Azul claro
        'ch_estac': '#D3D3D3'  # Cinza claro
    }
    return cores.get(tipo_reserva, '#FFFFFF')  # Branco (default)

