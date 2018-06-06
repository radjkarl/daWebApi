import ssl
import socket
import builtins
from queue import Queue
from math import ceil

from inspect import Signature, Parameter

from PyQt5 import QtCore  # TODO: replace with normal thread

# to make wepAPI independent of other packages, 
# that's a soft link pointing to fancytools.os.PathStr:
from dAwebAPI.PathStr import PathStr
from dAwebAPI.SeizedCom import SeizedCom
from dAwebAPI.parseArgStr import applyTyp


class _UploadThread(QtCore.QThread):
    sigUpdate = QtCore.pyqtSignal(int, int)
    sigDone = QtCore.pyqtSignal()
    sigError = QtCore.pyqtSignal(str)

    def __init__(self, api, *args, **kwargs):
        super().__init__()
        self.api = api
        self.queue = []
        self.active = True
        self._lastFns = None
        self.addToQueue(*args, **kwargs)
        
    def prepare(self, paths, new_paths, fnUpdate=None, fnDone=None, fnError=None):
        self.paths = paths
        if new_paths is None:
            new_paths = paths
        self.new_paths = new_paths
        if fnUpdate:
            self.sigUpdate.connect(fnUpdate)
        if fnDone:
            self.sigDone.connect(fnDone)
        if fnError:
            self.sigError.connect(fnError) 
        self._lastFns = fnUpdate, fnDone, fnError
        self.sigError.connect(self.cancel)

    def addToQueue(self, *args, **kwargs):
        self.queue.append((args, kwargs))

    def cancel(self):
        self.active = False
        self.sigUpdate.disconnect()
      # TODO:
#       def cancel(self):  # TODO on base class together with uploadthread
#         self._cancel = True
#         if self._downloadID:
#             api = WebAPI(*self.api.address)  # TODO: add use_ssl
#             api._send(('cancelDownload(%s)' % self._downloadID).encode())
#             res = api._recv()
#             if res != b'OK':
#                 print('couldnt cancel donwload: %s' % res)
#                 self.sigError.emit(res.decode())
#             api.conn.close()
  
    def run(self):
        while True:
            args, kwargs = self.queue.pop(0)

            if self._lastFns:
                fnUpdate, fnDone, fnError = self._lastFns 
                if fnUpdate:
                    self.sigUpdate.disconnect(fnUpdate)
                if fnDone:
                    self.sigDone.disconnect(fnDone)
                if fnError:
                    self.sigError.disconnect(fnError) 

            self.prepare(*args, **kwargs)
            self._run()
                               
            if not self.active:
                fn = self.api.__getattr__('cancelUpload')
                if fn:  # if server has fn of same name 
                    fn()
                return
            if not len(self.queue):
                return
        
    def _run(self):
        islocal = self.api.isLocal()
        for index, (p, npath) in enumerate(zip(self.paths, self.new_paths)):
            p = PathStr(p)
            self.api._send(str('upload(%s,%s)' % (p.size(), npath)).encode())
            answer = self.api._recv().decode()  # conn.recv(1024).decode()

            if answer == 'OK':
                if islocal:
                    # the server runs on the same machine as the client
                    # here, there is no  reason to read and copy all files
                    # creating a symbolic link is enough:
                    self.api._send(p)
                    self.sigUpdate.emit(index, 100)
                else:
                    with open(p, 'rb') as f:
                        size = p.size()
                        ntimes = ceil(size / self.api._buffsize)
                        ntimes = min(100, ntimes)

                        size_piece = ceil(size / ntimes)
                        for i in range(ntimes):
                            if not self.active:
                                self.api._send(b'STOP')
                                return
                            data = f.read(size_piece)
                            self.api._send(data)
                            answer = self.api._recv()
                            if answer == b'OK':
                                self.sigUpdate.emit(index, int(100 * (i / ntimes)))
                            else:
                                self.sigError.emit(answer.decode())
                                return

            else:
                self.sigError.emit(answer)
                return

        self.sigDone.emit()


class _DownloadThread(QtCore.QThread):
    sigUpdate = QtCore.pyqtSignal(int)
    sigDone = QtCore.pyqtSignal(object)
    sigError = QtCore.pyqtSignal(str)

    def __init__(self, api, dfiles, root, **kwargs):
        super().__init__()
        self.api = api
        self._cancel = False
        self.queue = []
        self._nfiles = 0
        self._downloadID = None
        self.addToQueue(dfiles, root, kwargs)

    def addToQueue(self, dfiles, root, kwargs):
        if not type(dfiles) in (tuple, list):
            dfiles = [dfiles]
        self._nfiles += len(dfiles)
        self.queue.append((dfiles, root, kwargs))

    def run(self):
        self._files = []
        self._fnsDone = []
        self._jobfiles = []
        while len(self.queue):
            dFiles, root, kwargs = self.queue.pop()
            cmd = kwargs.get('cmd', None)
            fnsDone = kwargs.get('fnsDone', None)

            ll = len(dFiles)
            jobfiles = []
            for f in dFiles:
                if self._cancel: 
                    break
                if ll == 1 and root.isFileLike():
                    # local file => root 
                    localpath = root
                else:
                    # local  file => root\relFilePath
                    localpath = root.join(f)
                    
                self.api._q.get()
                if self._download(f, localpath, cmd):
                    self._files.append(localpath)
                    jobfiles.append(localpath)
                self.api._q.put(1)

            if fnsDone:  

                # need to allocate to self otherwise singleShot doesnt work
                self._jobfiles.append(jobfiles)
                if not type(fnsDone) in (list, tuple):
                    fnsDone = [fnsDone]
                self._fnsDone.extend(fnsDone)
                QtCore.QTimer.singleShot(0, self._doneJob)
        self.sigDone.emit(self._files)

    def _doneJob(self):
        # execute all done functions try with/-out path as argument
        for fi, files in zip(self._fnsDone, self._jobfiles):
            if len(files) == 0:
                files = None               
            if len(files) == 1:
                files = files[0]
                               
            try:
                fi(files)
            except TypeError:
                fi()
        self._fnsDone = []
        self._jobfiles = []

    def cancel(self):  # TODO on base class together with uploadthread
        self._cancel = True
        if self._downloadID:
             
            api = WebAPI(*self.api.address)  # TODO: add use_ssl
            api._send(('cancelDownload(%s)' % self._downloadID).encode())
            res = api._recv()
            if res != b'OK':
                print('couldnt cancel donwload: %s' % res)
                self.sigError.emit(res.decode())
            api.conn.close()

    def _download(self, serverpath, localpath, cmd):
        if cmd is None:
            cmd = 'download(%s)' % serverpath
        self.api._send(cmd.encode())
 
        out = self.api.conn.recv(self.api._buffsize)
        # DOWNLOAD
        if out[0:1] == b'%':
            self.sigUpdate.emit(0)

            # ONLY CREATE LINK IF CLIENT AND SERVER ARE ON  SAME MACHINE:
            if self.api.isLocal() and len(out) < 256:
#                 print(out, 333, out[5:])
                out = out[11:]
                try:
                    out = PathStr(out.decode())
                except UnicodeDecodeError:
                    pass
                else:
                    if out.exists():
                        out.symlink(localpath)
                        return
                    else:
                        out = out.encode()  # sigError only takes bytes 
            else:  # ACTUALLY DOWNLOAD FILE
                # ensure folder structure exists:
                p = PathStr(localpath).splitNames()
                PathStr(p[0]).mkdir(*p[1:-1])
                
                self._downloadID = int.from_bytes(out[1:7], 'big')
                # TODO: put also in SeizedCom class
                size = int.from_bytes(out[7:11], 'big')
                out = out[11:]
                msg_every_n_perc = 1
                stepsize = size / (100 / msg_every_n_perc)

                isize = 0
                with open(localpath, 'wb') as f:
                    f.write(out)
                    isize += len(out)
                    remaining = size - len(out)
                    while remaining > 0: 
                        out = self.api.conn.recv(self.api._buffsize)
                        if out == b'STOP':
                            return False
                        
                        f.write(out)
                        remaining -= len(out)
                        isize += len(out)
                        # sigupdate.emit:
                        if isize > stepsize:
                            # download process for this file:
                            rel = (size - remaining) / size  
                            # progress over all files:
                            overall = (len(self._files) + rel) / self._nfiles 
                            self.sigUpdate.emit(int(100 * overall))
                            isize = 0
        else:
            self.sigError.emit(bytes(out))
        return True


def signatureFromStr(args, ret):
    '''
    creates a Python function signature from argumend out putput signature strings
     e.g.:
        args = 'str, int'
        ret = 'bytes'
        ==> inspect.Signature{(str, int) -> bytes}
    '''

    def _totyp(ss):
        return getattr(builtins, ss, ss)

    return_annotation = _totyp(ret) if ret else Signature.empty
    X = Parameter.POSITIONAL_OR_KEYWORD
    params = []
    for pi in args.split(', '):

        ss = pi.split(':')
        if len(ss) == 2:
            # param has type hint
            P = Parameter(ss[0], X, annotation=_totyp(ss[1]))
        else:
            ss = pi.split('=')
            if len(ss) == 2:
                # param has default value
                P = Parameter(ss[0], X, default=ss[1])
            elif len(ss[0]):
                P = Parameter(ss[0], X)
            else:
                continue
        params.append(P)
    return Signature(parameters=params,
                     return_annotation=return_annotation)


class WebAPI(QtCore.QObject, SeizedCom):
    '''
    eccess web based api is the same fashion ad local apis
    >>> mylib = WebAPI('192.169.1.1', 443) # the servers ip and port
    >>> mylib.function1
    doc of function1
    >>> mylib.function2(1,2,3)
    formated output of function2
    >>> mylip.help()
    list of all all available functions
    '''
    sigError = QtCore.pyqtSignal(bytes)

    def __init__(self, IPOrSocket, port=443, use_ssl=True, timeout=20,
                 buffsize=4096):
        self._timeout = timeout
        self._downloadThread = None
        self._uploadThread = None
        self._q = Queue()
        self._q.put(1)
        
        if isinstance(IPOrSocket, ssl.SSLSocket):
            conn = IPOrSocket
        else:
            conn = self._connection(IPOrSocket, port, use_ssl)
        super().__init__(conn=conn, buffsize=buffsize)

        # temporarily overrides self._format, because it refers to self._api:
        self._api = {}
        # need to pre-define types, so __getAttr_ + _format works:
        self._api['api_json'] = signatureFromStr('', 'json'), ''
        
        self._api = self.api_json()
        for key, (args, ret, doc) in self._api.items():
            self._api[key] = signatureFromStr(args, ret), doc

    def help(self):
        return self.api_md()

    def __dir__(self):
        return list(self._api.keys())

#     @staticmethod
    def _connection(self, HOST, PORT, use_ssl=True, verify_ssl=True):
        sock = socket.socket(socket.AF_INET)
        if use_ssl:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # optional
            context.check_hostname = False  # disable check  host==domain

            if not verify_ssl:
            # if the server certificate is self-signed and not added to a
            # certificate authority, trust check will fail, so diable it:
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=HOST)

        # raise socket.timeout, if nothing comes after X sec
        sock.setblocking(False)
        sock.settimeout(self._timeout)  # max wait time
        try:
            sock.connect((HOST, PORT))
        except (socket.timeout, ssl.SSLEOFError):
            if use_ssl == True:
                print('WARNING: could not connect via SSL. Your connection is not private.')
                return self._connection(HOST, PORT, use_ssl=False)
        except ssl.SSLError:
                print('WARNING: SSL certificate not verified. Your connection might be corrupted.')
                return self._connection(HOST, PORT, use_ssl, verify_ssl=False)            
        return sock

    @staticmethod
    def _buildCmd(fn, args):
        '''
        fn ... function string listed in api()
        args ... tuple/list of argumens for that function
        returns command to be sended to server
            example: fn='login'  args=('karl','pass123456')
                     ==>'login(karl,pass123456)'
        '''
        cmd = fn
        if args is not None:
            cmd += '(%s)' % ','.join([str(a) for a in args])
        return cmd

    def _format(self, fn, out:str):
        '''
        format string/byte output into function output dtype, if specified
           e.g.: def myFn()->int:
                    return '1'
                 _format(myFn, '1') ==> 1
        '''
        if callable(fn):
            sig = fn.__signature__
        else:
            try:
                sig = self._api[fn][0]
            except KeyError:
                return out
        ret = sig.return_annotation
        if ret is not Signature.empty:
            try:
                return applyTyp(out, ret)
            except Exception:
                print('ERROR formating output [%s] to type [%s]' % (
                    out[:100], ret))
        return out

    def __getattr__(self, request):
        '''translate all (undefined) method calls into send commands following
           'METHOD(ARG1, ARG2)' using functions defined in self._api[name]=signature,doc
          returns function with __help__ and __signature__
        '''
        try:
            sig, doc = self._api[request]
        except KeyError:
            raise AttributeError()
        else:

            def fn(*args):
                request = self._buildCmd(fn.request, args)
                self._q.get()
                self._send(request)
                # only receive answer if a receive type is given:
                if fn.__signature__.return_annotation is not Signature.empty:
                    answer = self._format(fn, self._recv())
                else:
                    answer = None
                self._q.put(1)
                return answer

            fn.request = request
            fn.__doc__ = doc
            fn.__signature__ = sig
            return fn

    def close(self):
        self._recv()
        self.conn.close()

    def _recv(self):
        out = None
        try:
            out = SeizedCom._recv(self)
        except Exception:
            if out is None:
                raise
            if isinstance(out, bytearray):
                out = bytes(out)  # because sigError takes only bytes
            self.sigError.emit(out)
        return out

    def upload(self, paths, new_paths=None, *args, **kwargs):
        '''
        paths ... local file paths
                   e.g. ['/home/user/myFile.png',...]
        new_paths ... name under which file is saved on the server 
                   e.g. ['10.png',...]
        '''

        if not self._isUploading():
            d = self._uploadThread = _UploadThread(self, paths, new_paths, *args, **kwargs)
            d.start()
            return d
        else:
            self._uploadThread.addToQueue(paths, new_paths, *args, **kwargs)

    def isReady(self):
        return not self._q.empty() and not self._isDownloading() and not self._isUploading()

    def download(self, serverpath, localpath, **kwargs):
        '''
        serverpath ... #### // one or multiple paths to be downloaded
                   e.g. 'file/on/server'
        localpath ... local file root
                   e.g. 'c://users/karl/myFolder/'
        '''
        if not self._isDownloading():
            d = self._downloadThread = _DownloadThread(self, serverpath, localpath, **kwargs)
            d.start()
            return d
        else:
            self._downloadThread.addToQueue(serverpath, localpath, kwargs)

    def _isDownloading(self):
        return self._downloadThread is not None and not self._downloadThread.isFinished()

    def _isUploading(self):
        return self._uploadThread is not None and not self._uploadThread.isFinished()


if __name__ == '__main__':
    # try to connect to local server
    # TODO: provide accessible test server
    HOST, PORT = socket.gethostbyname(socket.gethostname()), 443  # local
    S = WebAPI(HOST, PORT)
    
    print(dir(S))
    print(S.user.__doc__)
    print(S.help())
