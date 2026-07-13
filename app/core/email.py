import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_reset_code_email(to_email: str, reset_code: str):
    sender_email = settings.SMTP_USER
    sender_password = settings.SMTP_PASSWORD.replace(" ", "") if settings.SMTP_PASSWORD else None
    
    if not sender_email or not sender_password:
        print("SMTP_USER or SMTP_PASSWORD not configured. Cannot send email.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Mã xác nhận Đặt lại Mật khẩu - AI Meeting"
    message["From"] = f"AI Meeting <{sender_email}>"
    message["To"] = to_email

    text = f"Mã xác nhận của bạn là: {reset_code}\nMã này sẽ hết hạn trong vòng 15 phút."
    html = f"""\
    <html>
      <body>
        <h2>Đặt lại mật khẩu</h2>
        <p>Mã xác nhận của bạn là: <strong style="font-size: 24px; color: #4F46E5;">{reset_code}</strong></p>
        <p>Mã này sẽ hết hạn trong vòng 15 phút. Vui lòng không chia sẻ mã này với bất kỳ ai.</p>
        <br>
        <p>Trân trọng,<br>Đội ngũ AI Meeting</p>
      </body>
    </html>
    """

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    message.attach(part1)
    message.attach(part2)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_verification_email(to_email: str, verification_code: str):
    sender_email = settings.SMTP_USER
    sender_password = settings.SMTP_PASSWORD.replace(" ", "") if settings.SMTP_PASSWORD else None
    
    if not sender_email or not sender_password:
        print("SMTP_USER or SMTP_PASSWORD not configured. Cannot send email.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Xác nhận địa chỉ Email - AI Meeting"
    message["From"] = f"AI Meeting <{sender_email}>"
    message["To"] = to_email

    text = f"Mã xác nhận email của bạn là: {verification_code}\nMã này sẽ hết hạn trong vòng 15 phút."
    html = f"""\
    <html>
      <body>
        <h2>Xác nhận địa chỉ Email</h2>
        <p>Cảm ơn bạn đã đăng ký tài khoản. Mã xác nhận của bạn là: <strong style="font-size: 24px; color: #4F46E5;">{verification_code}</strong></p>
        <p>Mã này sẽ hết hạn trong vòng 15 phút. Vui lòng nhập mã này trên trang web để hoàn tất đăng ký.</p>
        <br>
        <p>Trân trọng,<br>Đội ngũ AI Meeting</p>
      </body>
    </html>
    """

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    message.attach(part1)
    message.attach(part2)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
