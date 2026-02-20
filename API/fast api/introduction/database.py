import json
import sqlite3

class Database:
    def __init__(self):
        self.connection=sqlite3.connect("sqlite.db")
        self.cursor = self.connection.cursor()
        self.create_table("shipments")
        
    def create_table(self,name):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS shipments (id INTEGER PRIMARY KEY, weight REAL, content TEXT, status TEXT)")

cursor.execute("""INSERT INTO shipments values ('{id}','{content}','{weight}','{status}')""")
cursor.execure("""SELECT * FROM shipments WHERE id =:id AND status=:status""",{"status":status,"id":id})
connection.close()



