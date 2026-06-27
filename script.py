
import os
import requests
import csv
from datetime import datetime

# 1. Get your safe credentials from GitHub Secrets
email = os.environ.get("MYFXBOOK_EMAIL")
password = os.environ.get("MYFXBOOK_PASSWORD")

# 2. Ask Myfxbook for a connection token
login_url = f"https://myfxbook.com{email}&password={password}"
response = requests.get(login_url).json()

if response.get("error") == "false" or "session" in response:
    session_token = response["session"]
    
    # 3. Request the community sentiment data
    data_url = f"https://myfxbook.com{session_token}"
    sentiment_data = requests.get(data_url).json()
    
    # Myfxbook data is usually nested inside a 'symbols' list
    symbols_list = sentiment_data.get("symbols", [])
    
    # 4. Create today's CSV file
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"sentiment_{today}.csv"
    
    if symbols_list:
        # Get headers dynamically from the first item (e.g., shortPercentage, longPercentage)
        headers = ["date"] + list(symbols_list[0].keys())
        
        with open(filename, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            
            for row in symbols_list:
                row["date"] = today  # Add the date stamp to every row
                writer.writerow(row)
                
        print(f"Successfully saved CSV historical data to {filename}")
    else:
        print("No symbol data found in the Myfxbook response.")
else:
    print("Login failed. Check your GitHub secrets.")
