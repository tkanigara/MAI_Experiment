import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="mai_socmed_report",
        user="mai_user",
        password="mai_password",
        host="localhost",
        port=15432
    )