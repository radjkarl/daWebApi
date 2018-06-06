'''
Created on 23 May 2018

@author: karl
'''
from math import ceil
import socket


class SeizedCom:

    def __init__(self, conn=None, buffsize=4096):
        self.conn = conn
        self._buffsize = buffsize
    
    def _recv(self, out=None, max_size=None):
        if out is None:
            out = self.conn.recv(self._buffsize)
        if out[0:1] == b'%':  # package is sent sized
            size = int.from_bytes(out[1:5], 'big')  # read first 4 bytes to get size
            if max_size is not None:
                size = min(size, max_size)
            out = out[5:]
            remaining = size - len(out)
            out = bytearray(out)
            while remaining > 0: 
                answer = self.conn.recv(self._buffsize)
                out.extend(answer)
                remaining -= len(answer)
        return out

#     def _recvToFile(self, path):
#             n_recv = int.from_bytes(out[1:3], 'big')
#             if n_recv:
#                 n_recv += 1
# 
#             with open(localpath, 'wb') as f:
#                 f.write(out[3:])
#                 for _ in range(n_recv):
#                     out = self.conn.recv(self._buffsize)
#                     f.write(out)

    def _send(self, msg):
        try:
            msg = msg.encode()
        except AttributeError:
            pass  # is already bytes
        nbyt = self._nSend(len(msg))[1]
        self.conn.send(b'%' + nbyt + msg)

    def sendFile(self, path):  # , fnUpdate=None):
        self._cancelSendFile = False
        with open(path, 'rb') as f:
            size = path.size()
            n, bsize = self._nSend(size)
            msg = f.read(self._buffsize)
            ID = id(self).to_bytes(6, 'big')
            self.conn.send(b'%' + ID + bsize + msg)
            remaining = size - len(msg)
            while remaining:
                if self._cancelSendFile:
                    self.conn.send(b'STOP')
                    return
                msg = f.read(self._buffsize)
                self.conn.send(msg)
                remaining -= len(msg)

    def cancelSendFile(self):
        self._cancelSendFile = True

    def _nSend(self, size):
        # number of additional receives
        n = ceil(size / self._buffsize) - 1
        return n, size.to_bytes(4, 'big')

    @property
    def address(self):
        '''returns host IP and port'''
        return self.conn.getpeername()

    def isLocal(self):
        '''
        returns True, is webserver runs on localhost
        '''
        return self.address[0] == socket.gethostbyname(socket.gethostname())
