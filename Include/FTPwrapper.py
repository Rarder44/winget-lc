from ftplib import FTP, error_perm
from Include.settings import Settings
import os.path
import posixpath
from Include.misc import UploadProgressBar

class FTPwrapper:
    def __init__(self,host,user,pwd) -> None:
        self.ftp = FTP(host)
        self.ftp.login(user,pwd)
        self.ftp.cwd(Settings().config["deploy-ftp"]["FTPRemotePath"]) 
        pass

    def rmdir_contents(self,path):
        #cancella tutti i file e cartelle all'interno di un path fornito ( la cartella passata non viene cancellata)
        try:
            for (name, properties) in self.ftp.mlsd(path=path):
                if name in ['.', '..']:
                    continue
                elif properties['type'] == 'file':
                    self.ftp.delete(f"{path}/{name}")
                elif properties['type'] == 'dir':
                    self.remove_contents(f"{path}/{name}")               
                    self.ftp.rmd(f"{path}/{name}")
            return True
        except:
            return False

    def push_contents(self,localPath,remotePath):
        #carica l'intera cartella "localPath" nel "remotePath" ( se il remote path non esiste, lo crea)
        if not os.path.exists(localPath):
            return
        if not self.path_exist(remotePath):
            self.mkdir(remotePath)        

        current= self.ftp.pwd()
        self.ftp.cwd(remotePath)
        for name in os.listdir(localPath):
            fulllocalpath =posixpath.join(localPath, name)
            
            if os.path.isfile(fulllocalpath):
                #print("STOR", name, localpath)
                self.upload(fulllocalpath,name,True)
                
            elif os.path.isdir(fulllocalpath):
                #print("CWD", name)
                
                fullRemotePath=posixpath.join(remotePath, name)
                self.push_contents( fulllocalpath,fullRemotePath)           
                #print("CWD", "..")
        self.ftp.cwd(current)
              

    def upload(self,localPath,remoteName,progressBar=False):
        #carica il file specificato nella cartella corrente "CWD"
        #progressBar permette di visualizzare una progressbar nella cli
        if progressBar:
            filesize = os.path.getsize(localPath)
            with UploadProgressBar(unit='B', unit_scale=True,miniters=1, desc=localPath.split('/')[-1]) as t:      
                t.total=filesize
                self.ftp.storbinary('STOR ' + remoteName, open(localPath,'rb'), callback = lambda data: t.update(len(data)) )
                t.update(1) #non so xke ma manca un byte per la progess... bha!
        else:
            self.ftp.storbinary('STOR ' + remoteName, open(localPath,'rb'))
        

    def mkdir(self,path):

        try:
            self.ftp.mkd(path)
        # ignore "directory already exists"
        except error_perm as e:
            if not e.args[0].startswith('550'): 
                raise

    
    def path_exist(self,path):
        
        current= self.ftp.pwd()
        status=False
        try:
            self.ftp.cwd(path)
            status=True
            self.ftp.cwd(current)
        except:
            pass
        
        return status

    def file_exist(self,path):
        if self.path_exist(path):
            return False
        
        #TODO: capisco se è un rif relativo o assoluto
        #TODO:prendo la cartella che dovrebbe contenere il file
        parentPath="TODO"
        #mi salvo la certella corrente
        current= self.ftp.pwd()
        #vado in quella cartella
        self.ftp.cwd(path)
        status=False
        #TODO: controllo la lista di file e vedo se c'è il file richiesto
        #TODO: prendo se c'è o no

        #prima di ritornare, reimposto la cartella precedente
        self.ftp.cwd(current)
        return status


    def exist(self,path):
        return self.path_exist(path) or self.file_exist(path)

    def getContents(self,path):
        #ritorna la lista di file e cartelle del path specificato
        contents= self.ftp.mlsd(path=path)
        ret=[]
        for (name, properties) in contents:
            if name in ['.', '..']:
                    continue
            ret.append((name, properties))
        return ret

    def removeAllEmptyFolder(self,path):
        #cancella tutte le cartelle vuote presenti in tutte le sottocartelle di "path"

        #controllo se ci sono file e cartelle,
        #se si, li scorro e vedo se posso cancellare qualcosa
        
        contents= self.getContents(path)
        if len(contents) > 0:
            for (name, properties) in contents:
                if properties['type'] == 'file':
                    #la cartella sicuaramente non è vuota -> ritorno
                    return
                
                elif properties['type'] == 'dir':
                    #trovo una cartella, che potrebbe essere vuota
                    #la scorro ricorsivamente ( se è vuota si cancellerà da sola )
                    self.removeAllEmptyFolder(f"{path}/{name}")
            

             #se dopo aver passato i file, trovo che è vuota, allora la cancello
            contents= self.getContents(path)
            if len(contents) == 0: 
                self.ftp.rmd(path)

        else:   #se è vuota -> cancello
            self.ftp.rmd(path)
            return
        
       

        


        pass

