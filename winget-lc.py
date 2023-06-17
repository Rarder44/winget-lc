import sys
import logging
import argparse

import os.path
import subprocess
import pyuac
import requests
import shutil
import zipfile
import xml.etree.ElementTree as ET
import re
from packaging import version
from settings import Settings
import sqlite3
import yaml
import os
from urllib.parse import urlparse
import urllib.request
from tqdm import tqdm
import hashlib
from ftplib import FTP, error_perm

def powershell(command):
   return subprocess.run(["powershell", "-command", command], capture_output=True)

def generateCertificate(outputPath, fileName, cerPublisher, eku, expire,password ):
    #genera un certificato con i parametri passati
    winKit= getWindowsKitFolder()
    if not os.path.exists(outputPath):   
        os.mkdir(outputPath)

    cmd=f""" $cert = New-SelfSignedCertificate -Type Custom -KeySpec Signature -Subject "{cerPublisher}" -KeyExportPolicy Exportable -CertStoreLocation "Cert:\CurrentUser\My" -KeyUsageProperty Sign  -NotAfter '{expire}' -TextExtension @("2.5.29.37={{text}}{eku}");
            Export-Certificate -Cert $cert -FilePath {outputPath}\{fileName}.cer;
            $CertPassword = ConvertTo-SecureString -String "{password}" -Force -AsPlainText;
            Export-PfxCertificate -Cert $cert -FilePath {outputPath}\{fileName}.pfx -Password $CertPassword;"""


    out=powershell(cmd)
    

    

def registerCertificate(cerPath):
    out=powershell(f"Certutil -addStore TrustedPeople {cerPath}")

    

def getWindowsKitFolder():
   confFolder= Settings().config['DEFAULT']['WindowsKitFolder']
   if confFolder=='' or not os.path.exists(confFolder):
      #TODO: search in  C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64 or near...
        assert True,"WindowsKit not found"
   
   return confFolder
   

def isCertificatePresent():
    savePath= Settings().config['certificate']['savePath']
    certName =Settings().config['certificate']['certificateName']
    if not os.path.isfile(f"{ savePath}/{ certName}.cer"):
       return False
    if not os.path.isfile(f"{ savePath}/{ certName}.pfx"):
       return False
       
    return True

def prepareWorkFolder():
    if os.path.exists(Settings().workFolder):
        shutil.rmtree(Settings().workFolder)  
    os.mkdir(Settings().workFolder)
    

def main(argv):
    """
    preparazione:
        - creare la firma
        - installare la firma come valida

    ad ogni aggiornamento
        - scaricare il file source.msix
        - patchare i problemi di appManifest.xml ???
        - modificare l'appManifest xml in modo che  "Identity" corrisponda alla firma
        - modificare il db e mantenere i programmi che mi servono
        - scaricare i file yaml di tutti i programmi che mi servono 
        - scarico le risorse in locale
        - modificare i file yaml puntando alle risorse in locale
        - faccio l'hash SHA256 di ogni file yaml e li metto nel DB ( manifest -> hash  ) 
        - creo il pacchetto msix
        - firmo il pacchetto
        - deploy del pacchetto / yaml / installazioni su server
    """
    


    parser = argparse.ArgumentParser(description="Create Zip64 files.")
    parser.add_argument("-rk", "--regen_key", default=False, help="force regenerate key")
 
    args = parser.parse_args(argv)
    #print(args)






    jmp =True

    if not jmp:
        pass
        #preparo la cartella di lavoro
        prepareWorkFolder()

        #creare la firma
        if( args.regen_key or not isCertificatePresent()):
            generateCertificate(Settings().config["certificate"]["savePath"],
                                Settings().config["certificate"]["certificateName"],
                                Settings().cerPublisher,
                                Settings().config["certificate"]["eku"],
                                Settings().config["certificate"]["expire"],
                                Settings().config["certificate"]["password"])
        
        #non serve registrare il certificato
        #lo devono registrare i client che useranno il mio winget source
        #registerCertificate( f"{Settings().config['certificate']['savePath']}/{Settings().config['certificate']['certificateName']}.cer")

        #copio la cartella sourceDefault nella workFolder
        shutil.copytree("sourceDefault",f'{Settings().workFolder}/sourceNew')
        if not os.path.exists(f'{Settings().workFolder}/sourceNew/Public'):
            os.mkdir(f'{Settings().workFolder}/sourceNew/Public')

        #scaricare il file source.msix
        originSourceLocal= f'{Settings().workFolder}/source.msix'
        download(f'{Settings().config["winget"]["source"]}/source.msix',originSourceLocal)
        #estraggo i file
        with zipfile.ZipFile(originSourceLocal, 'r') as zip:
            with open(f"{Settings().workFolder}/sourceNew/Public/index.db", 'wb') as f:
                    f.write(zip.read("Public/index.db"))


        #patch appManifest.xml in modo che  "Identity" corrisponda alla firma e cambio la versione

        #NOTE: non ho usato l'xml Parser xke durante la riscrittura del file combinava casini e il "MakeAppx" dava problemi ( non riusciva a verificare la correttezza dell' xml)
        xml= None
        with open(f"{Settings().workFolder}/sourceNew/AppxManifest.xml", 'r') as file:
            xml = file.read()

        xml = re.sub("Publisher=\"[^\\\"]*\"", f'Publisher="{Settings().cerPublisher}"', xml)


        #NOTE: lo spazio davanti a " Version" SERVE!! altrimenti va a prendere l'attributo "MinVersion"
        if Settings().config["version"]["versionType"]=="auto":
            #scarico la vecchia versione

            download(f'{Settings().config["deploy-ftp"]["baseURL"]}/source.msix',f'{Settings().workFolder}/sourceOld.msix')


            #estraggo il file AppxManifest.xml
            with zipfile.ZipFile(f'{Settings().workFolder}/sourceOld.msix', 'r') as zip:
                with open(f"{Settings().workFolder}/AppxManifestOld.xml", 'wb') as f:
                        f.write(zip.read("AppxManifest.xml"))

            #recupero la vecchia versione
            xmlOld= None
            with open(f"{Settings().workFolder}/AppxManifestOld.xml", 'r') as file:
                xmlOld = file.read()
            m = re.search(" Version=\"([^\\\"]*)\"",xmlOld,re.M)
            v = version.parse(m.groups()[0]) 
            l=list(v.release)
            l[3]+=1
            l = [str(el) for el in l]
            newVersion=".".join(l)
            xml = re.sub(" Version=\"[^\\\"]*\"", f' Version="{newVersion}"', xml)


            #cancello i file temporanei
            os.remove(f"{Settings().workFolder}/AppxManifestOld.xml")
            os.remove(f'{Settings().workFolder}/sourceOld.msix')
            
        elif Settings().config["version"]["versionType"]=="static":
            xml = re.sub(" Version=\"[^\\\"]*\"", f' Version="{Settings().config["version"]["staticVersion"]}"', xml)
            
        elif Settings().config["version"]["versionType"]=="origin":
            
            #estraggo il file AppxManifest.xml dal sorgente scaricato in precedenza
            with zipfile.ZipFile(f'{Settings().workFolder}/source.msix', 'r') as zip:
                with open(f"{Settings().workFolder}/AppxManifestForVersion.xml", 'wb') as f:
                        f.write(zip.read("AppxManifest.xml"))

            #recupero la versione
            xmlSource= None
            with open(f"{Settings().workFolder}/AppxManifestForVersion.xml", 'r') as file:
                xmlSource = file.read()
            m = re.search(" Version=\"([^\\\"]*)\"",xmlSource,re.M)
            xml = re.sub(" Version=\"[^\\\"]*\"", f' Version="{m.groups()[0]}"', xml)

            #cancello i file temporanei
            os.remove(f"{Settings().workFolder}/AppxManifestForVersion.xml")


            pass
        else:
            assert True, "INI error: [version][versionType] not valid"
        

        with open(f"{Settings().workFolder}/sourceNew/AppxManifest.xml", 'w') as file:
            file.write(xml)
    

        #modificare il db e mantenere i programmi che mi servono
        packetIDsFormatted=",".join([ f"'{s.strip()}'" for s in Settings().config["winget"]["packetIDs"].split(",")])
        print(packetIDsFormatted)
        
        con = sqlite3.connect(f"{Settings().workFolder}/sourceNew/Public/index.db")
        
        cur = con.cursor()
        cur.execute(f"DELETE from ids where ids.id not in ({packetIDsFormatted})")
        cur.execute(f"DELETE from manifest where id not in (SELECT rowid from ids) ")
        cur.execute(f"DELETE from names where rowid not in (SELECT DISTINCT name from manifest) ")
        cur.execute(f"DELETE from monikers where rowid not in (SELECT DISTINCT moniker from manifest) ")

        cur.execute(f"DELETE from versions where rowid not in (SELECT DISTINCT version from manifest union SELECT DISTINCT arp_min_version from manifest union SELECT DISTINCT arp_max_version from manifest) ")

        cur.execute(f"DELETE from commands_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from commands where rowid not in (SELECT DISTINCT command from commands_map)")
        cur.execute(f"DELETE from norm_names_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from norm_names where rowid not in (SELECT DISTINCT norm_name from norm_names_map)")
        cur.execute(f"DELETE from norm_publishers_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from norm_publishers where rowid not in (SELECT DISTINCT norm_publisher from norm_publishers_map)")
        cur.execute(f"DELETE from pfns_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from pfns where rowid not in (SELECT DISTINCT pfn from pfns_map)")
        cur.execute(f"DELETE from productcodes_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from productcodes where rowid not in (SELECT DISTINCT productcode from productcodes_map)")
        cur.execute(f"DELETE from tags_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from tags where rowid not in (SELECT DISTINCT tag from tags_map)")
        cur.execute(f"DELETE from upgradecodes_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from upgradecodes where rowid not in (SELECT DISTINCT upgradecode from upgradecodes_map)")


        cur.execute(f"""WITH RECURSIVE all_tree_pathparts (parent,path,rowidLastElement) AS (
            SELECT p1.parent,p1.pathpart,p1.rowid 
            FROM pathparts p1
            WHERE p1.rowid in (SELECT pathpart from manifest ) 

            UNION ALL

            SELECT  p.parent,p.pathpart || '\' || c.path, c.rowidLastElement
            FROM pathparts p
            JOIN all_tree_pathparts c ON p.rowid = c.parent
        )
        delete from pathparts where rowid not in ( SELECT DISTINCT parent FROM all_tree_pathparts)""")
        con.commit()


        yamlToDownloads = [{"id":row[2],"path":row[1]} for row in cur.execute("""WITH RECURSIVE all_tree_pathparts (parent,path,rowidLastElement) AS (
            SELECT p1.parent,p1.pathpart,p1.rowid 
            FROM pathparts p1
            WHERE p1.rowid in (SELECT pathpart from (SELECT * from manifest GROUP BY id having rowid = max(rowid)) as t INNER JOIN versions on ( versions.rowid = t.version ) ) 

            UNION ALL

            SELECT  p.parent,p.pathpart || '/' || c.path, c.rowidLastElement
            FROM pathparts p
            JOIN all_tree_pathparts c ON p.rowid = c.parent
        )

        SELECT * FROM all_tree_pathparts where parent is NULL""")]


        

        #scaricare i file yaml di tutti i programmi che mi servono 
        os.makedirs(f'{Settings().workFolder}/ftp',exist_ok=True)

        for el in yamlToDownloads:

            localYaml= f'{Settings().workFolder}/ftp/{el["path"]}'
            os.makedirs(os.path.dirname(localYaml),exist_ok=True)

            download( f'{Settings().config["winget"]["source"]}/{el["path"]}',localYaml)
            #analisi dello yaml 
            yamlData=None

            with open(localYaml, "r") as stream:
                yamlData= yaml.safe_load(stream)

            #scarico tutti gli installers
            i = 0
            for installer in yamlData["Installers"]:
                a = urlparse(installer["InstallerUrl"])
                newFileName = f"{i}_{os.path.basename(a.path)}"
                newFilePath=f"{Settings().workFolder}/ftp/{os.path.dirname(el['path'])}/{newFileName}"
                newFileUrl= f'{Settings().config["deploy-ftp"]["baseURL"]}/{os.path.dirname(el["path"])}/{newFileName}'
                download(installer["InstallerUrl"],newFilePath)
                i=i+1
                #modifico il link d'installazione
                installer["InstallerUrl"]=newFileUrl


            #scrivo le modifiche nello yaml
            with open(localYaml, "w") as stream:
                yaml.safe_dump(yamlData,stream)


            #faccio l'hash SHA256 del file yaml e lo metto nel DB ( manifest -> hash  ) 
            sha = sha256(localYaml)
            cur.execute(f"UPDATE manifest SET hash = x'{sha}' where pathpart= {el['id']}")
            con.commit()
        




        con.close()

        #creo il pacchetto msix
        os.environ['PATH'] += os.pathsep + Settings().config['DEFAULT']['WindowsKitFolder']
        os.system(f"MakeAppx pack /d {Settings().workFolder}/sourceNew /p {Settings().workFolder}/sourceNew.msix /nv /o")
        

        #firmo il pacchetto
        os.system(f"signtool sign /fd SHA256 /a /f {Settings().config['certificate']['savePath']}/{Settings().config['certificate']['certificateName']}.pfx " +
                f"/p {Settings().config['certificate']['password']} {Settings().workFolder}/sourceNew.msix ")
        
        shutil.move(f"{Settings().workFolder}/sourceNew.msix",f"{Settings().workFolder}/ftp/source.msix")


    #deploy del pacchetto / yaml / installazioni su server
    if Settings().config["deploy-ftp"]["uploadViaFTP"].lower()=="true":
        pushViaFTP()




class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def download(url, output_path):
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)


def sha256(filename):
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def pushViaFTP():
    ftp = myFTP(Settings().config["deploy-ftp"]["host"],Settings().config["deploy-ftp"]["username"],Settings().config["deploy-ftp"]["password"] )
    ftp.remove_contents(Settings().config["deploy-ftp"]["FTPRemotePath"])
    ftp.push_contents(f'{Settings().workFolder}/ftp',Settings().config["deploy-ftp"]["FTPRemotePath"])
    pass






class myFTP:
    def __init__(self,host,user,pwd) -> None:
        self.ftp = FTP(host)
        self.ftp.login(user,pwd)
        self.ftp.cwd(Settings().config["deploy-ftp"]["FTPRemotePath"]) 
        pass

    def remove_contents(self,path):
        for (name, properties) in self.ftp.mlsd(path=path):
            if name in ['.', '..']:
                continue
            elif properties['type'] == 'file':
                self.ftp.delete(f"{path}/{name}")
            elif properties['type'] == 'dir':
                self.remove_contents(f"{path}/{name}")               
                self.ftp.rmd(f"{path}/{name}")

    def push_contents(self,localPath,remotePath):
        if not os.path.exists(localPath):
            return
        
        #TODO: completare la copia di tutti i file della cartella specificata nella path remota.
        pass



if __name__ == '__main__':
    #run as admin
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        print("IF YOU ARE IN VSCODE - RESTART VS CODE AS ADMIN!!!")
        pyuac.runAsAdmin()
    else:        
        main(sys.argv[1:])
        
    
