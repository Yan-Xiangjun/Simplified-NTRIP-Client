import socket
import sys
import datetime
import base64
import time
import serial
from pynmeagps import NMEAReader

user = base64.b64encode(bytes('psi_user:psi', 'utf-8')).decode("utf-8")
mountPointString = 'GET /T430_32 HTTP/1.1\r\n'\
'User-Agent: NTRIP JCMBsoftPythonClient/0.2\r\n'\
f'Authorization: Basic {user}\r\n\r\n'

print(mountPointString)
# reconnect parameter (fixed values):
factor = 2  # How much the sleep time increases with each failed attempt
maxReconnect = 1
maxReconnectTime = 1200
sleepTime = 1  # So the first one is 1 second


class NtripClient(object):

    def __init__(self):
        self.buffer = 50
        self.out = sys.stdout
        self.port = 2101
        self.caster = 'ntrip.geodetic.gov.hk'
        self.setPosition(50.09, 8.66)
        self.socket = None
        self.stream = serial.Serial('/dev/ttyAMA0', 38400, timeout=3)
        self.nmr = NMEAReader(self.stream)

    def setPosition(self, lat, lon):
        self.flagN = "N"
        self.flagE = "E"
        if lon > 180:
            lon = (lon - 360) * -1
            self.flagE = "W"
        elif (lon < 0 and lon >= -180):
            lon = lon * -1
            self.flagE = "W"
        elif lon < -180:
            lon = lon + 360
            self.flagE = "E"
        else:
            self.lon = lon
        if lat < 0:
            lat = lat * -1
            self.flagN = "S"
        self.lonDeg = int(lon)
        self.latDeg = int(lat)
        self.lonMin = (lon - self.lonDeg) * 60
        self.latMin = (lat - self.latDeg) * 60

    def getGGABytes(self):
        while True:
            (raw_data, parsed_data) = self.nmr.read()
            if bytes("GNGGA", 'ascii') in raw_data:
                # print(parsed_data)
                return raw_data

    def readData(self):
        reconnectTry = 1
        sleepTime = 1

        try:
            while reconnectTry <= maxReconnect:
                found_header = False
                sys.stderr.write(f'Connection {reconnectTry} of {maxReconnect}\n')

                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                error_indicator = self.socket.connect_ex((self.caster, self.port))
                if error_indicator == 0:
                    sleepTime = 1

                    self.socket.settimeout(10)
                    self.socket.sendall(bytes(mountPointString, 'ascii'))
                    while not found_header:
                        casterResponse = self.socket.recv(4096)  #All the data
                        # print(casterResponse)
                        header_lines = casterResponse.decode('utf-8').split("\r\n")

                        # header_lines empty, request fail,exit while loop
                        for line in header_lines:
                            if line == "":
                                if not found_header:
                                    found_header = True
                                    sys.stderr.write("End Of Header" + "\n")
                            else:
                                sys.stderr.write("Header: " + line + "\n")

                        # header_lines has content
                        for line in header_lines:
                            if line.find("SOURCETABLE") >= 0:
                                sys.stderr.write("Mount point does not exist")
                                sys.exit(1)
                            elif line.find("401 Unauthorized") >= 0:
                                sys.stderr.write("Unauthorized request\n")
                                sys.exit(1)
                            elif line.find("404 Not Found") >= 0:
                                sys.stderr.write("Mount Point does not exist\n")
                                sys.exit(2)
                            elif line.find("ICY 200 OK") >= 0:
                                #Request was valid
                                self.socket.sendall(self.getGGABytes())
                            elif line.find("HTTP/1.0 200 OK") >= 0:
                                #Request was valid
                                self.socket.sendall(self.getGGABytes())
                            elif line.find("HTTP/1.1 200 OK") >= 0:
                                #Request was valid
                                self.socket.sendall(self.getGGABytes())

                    data = "Initial data"
                    while data:
                        try:
                            data = self.socket.recv(self.buffer)
                            # self.out.buffer.write(data)
                            self.stream.write(data)
                            (raw_data, parsed_data) = self.nmr.read()
                            if bytes("GNGGA", 'ascii') in raw_data:
                                print(raw_data)
                                with open('location.txt', 'w') as f:
                                    f.write(
                                        f'{parsed_data.lat},{parsed_data.NS},{parsed_data.lon},{parsed_data.EW},{parsed_data.alt},{parsed_data.quality}\n'
                                    )

                        except socket.timeout:
                            sys.stderr.write('Connection TimedOut\n')
                            data = False
                        except socket.error:
                            sys.stderr.write('Connection Error\n')
                            data = False

                    sys.stderr.write('Closing Connection\n')
                    self.socket.close()
                    self.socket = None

                    if reconnectTry < maxReconnect:
                        sys.stderr.write(
                            "%s No Connection to NtripCaster.  Trying again in %i seconds\n" %
                            (datetime.datetime.now(), sleepTime))
                        time.sleep(sleepTime)
                        sleepTime *= factor

                        if sleepTime > maxReconnectTime:
                            sleepTime = maxReconnectTime
                    else:
                        sys.exit(1)

                    reconnectTry += 1
                else:
                    self.socket = None
                    print("Error indicator: ", error_indicator)

                    if reconnectTry < maxReconnect:
                        sys.stderr.write(
                            "%s No Connection to NtripCaster.  Trying again in %i seconds\n" %
                            (datetime.datetime.now(), sleepTime))
                        time.sleep(sleepTime)
                        sleepTime *= factor
                        if sleepTime > maxReconnectTime:
                            sleepTime = maxReconnectTime
                    reconnectTry += 1

        except KeyboardInterrupt:
            if self.socket:
                self.socket.close()
            self.stream.close()
            sys.exit()


if __name__ == '__main__':
    n = NtripClient()
    n.readData()
