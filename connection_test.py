import psycopg2
conn = psycopg2.connect(
    # host="GS-SV-011",
    # host="192.168.0.236",
    host="localhost",
    database="noggin_db",
    user="noggin_app",
    password="GoodKingCoat16"
)
