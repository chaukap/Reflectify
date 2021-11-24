import mysql.connector
import pandas as pd

keys = pd.read_csv("keys.csv")

server = keys.SessionsServer[0]
database = keys.SessionsDb[0]
username = keys.SessionUser[0]
password = keys.SessionPassword[0]

connection = mysql.connector.connect(host=server, database=database, user=username, password=password, ssl_key='client-key.pem', ssl_cert='client-cert.pem', ssl_ca='server-ca.pem')
cursor = connection.cursor()
cursor.execute("SELECT * FROM access_requests")
print(cursor.fetchall())