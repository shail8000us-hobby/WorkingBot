#!/usr/bin/env python3
import os, sys, argparse, ssl, smtplib, mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text    import MIMEText
from email.mime.base    import MIMEBase
from email              import encoders

def envs(k, d=""):
    v=os.getenv(k)
    return v if v not in (None,"") else d

def load_dotenv_if_present():
    try:
        from dotenv import load_dotenv
        for fname in (".env",".env.reports"):
            if os.path.exists(fname):
                load_dotenv(fname, override=True)
    except Exception:
        pass

def attach_file(msg, path):
    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    with open(path, 'rb') as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(path)}"')
        msg.attach(part)

def send_email(file_path, to_list):
    server = envs("SMTP_SERVER","smtp.gmail.com")
    port   = int(envs("SMTP_PORT","465"))
    user   = envs("SENDER_EMAIL")
    pwd    = envs("SENDER_PASSWORD")
    if not (server and port and user and pwd):
        raise SystemExit("Missing SMTP_SERVER/SMTP_PORT/SENDER_EMAIL/SENDER_PASSWORD in env")

    subj = f"Delta PnL Report — {os.path.basename(file_path)}"
    body = "Automated report attached.\n\nSent by tools/send_report.py"
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To']   = ", ".join(to_list)
    msg['Subject'] = subj
    msg.attach(MIMEText(body, 'plain'))
    attach_file(msg, file_path)

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(server, port, context=ctx) as s:
            s.login(user, pwd)
            s.sendmail(user, to_list, msg.as_string())
    else:
        with smtplib.SMTP(server, port) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            s.login(user, pwd)
            s.sendmail(user, to_list, msg.as_string())
    print(f"[ok] email sent → {to_list} ({server}:{port})")

def main():
    load_dotenv_if_present()
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--to", nargs="+", default=[])
    args = ap.parse_args()
    if not os.path.isfile(args.file):
        raise SystemExit(f"file not found: {args.file}")
    to_env = [x.strip() for x in (envs("EMAIL_TO") or envs("SENDER_EMAIL")).split(",") if x.strip()]
    to_list = args.to if args.to else to_env
    if not to_list:
        raise SystemExit("no recipient: pass --to or set EMAIL_TO/SENDER_EMAIL")
    send_email(args.file, to_list)

if __name__ == "__main__":
    main()
