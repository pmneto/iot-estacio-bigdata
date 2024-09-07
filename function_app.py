import logging
import azure.functions as func  # Import necessário para Azure Functions
import os
import json
import pandas as pd
from azure.cosmos import CosmosClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import matplotlib.pyplot as plt

app = func.FunctionApp()

# Função para gerar e salvar o gráfico
def gerar_grafico(df):
    plt.figure(figsize=(10, 5))
    plt.plot(df['dataHoraUTC'], df['temperatura'], label='Temperatura (C)', color='orange')
    plt.plot(df['dataHoraUTC'], df['umidade'], label='Umidade (%)', color='blue')
    plt.xlabel('Data/Hora')
    plt.ylabel('Valores')
    plt.title('Relatório de Temperatura e Umidade')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Salvar o gráfico como PNG
    plt.savefig('/tmp/relatorio_grafico.png')
    plt.close()

# Função para enviar e-mail com anexo
def enviar_email():
    try:
        # Configurações do e-mail (Gmail como exemplo)
        email_host = os.getenv('SMTP_SERVER')
        email_host_port = int(os.getenv('SMTP_PORT'))
        sender_email = os.getenv('SMTP_USER')
        receiver_email = os.getenv('EMAIL_RECIPIENT')
        email_password = os.getenv('SMTP_PASSWORD')

        # Criação do objeto MIMEMultipart para o e-mail
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = 'Relatório de Temperatura e Umidade - Diário'

        # Corpo do e-mail
        body = 'Segue em anexo o relatório de temperatura e umidade diário.'
        msg.attach(MIMEText(body, 'plain'))

        # Anexar o gráfico gerado
        filename = '/tmp/relatorio_grafico.png'
        attachment = open(filename, 'rb')

        part = MIMEBase('application', 'octet-stream')
        part.set_payload((attachment).read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', "attachment; filename= relatorio_grafico.png")

        msg.attach(part)

        # Conectar ao servidor SMTP
        server = smtplib.SMTP(email_host, email_host_port)
        server.starttls()
        server.login(sender_email, email_password)

        # Enviar e-mail
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()

        logging.info("E-mail enviado com sucesso!")

    except Exception as e:
        logging.error(f"Erro ao enviar e-mail: {str(e)}")

# Função disparada por trigger de tempo
@app.schedule(schedule="0 8 * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False)
def report_sent(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')

    try:
        # Obter as variáveis de ambiente para o Cosmos DB
        cosmos_url = os.getenv('COSMOS_DB_URL')
        cosmos_key = os.getenv('COSMOS_DB_KEY')
        database_name = os.getenv('COSMOS_DB_DATABASE_NAME', 'TemperaturaUmidadeDB')
        container_name = os.getenv('COSMOS_DB_CONTAINER_NAME', 'Leituras')

        # Criar cliente CosmosDB
        client = CosmosClient(cosmos_url, credential=cosmos_key)
        database = client.get_database_client(database_name)
        container = database.get_container_client(container_name)

        # Executar a consulta para obter todos os dados
        query = "SELECT * FROM c"
        items = list(container.query_items(query, enable_cross_partition_query=True))

        if not items:
            logging.info("Nenhum dado encontrado no CosmosDB.")
            return

        # Criar um DataFrame para tratar os dados
        df = pd.DataFrame(items)
        df['dataHoraUTC'] = df['dataHoraUTC'].dt.tz_convert('America/Sao_Paulo')
        
        logging.info(f"Dados recuperados: {df}")

        # Gerar gráfico a partir dos dados
        gerar_grafico(df)

        # Enviar relatório por e-mail
        enviar_email()

    except Exception as e:
        logging.error(f"Erro ao processar a solicitação: {str(e)}")
