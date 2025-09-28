#from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
#import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email
from datetime import datetime, timedelta


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
        hora_inicio_existente = reserva['hora_inicio']
        hora_fim_existente = reserva['hora_fim']
        usuario_existente = reserva['user_id']
        # Verifica se a reserva é no mesmo dia
        if reserva['data'] == data:
            # Restrições específicas para churrasqueiras e salão de festas
            if tipo_reserva_nova in ['ch_piscina', 'ch_estac', 'salao', 'pergolado']:
                # Se já houver uma reserva do mesmo tipo no mesmo dia, impede a nova reserva
                if reserva['tipo_reserva'] == tipo_reserva_nova:
                    return True  # Conflito: uma reserva por dia nesses tipos
                
            # Impede combinações proibidas
                if user_id_nova == usuario_existente and user_id_nova != 'D12PCNwgz9WmNFafMwtnFlzwvNb2':
                    # Conflitos entre ch_piscina, salao, ch_estac e pergolado
                    pares_proibidos = [
                        ('ch_piscina', 'salao'),
                        ('salao', 'ch_piscina'),
                        ('ch_piscina', 'ch_estac'),
                        ('ch_estac', 'ch_piscina'),
                        ('ch_piscina', 'pergolado'),
                        ('pergolado', 'ch_piscina'),
                        ('salao', 'pergolado'),
                        ('pergolado', 'salao'),
                        ('ch_estac', 'pergolado'),
                        ('pergolado', 'ch_estac'),
                    ]
                    if (reserva['tipo_reserva'], tipo_reserva_nova) in pares_proibidos:
                        return True
                

            # Verificar conflito de horário para outras instalações (quadras, etc.)
            if reserva['tipo_reserva'] == tipo_reserva_nova:
                # Verifica se os horários se sobrepõem
                if (hora_inicio_nova < hora_fim_existente) and (hora_fim_nova > hora_inicio_existente):
                    return True  # Conflito de horário

        # Bloquear mesma instalação no D-1 ou D+1
        data_existente = datetime.strptime(reserva['data'], "%Y-%m-%d").date()
        data_nova = datetime.strptime(data, "%Y-%m-%d").date()

        if user_id_nova == usuario_existente and user_id_nova != 'D12PCNwgz9WmNFafMwtnFlzwvNb2':
            print('Heyeey')
            if tipo_reserva_nova in ['pergolado', 'ch_piscina', 'ch_estac', 'salao']:
                if reserva['tipo_reserva'] == tipo_reserva_nova:
                    print('Mesmo tipo')
                    diferenca_dias = abs((data_existente - data_nova).days)
                    if diferenca_dias == 1:  # D-1 ou D+1
                        return True  # Conflito

    return False

# Mapeia as cores de fundo do calendário de acordo com o tipo de reserva
def get_reserva_color(tipo_reserva):
    cores = {
        'tenis': '#90EE90',  # Verde claro
        'poliesportiva': '#FACACA',  # Vermelho claro
        'salao': '#F0CCA1',  # Amarelo claro
        'ch_piscina': '#ADD8E6',  # Azul claro
        'ch_estac': '#D3D3D3',  # Cinza claro
        'pergolado': '#ee3b3b'
    }
    return cores.get(tipo_reserva, '#FFFFFF')  # Branco (default)
    

