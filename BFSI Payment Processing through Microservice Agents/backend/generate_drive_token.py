from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/drive.file']  # Access only files your app creates

# Path to your OAuth credentials
CLIENT_SECRETS_FILE = r'C:\Users\merugumala.y\Documents\bfsi-payments-microservice\data\google-credentials.json'

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

# Save token
with open('data/drive_token.json', 'w') as token_file:
    token_file.write(creds.to_json())

print("Drive token saved at data/drive_token.json")
