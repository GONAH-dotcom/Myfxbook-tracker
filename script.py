import os
import requests
import csv
from datetime import datetime

# 1. Get credentials securely from your GitHub Secrets
email = os.environ.get("MYFXBOOK_EMAIL")
password = os.environ.get("MYFXBOOK_PASSWORD")

# 2. Correct Myfxbook API Login URL
login_url = f"https://www.myfxbook.com/api/login.json?email={email}&password={password}"

try:
    print("Attempting to log into Myfxbook...")
    response = requests.get(login_url)
    login_data = response.json()

    # Check if login gave us a valid session
    if "session" in login_data and login_data.get("error") in [False, "false", "False"]:
        session_token = login_data["session"]
        print("Login successful! Fetching sentiment data...")

        # 3. Correct Community Outlook (Sentiment) URL
        data_url = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session_token}"
        sentiment_data = requests.get(data_url).json()

        # Extract the list of symbols
        symbols_list = sentiment_data.get("symbols", [])

        if symbols_list:
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"sentiment_{today}.csv"

            # 4. Process data into standard CSV rows cleanly
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
        else:
            print("Error: Myfxbook sent back an empty list of symbols.")

    else:
        print(f"Login Failed. Myfxbook API said: {login_data.get('message', 'Unknown Error')}")
        print("Please check your GitHub Secrets — email and password may have typos.")

except Exception as e:
    print(f"An unexpected system error occurred: {e}")
