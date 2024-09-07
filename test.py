import logging
import os
import pandas as pd
from azure.cosmos import CosmosClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import json
import base64

# TESTE LOCAL

# Carregar variáveis de ambiente do arquivo .env (para testes locais)
load_dotenv()

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

    # Salvar o gráfico como PNG localmente
    plt.savefig('relatorio_grafico.png')
    plt.close()

# Função para enviar e-mail com anexo
def enviar_email():
    try:
        # Configurações do e-mail obtidas das variáveis de ambiente
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
        filename = 'relatorio_grafico.png'
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

# Função para corrigir padding em strings base64
def base64_decode(data):
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data)
    except Exception as e:
        logging.error(f"Erro ao decodificar base64: {str(e)}")
        return None

# Função principal para obter dados do CosmosDB e enviar o relatório
def report_sent():
    logging.info('Iniciando a execução da função para obter dados do CosmosDB.')

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

        # Log dos itens obtidos
        logging.info(f"Itens do CosmosDB: {json.dumps(items, indent=4)}")

        # Verificar e processar cada item
        data = []
        for item in items:
            try:
                # Verificar se os campos essenciais existem e são válidos
                if 'dataHoraUTC' in item and 'temperatura' in item and 'umidade' in item:
                    # Verificar se algum campo é codificado em base64 (se aplicável)
                    logging.info(f"Processando item: {item}")
                    data.append({
                        'dataHoraUTC': item['dataHoraUTC'],
                        'temperatura': item['temperatura'],
                        'umidade': item['umidade']
                    })
                else:
                    logging.warning(f"Dados incompletos ou inválidos: {item}")
            except Exception as e:
                logging.error(f"Erro ao processar item: {str(e)}")
                logging.error(f"Item problemático: {item}")

        if not data:
            logging.info("Nenhum dado válido encontrado após filtragem.")
            return

        df = pd.DataFrame(data)
        logging.info(f"Dados recuperados e tratados: {df}")

        # Gerar gráfico a partir dos dados
        gerar_grafico(df)

        # Enviar relatório por e-mail
        enviar_email()

    except Exception as e:
        logging.error(f"Erro ao processar a solicitação: {str(e)}")
        logging.error(f"Erro detalhado: {str(e)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report_sent()
