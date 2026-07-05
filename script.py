# script.py â€” Myfxbook Sentiment Bot
# Updated: 2026-07-04
# Runs every 4 hours Mon-Fri
# Fetches retail sentiment from Myfxbook
# Sends email alerts for extreme pairs (>=75%)
# All times in New York (NY) time

import os
import requests
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

email          = os.environ.get("MYFXBOOK_EMAIL")
password       = os.environ.get("MYFXBOOK_PASSWORD")
gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
gmail_user     = "gonahcharo1993@gmail.com"

NY_UTC_OFFSET  = 4   # EDT: UTC-4. Change to 5 for EST (Nov-Mar)

def utc_to_ny(utc_dt):
    return utc_dt - timedelta(hours=NY_UTC_OFFSET)

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From']    = gmail_user
        msg['To']      = gmail_user
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
    response   = requests.get(login_url)
    login_data = response.json()

    if "session" in login_data and login_data.get("error") in [False, "false", "False"]:
        session_token = login_data["session"]
        print("Login successful! Fetching sentiment data...")

        data_url       = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session_token}"
        sentiment_data = requests.get(data_url).json()
        symbols_list   = sentiment_data.get("symbols", [])

        if symbols_list:
            now_utc  = datetime.now(timezone.utc)
            now_ny   = utc_to_ny(now_utc)
            today_ny = now_ny.strftime("%Y-%m-%d")
            time_ny  = now_ny.strftime("%I:%M%p")
            hour_ny  = now_ny.strftime("%I%p").lower()
            filename = f"sentiment_{today_ny}_{hour_ny}_NY.csv"

            headers = [
                "date_NY", "time_NY", "name",
                "shortPercentage", "longPercentage",
                "shortVolume", "longVolume",
                "longPositions", "shortPositions", "totalPositions"
            ]

            with open(filename, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                for item in symbols_list:
                    row = {"date_NY": today_ny, "time_NY": time_ny}
                    row.update(item)
                    writer.writerow(row)

            print(f"Success! Saved data to {filename}")

            # Find extreme sentiment pairs (>=75%) â€” contrarian signals
            extreme = []
            for item in symbols_list:
                short = float(item.get("shortPercentage", 0))
                long  = float(item.get("longPercentage",  0))
                name  = item.get("name", "")
                if short >= 75:
                    extreme.append(f"FADE LONG  | {name}: {short}% Short -> BUY")
                elif long >= 75:
                    extreme.append(f"FADE SHORT | {name}: {long}% Long  -> SELL")

            subject = f"FX Sentiment Update -- {today_ny} {time_ny} NY"
            if extreme:
                body  = f"Extreme Sentiment Pairs (>=75% threshold):\n\n"
                body += "\n".join(extreme)
                body += f"\n\nReminder: Fade the crowd â€” trade OPPOSITE direction!\n"
                body += f"\nCSV saved: {filename}"
            else:
                body  = f"No extreme sentiment pairs at this time.\n"
                body += f"All pairs below 75% threshold â€” no contrarian signal.\n"
                body += f"\nCSV saved: {filename}"

            send_email(subject, body)

        else:
            print("Error: Myfxbook returned empty symbols list.")
            send_email("FX Sentiment Error",
                       "Myfxbook returned empty symbols list. Check API status.")

    else:
        msg = login_data.get('message', 'Unknown Error')
        print(f"Login Failed: {msg}")
        send_email("FX Sentiment Login Failed",
                   f"Login failed: {msg}\nCheck GitHub Secrets for MYFXBOOK_EMAIL and MYFXBOOK_PASSWORD.")

except Exception as e:
    print(f"Unexpected error: {e}")
    send_email("FX Sentiment Error", f"Unexpected error: {e}")
