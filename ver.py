from garminconnect import Garmin

client = Garmin("seu@email.com", "suasenha")
client.login()
print("Login OK")
print([m for m in dir(client) if 'vo2' in m.lower()])