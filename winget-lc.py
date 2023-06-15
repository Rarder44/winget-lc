import sys
import logging
import argparse
import configparser
import os.path
import subprocess
import pyuac
import requests
import shutil
import zipfile
import xml.etree.ElementTree as ET
import re

class Settings(object):
  def __new__(cls):
    if not hasattr(cls, 'instance'):
      cls.instance = super(Settings, cls).__new__(cls)
      cls.config=None
      cls.workFolder="tmp"
    return cls.instance
  

def powershell(command):
   return subprocess.run(["powershell", "-command", command], capture_output=True)

def generateCertificate(outputPath, fileName, CN,O,C, eku, expire,password ):
    #genera un certificato con i parametri passati
    winKit= getWindowsKitFolder()
    if not os.path.exists(outputPath):   
        os.mkdir(outputPath)

    cmd=f""" $cert = New-SelfSignedCertificate -Type Custom -KeySpec Signature -Subject "CN={CN}, O={O}, C={C}" -KeyExportPolicy Exportable -CertStoreLocation "Cert:\CurrentUser\My" -KeyUsageProperty Sign  -NotAfter '{expire}' -TextExtension @("2.5.29.37={{text}}{eku}");
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
    Settings().config = configparser.ConfigParser()
    Settings().config.read('config.ini')


    parser = argparse.ArgumentParser(description="Create Zip64 files.")
    parser.add_argument("-rk", "--regen_key", default=False, help="force regenerate key")
 
    args = parser.parse_args(argv)
    #print(args)






    jmp =True

    if not jmp:
        #preparo la cartella di lavoro
        prepareWorkFolder()

        #creare la firma
        if( args.regen_key or not isCertificatePresent()):
            generateCertificate(Settings().config["certificate"]["savePath"],
                                Settings().config["certificate"]["certificateName"],
                                Settings().config["certificate"]["CN"],
                                Settings().config["certificate"]["O"],
                                Settings().config["certificate"]["C"],
                                Settings().config["certificate"]["eku"],
                                Settings().config["certificate"]["expire"],
                                Settings().config["certificate"]["password"])
        
        #non serve registrare il certificato
        #lo devono registrare i client che useranno il mio winget source
        #registerCertificate( f"{Settings().config['certificate']['savePath']}/{Settings().config['certificate']['certificateName']}.cer")

        #copio la cartella sourceDefault nella workFolder
        shutil.copytree("sourceDefault",f'{Settings().workFolder}/sourceNew')

        #scaricare il file source.msix
        url = f'{Settings().config["winget"]["source"]}/source.msix'
        r = requests.get(url, allow_redirects=True)
        open(f'{Settings().workFolder}/source.msix', 'wb').write(r.content)
        #estraggo i file
        with zipfile.ZipFile(f'{Settings().workFolder}/source.msix', 'r') as zip:
            with open(f"{Settings().workFolder}/sourceNew/Public/index.db", 'wb') as f:
                    f.write(zip.read("Public/index.db"))


    
    #NOTE: non ho usato l'xml Parser xke durante la riscrittura del file combinava casini e il "MakeAppx" dava problemi ( non riusciva a verificare la correttezza dell' xml)
    #patch appManifest.xml in modo che  "Identity" corrisponda alla firma
    xml= None
    with open(f"{Settings().workFolder}/sourceNew/AppxManifest.xml", 'r') as file:
        xml = file.read()

    xml = re.sub("Publisher=\"[^\\\"]*\"", f'Publisher="CN={Settings().config["certificate"]["CN"]}, O={Settings().config["certificate"]["O"]}, C={Settings().config["certificate"]["C"]}"', xml)
   

    #NOTE: lo spazio davanti a " Version" SERVE!! altrimenti va a prendere l'attributo "MinVersion"
    if Settings().config["version"]["versionType"]=="auto":
        #TODO:
        pass
    elif Settings().config["version"]["versionType"]=="static":
        xml = re.sub(" Version=\"[^\\\"]*\"", f' Version="{Settings().config["version"]["staticVersion"]}"', xml)
        
    elif Settings().config["version"]["versionType"]=="origin":
        #TODO:
        pass
    else:
        assert True, "INI error: [version][versionType] not valid"
    

    with open(f"{Settings().workFolder}/sourceNew/AppxManifest.xml", 'w') as file:
        file.write(xml)
    
    #TODO: 
    """
        - modificare l'appManifest xml in modo che  "Identity" corrisponda alla firma
        - modificare il db e mantenere i programmi che mi servono
        - scaricare i file yaml di tutti i programmi che mi servono 
        - scarico le risorse in locale
        - modificare i file yaml puntando alle risorse in locale
        - faccio l'hash SHA256 di ogni file yaml e li metto nel DB ( manifest -> hash  ) 
    """


    #creo il pacchetto msix
    os.environ['PATH'] += os.pathsep + Settings().config['DEFAULT']['WindowsKitFolder']
    os.system(f"MakeAppx pack /d {Settings().workFolder}/sourceNew /p {Settings().workFolder}/sourceNew.msix /nv /o")
    

    #firmo il pacchetto
    os.system(f"signtool sign /fd SHA256 /a /f {Settings().config['certificate']['savePath']}/{Settings().config['certificate']['certificateName']}.pfx " +
              f"/p {Settings().config['certificate']['password']} {Settings().workFolder}/sourceNew.msix ")
    
    #TODO: deploy del pacchetto / yaml / installazioni su server


def debug():
    
    
    pass
    


if __name__ == '__main__':
    #run as admin
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        print("IF YOU ARE IN VSCODE - RESTART VS CODE AS ADMIN!!!")
        pyuac.runAsAdmin()
    else:        
        main(sys.argv[1:])
        
    
