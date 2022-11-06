from socket import *
import threading
import os
from getpass import getpass
from pathlib import Path


class Server:
    def __init__(self, server_ip):
        self.server_name = server_ip
        self.server_port = 8000
        self.server_socket = socket(AF_INET, SOCK_DGRAM)

    def login_account(self):
        user_name = input("Usuario: ")
        password = getpass("Contraseña: ")
        msg = "login|" + user_name + "|" + password
        self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))
        ans = self.server_socket.recv(2048).decode()
        if ans == "OK":
            print(f"Iniciada sesión como {user_name}")
            self.user = user_name
            self.password = password
            return True
        elif ans == "IN":
            print("Ya se ha iniciado sesión con esta cuenta")
            return False
        else:
            print("Usuario/Contraseña incorrectos")
            return False

    def create_account(self):
        user_name = input("Usuario: ")
        password = input("Contraseña: ")
        password_conf = input("Confirmar contraseña: ")
        if password == password_conf:
            msg = "create|" + user_name + "|" + password
            self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))
            ans = self.server_socket.recv(2048).decode()
            if ans == "OK":
                print(f"Cuenta creada como {user_name}. Inicia sesión")
                return True
            elif ans == "USER-EXISTS":
                print("El usuario ya está en existe")
            else:
                print("Error al crear cuenta, vuelva a intentarlo.")
        else:
            print("Las contraseñas no coinciden")
            return False

    def get_ip(self, name):
        msg = "quest_ip|" + self.user + "|" + self.password + "|" + name
        self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))
        ans = self.server_socket.recv(2048).decode().split("|")
        if ans[0] == "YES":
            return ans[1]
        else:
            return ans[0]

    def get_name(self, ip):
        msg = "quest_name|" + ip
        self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))
        ans = self.server_socket.recv(2048).decode()
        return ans

    def log_trans(self, sender_name, file_name):
        msg = f"log_trans|{sender_name}|{self.user}|{file_name}"
        self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))

    def logout(self):
        msg = "out|" + self.user + "|" + self.password
        self.server_socket.sendto(msg.encode(), (self.server_name, self.server_port))
        print("Se ha cerrado sesión")


class Receiver:
    def __init__(self, server):
        self.server_port = 12000
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.server_socket.bind(("", self.server_port))
        self.server_socket.listen()
        self.server = server
        print("Listo para recibir archivos")

    def welcome(self):
        while True:
            connection_socket, addr = self.server_socket.accept()
            user_name = self.server.get_name(addr[0])
            self.recv(connection_socket, user_name)

    def save_file(self, file_name, connection_socket):
        connection_socket.send("Y".encode())
        downloads_path = str(Path.home() / "Downloads")
        file_name = downloads_path + "/" + file_name
        with open(file_name, "wb") as file:
            while True:
                data = connection_socket.recv(4096)
                if not data:
                    break
                file.write(data)

    def accept_file(self, file_name, connection_socket):
        file_format = file_name.split(".")[-1]
        print("Introduce el nombre con el que guardar el archivo: ")
        name = input()
        if name == "":
            name = file_name.replace(f".{file_format}", "")
        file_name = name + "." + file_format
        self.save_file(file_name, connection_socket)

    def recv(self, connection_socket, user_name):
        file_name = connection_socket.recv(4096).decode()
        print(f"{user_name} quiere enviar {file_name}")
        print("Desea aceptar el archivo (Y/N): ")
        check = input()
        if check.upper() == "Y":
            self.accept_file(file_name, connection_socket)
            print("Archivo recibido correctamente. Guardado en 'Descargas'")
            self.server.log_trans(user_name, file_name)
        else:
            connection_socket.send("N".encode())
            print("Archivo rechazado")


class Sender:
    def __init__(self, server):
        self.server = server
        self.server_port = 12000

    def connect(self, server_name):
        self.client_socket = socket(AF_INET, SOCK_STREAM)
        self.client_socket.connect((server_name, self.server_port))

    def check_file(self, file_name):
        return os.path.exists(file_name)

    def send_file(self):
        while True:
            command  = input()
            if command == "/send":
                user_name = input("A quien desea enviar el archivo: ")
                server_name = self.server.get_ip(user_name)
                if server_name == "NO-USER":
                    print("Usuario no existente")
                elif server_name == "NO-CONN":
                    print("Usuario no conectado")
                else:
                    self.connect(server_name)
                    file_name = input("Introduce el archivo a enviar: ")
                    if self.check_file(file_name):
                        self.client_socket.send(file_name.encode())
                        check = self.client_socket.recv(4096).decode()
                        if check == "Y":
                            with open(file_name, "rb") as file:
                                data = file.read()
                            self.client_socket.sendall(data)
                            print("Archivo enviado correctamente")
                        else:
                            print("Archivo rechazado")
                        self.client_socket.close()
                    else:
                        print("Archivo no existente")
            elif command == "/logout":
                self.server.logout()
                os._exit(1)
            elif command == "/exit":
                self.server.logout()
                os._exit(1)


def main():
    os.system("cls||clear")
    server_ip = input("IP del servidor: ")
    server = Server(server_ip)
    while True:
        print("1. Iniciar sesión")
        print("2. Crear cuenta")
        print("3. Salir")
        opc = input()
        if opc == "1":
            ans = server.login_account()
            if ans:
                break
        elif opc == "2":
            ans = server.create_account()
        elif opc == "3":
            os._exit(1)
        else:
            print("Elige una opción existente")
    receiver = Receiver(server)
    sender = Sender(server)
    thread_recv = threading.Thread(target=receiver.welcome)
    thread_sender = threading.Thread(target=sender.send_file)
    thread_recv.start()
    thread_sender.start()

if __name__ == "__main__":
    main()
    