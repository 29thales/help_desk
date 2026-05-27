import os
import smtplib
import imaplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid


def _config_email():
    smtp_server = os.getenv("SMTP_SERVER", "").strip()
    smtp_port_str = os.getenv("SMTP_PORT", "587").strip()
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()

    if not smtp_server:
        raise ValueError("SMTP_SERVER nao configurado no .env")
    if not sender_email:
        raise ValueError("SENDER_EMAIL nao configurado no .env")
    if not sender_password:
        raise ValueError("SENDER_PASSWORD nao configurado no .env (use senha de app do Gmail)")

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        raise ValueError(f"SMTP_PORT invalido: {smtp_port_str}")

    return {
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "sender_email": sender_email,
        "sender_password": sender_password,
    }


def _salvar_em_enviados_imap(config, mensagem_bytes):
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(config["sender_email"], config["sender_password"])
        for pasta in ['"[Gmail]/Enviados"', '"[Gmail]/Sent Mail"']:
            try:
                imap.append(pasta, '\\Seen', imaplib.Time2Internaldate(time.time()), mensagem_bytes)
                break
            except Exception:
                continue
        imap.logout()
    except Exception as e:
        print(f"Aviso: nao foi possivel salvar em Enviados do Gmail: {e}")


def enviar_email_faturamento(destinatario, assunto, corpo, pdf_bytes, nome_arquivo_pdf, nome_remetente="RNS TECH"):
    try:
        config = _config_email()
    except ValueError as e:
        return False, f"Configuracao de email invalida: {e}"

    msg = MIMEMultipart()
    msg["From"] = f"{nome_remetente} <{config['sender_email']}>"
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    corpo_html = corpo.replace("\n", "<br/>")
    corpo_completo_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; font-size: 14px; color: #243447; line-height: 1.6;">
            {corpo_html}
        </body>
    </html>
    """
    msg.attach(MIMEText(corpo, "plain", "utf-8"))
    msg.attach(MIMEText(corpo_completo_html, "html", "utf-8"))

    if pdf_bytes:
        anexo = MIMEApplication(pdf_bytes, _subtype="pdf")
        anexo.add_header("Content-Disposition", "attachment", filename=nome_arquivo_pdf)
        msg.attach(anexo)

    try:
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=30) as servidor:
            servidor.starttls()
            servidor.login(config["sender_email"], config["sender_password"])
            servidor.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Falha de autenticacao no Gmail. Verifique se: "
            "(1) Autenticacao de 2 fatores esta ativa, "
            "(2) SENDER_PASSWORD eh senha de app (16 chars), "
            "(3) SENDER_EMAIL bate com a conta da senha de app"
        )
    except smtplib.SMTPRecipientsRefused:
        return False, f"Destinatario recusado: {destinatario}"
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro inesperado ao enviar email: {e}"

    _salvar_em_enviados_imap(config, msg.as_bytes())
    return True, f"Email enviado com sucesso para {destinatario}"


def _formatar_moeda(valor):
    valor = float(valor or 0)
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def montar_template_faturamento(detalhe_cliente):
    nome = detalhe_cliente.get("nome") or "Cliente"
    empresa = detalhe_cliente.get("empresa") or nome
    mes = detalhe_cliente.get("mes")
    ano = detalhe_cliente.get("ano")
    qtd = detalhe_cliente.get("quantidade_chamados", 0)
    total = detalhe_cliente.get("total_faturado", 0)

    assunto = f"Faturamento {empresa} - {mes:02d}/{ano} - RNS TECH"

    corpo = (
        f"Ola {nome},\n\n"
        f"Segue em anexo o relatorio de faturamento referente a competencia {mes:02d}/{ano}.\n\n"
        f"Resumo:\n"
        f"- Chamados finalizados: {qtd}\n"
        f"- Total apurado: {_formatar_moeda(total)}\n\n"
        f"Em caso de duvidas, estamos a disposicao.\n\n"
        f"Atenciosamente,\n"
        f"RNS TECH"
    )

    return {"assunto": assunto, "corpo": corpo}
