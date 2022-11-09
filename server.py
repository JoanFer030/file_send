from socket import *
import sqlite3
from threading import Thread
import os
from datetime import datetime

class Server:
    def __init__(self):
        self.server_port = 8000
        self.server_socket = socket(AF_INET, SOCK_DGRAM)
        self.server_socket.bind((gethostbyname(gethostname()), self.server_port))
        self.n_trans = 0
        print(f"{self.time()}> Servidor listo.\n")
        self.users = {}
        self.trans = {}
        self.actual_users = {}
        self.connect_db()

    def connect_db(self):
        if os.path.exists("files/data.sql"):
            self.conn = sqlite3.connect("files/data.sql")
            self.cursor = self.conn.cursor()
            self.cursor.execute("""
                SELECT *
                FROM users;
            """)
            records = self.cursor.fetchall()
            for user in records:
                self.users[user[0]] = [user[1], "", "NO"]
            print(f"{self.time()}> Tabla 'users' cargada con {len(records)} usuarios")
            self.cursor.execute("""
                SELECT *
                FROM file_transfer;
            """)
            records = self.cursor.fetchall()
            self.n_trans = len(records)
            for record in records:
                self.trans[record[0]] = (record[1], record[2], record[3], record[4])
            print(f"{self.time()}> Tabla 'file_transfer' cargada con {len(self.trans)} transferencias.")
            print(f"{self.time()}> Tabla 'record' cargada.\n")
        else:
            self.conn = sqlite3.connect("files/data.sql")
            self.cursor = self.conn.cursor() 
            self.cursor.execute("""
                CREATE TABLE users(
                    user_name varchar(50) primary key,
                    password varchar(100) not null
                )
            """)
            self.conn.commit()
            print(f"{self.time()}> Tabla 'users' creada")
            self.cursor.execute("""
                CREATE TABLE file_transfer(
                    id integer primary key autoincrement,
                    name_sender varchar(50) not null references users,
                    name_recv varchar(50) not null references users,
                    file varchar(150) not null,
                    datetime varchar(50) not null
                )
            """)
            self.conn.commit()
            print(f"{self.time()}> Tabla 'file_transfer' creada")
            self.cursor.execute("""
                CREATE TABLE record(
                    id integer primary key autoincrement,
                    user varchar(50) not null references users,
                    ip varchar(50) not null,
                    login_time varchar(150) not null,
                    logout_time varchar(50) not null
                )
            """)
            self.conn.commit()
            print(f"{self.time()}> Tabla 'record' creada")
        
    def add_user(self, user, password, info):
        if user in self.users:
            self.server_socket.sendto("USER-EXISTS".encode(), info)
        else:
            self.cursor.execute(f"""
                INSERT INTO users
                VALUES (:user_name, :password)
            """,
            {
                "user_name" : user, 
                "password" : password
            })
            self.conn.commit()
            self.server_socket.sendto("OK".encode(), info)
            self.users[user] = [password, info[0], "NO"]
            print(f"{self.time()}> Nuevo usuario creado: {user}")

    def login(self, user, password, info):
        if user in self.users and password == self.users[user][0] and self.users[user][2] == "NO":
            now = f"{datetime.now().day:02d}-{datetime.now().month:02d}-{datetime.now().year} {datetime.now().hour:02d}:{datetime.now().minute:02d}:{datetime.now().second:02d}"
            self.users[user] = [password, info[0], "YES"]
            self.actual_users[user] = now
            self.server_socket.sendto("OK".encode(), info)
            print(f"{self.time()}> {user} ha iniciado sesión ({info[0]}).")
        elif user in self.users and password == self.users[user][0] and self.users[user][2] == "YES":
            self.server_socket.sendto("IN".encode(), info)
            print(f"{self.time()}> {user} ({self.users[user][1]}) se ha intentado iniciar sesión desde ({info[0]}).")
        else:
            self.server_socket.sendto("ERROR".encode(), info)

    def logout(self, user, password, info):
        self.users[user] = [password, "", "NO"]
        now = f"{datetime.now().day:02d}-{datetime.now().month:02d}-{datetime.now().year} {datetime.now().hour:02d}:{datetime.now().minute:02d}:{datetime.now().second:02d}"
        self.cursor.execute("""
            INSERT INTO record (user, ip, login_time, logout_time)
            VALUES (:user, :ip, :login_time, :logout_time)
        """,
        {
            "user" : user,
            "ip" : info[0],
            "login_time" : self.actual_users[user],
            "logout_time" : now
        })
        self.conn.commit()
        del self.actual_users[user]
        print(f"{self.time()}> {user} ha cerrado sesión.")

    def get_ip(self, user, password, name, info):
        print(f"{self.time()}> {user} ha solicitado la IP de {name}.")
        if name in self.users:
            if self.users[name][2] == "YES":
                ip = self.users[name][1]
                msg = "YES|" + ip
                self.server_socket.sendto(msg.encode(), info)
                print(f"\t> La IP de {name} es {ip}.")
            else:
                self.server_socket.sendto("NO-CONN".encode(), info)
                print(f"\t> El usuario {name} no está conectado.") 
        else:
            self.server_socket.sendto("NO-USER".encode(), info)
            print(f"\t> El usuario {name} no existe.")

    def get_name(self, ip, info):
        for i in self.users:
            if ip == self.users[i][1]:
                self.server_socket.sendto(i.encode(), info)
                break

    def log_transfer(self, name_sender, name_recv, file_name):
        now = self.time(2)
        self.cursor.execute("""
            INSERT INTO file_transfer (name_sender, name_recv, file, datetime)
            VALUES (:name_sender, :name_recv, :file_name, :datetime)
        """,
        {
            "name_sender" : name_sender,
            "name_recv" : name_recv,
            "file_name" : file_name, 
            "datetime" : now
        })
        self.conn.commit()
        print(f"{self.time()}> {name_sender} envio a {name_recv}: {file_name}")
        self.n_trans += 1
        self.trans[self.n_trans] = (name_sender, name_recv, file_name, now)
    
    def listen(self):
        while True:
            msg, info = self.server_socket.recvfrom(2048)
            msg = msg.decode().split("|")
            if msg[0] == "create":
                self.add_user(msg[1], msg[2], info)
            elif msg[0] == "login":
                login_t = Thread(target=self.login, args=(msg[1], msg[2], info))
                login_t.start()
            elif msg[0] == "out":
                self.logout(msg[1], msg[2], info)
            elif msg[0] == "quest_ip":
                get_t = Thread(target=self.get_ip, args=(msg[1], msg[2], msg[3], info))
                get_t.start()
            elif msg[0] == "quest_name":
                name_t = Thread(target=self.get_name, args=(msg[1], info))
                name_t.start()
            elif msg[0] == "log_trans":
                self.log_transfer(msg[1], msg[2], msg[3])

    def time(self, t=1):
        if t == 1:
            return f"{datetime.now().hour:02d}:{datetime.now().minute:02d}:{datetime.now().second:02d}"
        elif t == 2:
            return f"{datetime.now().day:02d}-{datetime.now().month:02d}-{datetime.now().year} {datetime.now().hour:02d}:{datetime.now().minute:02d}:{datetime.now().second:02d}"

    def commands(self):
        commands_dict = {
            "/info" : "información del servidor",
            "/users" : "lista los usuarios actuales",
            "/user <nick>" : "información del usuario", 
            "/trans" : "muestra todas las transferencias",
            "/help" : "lista de comandos",
            "/close" : "cerrar servidor",
        }
        while True:
            hor = "\u2500"
            command = input("")
            if command == "/users":
                trad = {"YES":"SI", "NO":"NO"}
                print(f"\n{self.time()}>")
                print("Usuario", " "*40, "Dirección", " "*10, "Conectado")
                print(hor*80)
                for name, info in self.users.items():
                    print(f"{name:<48}{info[1]:<25}{trad[info[2]]}")
                print("\n")
            elif command == "/help":
                print(f"\n{self.time()}>")
                print("Comando", " "*20, "Descripción")
                print(hor*100)
                for name, description in commands_dict.items():
                    print(f"{name:40}{description}")
                print("\n")
            elif command == "/info":
                info = {
                    "Nº de usuarios" : len(self.users),
                    "Nº de transferencias" : self.n_trans,
                    "IP" : self.server_socket.getsockname()[0],
                    "Puerto" : self.server_socket.getsockname()[1],
                }
                print(f"\n{self.time()}>")
                print("Información")
                print(hor*50)
                for name, description in info.items():
                    print(f"{name:<30}{description}")
                print("\n")
            elif command.startswith("/user"):
                user = command[6:]
                trad = {"YES":"SI", "NO":"NO"}
                if user in self.users:
                    info = self.users[user]
                    print(f"\n{self.time()}>")
                    print("Usuario", " "*36, "Contraseña", " "*8, "Dirección", " "*10, "Conectado")
                    print(hor*95)
                    print(f"{user:<46}{info[0]:<18}{info[1]:<25}{trad[info[2]]}")
                    print("\n")
                else:
                    print("El usuario no existe")
            elif command == "/trans":
                print(f"\n{self.time()}>")
                print("ID", " "*2, "Remitente", " "*15, "Destino", " "*15, "Archivo", " "*22, "Fecha")
                print(hor*100)
                for tran in self.trans:
                    info = self.trans[tran]
                    print(f"{tran:<6}{info[0]:<26}{info[1]:<24}{info[2]:<24}{info[3]}")
                print("\n")
            elif command == "/close":
                check = input(f"{self.time()}> Seguro que quieres cerrar el servidor (Y/N): ")
                if check.upper() == "Y":
                    print(f"{self.time()}> Servidor cerrado")
                    os._exit(1)
                else:
                    print(f"{self.time()}> Cierre cancelado")
            else:
                print(f"{self.time()}> Comando no existente")


os.system("cls||clear")
server = Server()
commands_t = Thread(target=server.commands)
commands_t.start()
server.listen()

