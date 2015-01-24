# PYftp
Simple FTP Server in Pyhton

# pyFTP.conf

supported parameters :

**home_dir***: The starting dir for the server

**chroot***: Whether to contain the user to the home_dir

**ip***: The server's ip address

**port***: The port for the server to listen on

**users_file***: The file containing the user configuration

**welcome***: The welcome message

**bye***: The goodbye message

* the parameter is obligatory

# users.conf
The user conf file should contain 2 columns the first being the username the second being the password encrypted using sha256 encryption

**example:**

*user password*

