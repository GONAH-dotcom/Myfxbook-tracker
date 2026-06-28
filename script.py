import os
import requests
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

email = os.environ.get("MYFXBOOK_EMAIL")
password = os.environ.get("MYFXBOOK_PASSWORD")
gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
gmail_user = "gonahcharo1993@gmail.com"

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = gmail_user
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, gmail_user, msg.as_string())
        server.quit()
        print("Email notification sent!")
    except Exception as e:
        print(f"Email failed: {e}")

login_url = f"https://www.myfxbook.com/api/login.json?email={email}&password={password}"

try:
    print("Attempting to log into Myfxbook...")
    response = requests.get(login_url)
    login_data = response.json()

    if "session" in login_data and login_data.get("error") in [False, "false", "False"]:
        session_token = login_data["session"]
        print("Login successful! Fetching sentiment data...")

        data_url = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session_token}"
        sentiment_data = requests.get(data_url).json()

        symbols_list = sentiment_data.get("symbols", [])

        if symbols_list:
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            hour = now.strftime("%H")
            filename = f"sentiment_{today}_{hour}00.csv"

            headers = [
                "date", "name", "shortPercentage", "longPercentage",
                "shortVolume", "longVolume", "longPositions",
                "shortPositions", "totalPositions"
            ]

            with open(filename, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()

                for item in symbols_list:
                    row_data = {"date": today}
                    row_data.update(item)
                    writer.writerow(row_data)

            print(f"Success! Saved data to {filename}")

            # Find extreme sentiment pairs
            extreme = []
            for item in symbols_list:
                short = float(item.get("shortPercentage", 0))
                long = float(item.get("longPercentage", 0))
                name = item.get("name", "")
                if short >= 75:
                    extreme.append(f"🔴 {name}: {short}% Short → FADE LONG")
                elif long >= 75:
                    extreme.append(f"🔴 {name}: {long}% Long → FADE SHORT")

            # Build email
            subject = f"🤖 FX Sentiment Update — {today} {hour}00 UTC"
            if extreme:
                body = f"Extreme Sentiment Pairs:\n\n" + "\n".join(extreme)
                body += f"\n\n✅ CSV saved: {filename}"
            else:
                body = f"No extreme sentiment pairs at this time.\n\n✅ CSV saved: {filename}"

            send_email(subject, body)

        else:
            print("Error: Myfxbook sent back an empty list of symbols.")
            send_email("❌ FX Bot Error", "Myfxbook returned empty symbols list.")

    else:
        print(f"Login Failed. Myfxbook API said: {login_data.get('message', 'Unknown Error')}")
        send_email("❌ FX Bot Login Failed", "Check your Myfxbook credentials in GitHub Secrets.")

except Exception as e:
    print(f"An unexpected system error occurred: {e}")
    send_email("❌ FX Bot Error", f"Unexpected error: {e}")
