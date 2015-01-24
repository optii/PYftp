import sys
import socket
import os
import signal
import platform
import subprocess
import hashlib


##############################
# Kill those zombies !!
##############################
def kill_zombie(signum, frame):
    os.waitpid(0, 0)


##############################
# Exit on ctrl+c
##############################
def signal_handler(signal, frame):
    raise Exception("Closing down the program")


#################################################
# Checks if the username exists
# Parameters :
# username: The username to check
# Returns:
#   True if the username exists, false otherwise
#################################################
def checkUser(username, userfile):
    with open(userfile) as f:
        for line in f:
            line = line.strip().split(" ")
            print line
            if line[0] == username:
                return True
    return False


##############################################################
# Checks to see if the password for a username is correct
#
# Parameters:
#   username: The username
#   password: The password to check
# Returns:
#   True if username and password are correct, false otherwise
###############################################################
def checkPassword(username, userfile, password):
    with open(userfile) as f:
        for line in f:
            line = line.strip().split(" ")
            if line[0] == username and line[1] == hashlib.sha256(password).hexdigest():
                return True
    return False


#############################################
# Check for the user, and if found sends a
# request for the password
# Parameters:
#   arguments: The client request
#   s: The socket
# Returns:
#   The username if exists, False otherwise
#############################################
def user_cmd(arguments, userfile, s):
    if checkUser(arguments[1], userfile):
        s.send("331 Please specify a password\n")
        return arguments[1]
    else:
        s.send("430 Username incorrect\n")
        return False


##################################################
# PASS command must be preceded by the
# USER command
#
# Parameters:
#   username : The previously given username
#   arguments: The client request
# Returns:
#   True if login was successful, False otherwise
##################################################
def pass_cmd(username, userfile, arguments, s):
    if (username and checkPassword(username, userfile, arguments[1])):
        s.send("230 Login successful\n")
        return True
    elif not username:
        s.send("503 Previous request must be USER\n")
        return False
    else:
        s.send("530 Password incorrect\n")
        return False


######################################
# Sends system details to the client
######################################
def syst_cmd(s):
    s.send("215 " + platform.platform() + "\n")


####################################################
# NOTE : IN THE ACTUAL STATE THIS COMMAND DOES NOT
#        AFFECT THE TRANSFER TYPE
#
# Type command use to change the transfer type
#
# Parameters:
#   arguments: The client request
#   s: The socket
# Returns:
#   True if binary flag should be turned on
#   False if the binary flag should be turned off
#   Nothing if invalid arguments
####################################################
def type_cmd(arguments, s):
    if arguments[1] == "I" or arguments[1] == "L":
        s.send("200 Binary flag on\n")
        return True
    elif arguments[1] == "A":
        s.send("200 Binary flag off\n")
        return False
    else:
        s.send("502 Invalid arguments for type\n")


############################################
# Sends the working directory to the client
############################################
def pwd_cmd(s):
    s.send("257 \"" + os.getcwd() + "\" \n")


####################################
# Port command
#
# Parameters :
#   arguments: The client request
#   s : The socket
# Returns :
#   The calculated (ip,port)
####################################
def port_cmd(arguments, s):
    p = arguments[1].split(",")
    port = int(p[4]) * 256 + int(p[5])
    ip = p[0] + "." + p[1] + "." + p[2] + "." + p[3]
    s.send("200 Port command accepted\n")
    return (ip, port)


################################################
# Opens the data socket after a
# PORT command
#
# Parameters :
#    ip : The ip of the socket to be opened
#   port : The port of the socket to be opened
# Returns :
#   The newly opened socket
################################################
def open_data_socket(ip, port):
    s = socket.socket()
    s.connect((ip, int(port)))
    return s


##################################
# Closes the data socket
#
# Parameters :
#     s: The data socket to close
##################################
def close_data_socket(s):
    s.close()


#############################################
# Lists the current working directory of the
# server
#
# Parameters :
#   s : The socket
#   data_socket : The socket for the data
#############################################
def list_cmd(s, data_socket):
    s.send("150 Here comes the boom\n")
    try:
        p = subprocess.Popen(['ls', '-l'], stdout=subprocess.PIPE)
        data_socket.send(p.communicate()[0])
        s.send("226 Directory send OK\n")
    except:
        s.send("451 Could not read the directory\n")
    finally:
        close_data_socket(data_socket)


#############################################
# Downloads a given file from the ftp server
#
# Parameters :
#   arguments : The client request
#   s : The socket
#   data_socket : The socket for the data
#############################################
def retr_cmd(arguments, binary_flag, s, data_socket):
    s.send("150 Here comes the boom\n")
    try:
        mode = "r"
        if binary_flag:
            mode += "b"
        f = open(arguments[1], mode)
        data = f.read()
        f.close()
        data_socket.send(data)
        s.send("226 File send OK\n")
    except OSError, IOError:
        s.send("550 File not found\n")
    finally:
        close_data_socket(data_socket)


##########################################
# Uploads a file to the ftp server's
# current working directory
#
# Parameters :
#   arguments : The client request
#   s : The socket
#   data_socket : The socket for the data
##########################################
def stor_cmd(arguments, s, data_socket):
    s.send("150 Here comes the boom\n")
    try:
        f = open(arguments[1], "w")
        while 1:
            data = data_socket.recv(1024)
            f.write(data)
            if len(data) == 0:
                break

        f.close()
        s.send("226 File send OK\n")
    except IOError:
        s.send("550 File error\n")
    except socket.error:
        s.send("426 Connection was broken\n")
    finally:
        close_data_socket(data_socket)


########################################
# Changes current directory
#
# Parameters :
#   arguments : The client request
#   s : The socket
########################################
def cwd_cmd(arguments, config, s):
    try:
        dir = " ".join(arguments[1:])

        if not dir.startswith("/"):
            dir = os.path.normpath(os.getcwd() + "/" + dir)

        if config['chroot'].lower() == "true":
            if dir.startswith(config['home_dir']):
                os.chdir(arguments[1])
                s.send("200 Directory changed to " + os.getcwd() + "\n")
            else:
                s.send("550 Not able to access this directory\n")
        else:
            os.chdir(arguments[1])
            s.send("200 Directory changed to " + os.getcwd() + "\n")
    except OSError as e:
        s.send("500 " + e.message + "\n")


########################################
# Creates a directory
#
# Parameters :
#   arguments : The client request
#   s : The socket
########################################
def mkd_cmd(arguments, s):
    try:
        os.mkdir(" ".join(arguments[1:]))
        s.send("250 Folder created\n")
    except OSError as e:
        s.send("550 " + e.message + "\n")


########################################
# Removes a directory
#
# Parameters :
#   arguments : The client request
#   s : The socket
########################################
def rmd_cmd(arguments, s):
    try:
        os.rmdir(arguments[1])
        s.send("250 Folder deleted\n")
    except OSError as e:
        s.send("550 " + e.message + "\n")


########################################
# Deletes a file
#
# Parameters :
#   arguments : The client request
#   s : The socket
########################################
def dele_cmd(arguments, s):
    try:
        os.remove(arguments[1])
        s.send("250 File deleted\n")
    except OSError as e:
        s.send("550 " + e.message + "\n")


########################################
# Gives the features of the ftp server
#
# Parameters:
#   s : The socket
########################################
def feat_cmd(s):
    s.send("211-start\n211 end\n")


#####################################################
# Give the name of the file to be renamed
#
# Parameters:
#   arguments : The client request
#   s : The socket
# Returns:
#   The file name or false if the file doesn't exist
#####################################################
def rnfr_cmd(arguments, s):
    if os.path.isfile(arguments[1]):
        s.send("350 File exists\n")
        return arguments[1]
    else:
        s.send("450 File doesn't exist\n")
        return False


##############################################
# Rename the file previously given with a new
# name
#
# Must be preceded by the file from command
#
# Parameters:
#       arguments : The client request
#       src :   The source file
#       s : The socket
##############################################
def rnto_cmd(arguments, src, s):
    if src:
        try:
            os.rename(src, arguments[1])
        except OSError:
            s.send("550 Rejected\n")
    else:
        s.send("503 You must specify the file to rename first\n")


#############################################
# Creates the PASV socket for the FTP-DATA
#
# Parameters :
#       s : The socket
# Returns :
#       The client socket
#############################################
def pasv_cmd(s):
    data_socket = socket.socket()
    data_socket.bind(("127.0.0.1", 0))
    data_socket.listen(1)
    port = data_socket.getsockname()[1]
    p2 = port % 256
    p1 = (port - p2) / 256
    s.send("227 127,0,0,1," + str(p1) + "," + str(p2) + "\n")
    cl_data_socket, cl_data_addr = data_socket.accept()
    return cl_data_socket


######################################
# Gets the data socket, depending on
# whether PASV or PORT was used
#
# Parameters:
#   data_socket: The data socket or false
#   ip : The ip address or false
#   port: The port or false
# Returns:
#   The data socket or false
######################################
def get_data_socket(data_socket, ip, port, socketClient):
    if not ip and not port and not data_socket:  # if no PASV or PORT command has been called there is no connection
        socketClient.send("425 No connection established\n")
    if ip and port:  # If the PORT command was used we connect to the client port
        data_socket = open_data_socket(ip, port)
    return data_socket


#######################################
# Gets the contents of the config file
#######################################
def get_config():
    with open("pyFTP.conf") as f:
        list = map(str.strip, f.readlines())
        d = {}
        for param in list:
            param = param.split("=")
            d[param[0]] = param[1]
    return d


###############################
# The agent also known as 007
##############################
def agent(socketClient, config):
    socketClient.send("220 " + config['welcome'] + "\n")
    os.chdir(config['home_dir'])
    command = socketClient.recv(1024)
    username = False
    binary_flag = False
    data_socket = False
    ip = False
    port = False
    src = False
    arguments = command.strip("\r\n").split(" ")

    while arguments[0] != "QUIT":
        if arguments[0] == "USER":
            username = user_cmd(arguments, config["users_file"], socketClient)
        elif arguments[0] == "PASS":
            authenticated = pass_cmd(username, config["users_file"], arguments, socketClient)
        elif arguments[0] == "SYST":
            syst_cmd(socketClient)
        elif arguments[0] == "TYPE":
            binary_flag = type_cmd(arguments, socketClient)
        elif arguments[0] == "PWD":
            pwd_cmd(socketClient)
        elif arguments[0] == "PORT":
            ip, port = port_cmd(arguments, socketClient)
        elif arguments[0] == "PASV":
            data_socket = pasv_cmd(socketClient)
        elif arguments[0] == "LIST":
            data_socket = get_data_socket(data_socket, ip, port, socketClient)
            if data_socket:
                list_cmd(socketClient, data_socket)
            ip = False
            port = False
            data_socket = False
        elif arguments[0] == "RETR":
            data_socket = get_data_socket(data_socket, ip, port, socketClient)
            if data_socket:
                retr_cmd(arguments, binary_flag, socketClient, data_socket)
            ip = False
            port = False
            data_socket = False
        elif arguments[0] == "STOR":
            data_socket = get_data_socket(data_socket, ip, port, socketClient)
            if data_socket:
                stor_cmd(arguments, socketClient, data_socket)
            ip = False
            port = False
            data_socket = False
        elif arguments[0] == "FEAT":
            feat_cmd(socketClient)
        elif arguments[0] == "CWD":
            cwd_cmd(arguments, config, socketClient)
        elif arguments[0] == "MKD":
            mkd_cmd(arguments, socketClient)
        elif arguments[0] == "RMD":
            rmd_cmd(arguments, socketClient)
        elif arguments[0] == "DELE":
            dele_cmd(arguments, socketClient)
        elif arguments[0] == "RNFR":
            src = rnfr_cmd(arguments, socketClient)
        elif arguments[0] == "RNTO":
            rnto_cmd(arguments, src, socketClient)
        else:
            socketClient.send("502 Invalid command\n")

        c = socketClient.recv(1024)
        arguments = c.strip("\r\n").split(" ")

    socketClient.send("221 " + config['bye'] + "\n")
    socketClient.close()
    sys.exit()

#########################
#                       #
#         MAIN          #
#                       #
#########################
config = get_config()
signal.signal(signal.SIGINT, signal_handler)
socketListen = socket.socket()

try:
    socketListen.bind((config['ip'], int(config['port'])))
    socketListen.listen(5)
    print "Server listening on : " + config['ip'] + ':' + config['port'] + "\n"
    while True:
        socketC, addressC = socketListen.accept()

        pid = os.fork()
        if pid == 0:
            socketListen.close()
            agent(socketC, config)
        else:
            socketC.close()

    signal.signal(signal.SIGCHLD, kill_zombie)

except socket.error as e:
    print "Error " + str(e.errno) + ": " + e.message + " " + e.strerror
except Exception as e:
    print "\n" + e.message
finally:
    socketListen.close()
    if "socketC" in locals():
        socketC.close()
