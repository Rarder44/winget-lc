import sys
import argparse
import os.path
import pyuac
import requests
import shutil
import zipfile
import re
from packaging import version
from Include.settings import Settings
import yaml
import os
from urllib.parse import urlparse

from Include.CertUtil import *
from Include.FTPwrapper import *
from Include.winget_db import *

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
    #TODO: implementare "l'update"
    #se i file sono già stati scaricati su server ( xke non ci sono aggiornamenti )
        #posso confrontare lo sha256 del file eseguibile presente nellìo yaml
        #o molto più semplicemente la versione / path dei file
            #se uso la versione, posso controllare se il file yaml esiste sul mio server e se la "PackageVersion" e la "ManifestVersion" combaciano
            #se si, ho già i file, altrimenti non li ho
    #questi non vengono riscaricati e non vengono cancellati dal server durante il caricamento FTP
    
    assert Settings().config["DEFAULT"]["updateType"]  in ["clean","update"], "INI error: [DEFAULT][updateType] not valid"
    assert Settings().config["version"]["versionType"]  in ["auto","static","origin"], "INI error: [version][versionType] not valid"
    assert Settings().config["winget"]["source"] != "", "INI error: [winget][source] not set"
    assert Settings().config["winget"]["packetIDs"]  != "", "INI error: [winget][packetIDs] set at least one ID"

    assert Settings().config["DEFAULT"]["updateType"] == "update" and Settings().config["deploy-ftp"]["baseURL"] != "", "INI error: [deploy-ftp][baseURL] must be set if [DEFAULT][updateType] == update"

    #TODO: implemento gli altri assert... (SBATTA)


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
        

        with open(f"{Settings().workFolder}/sourceNew/AppxManifest.xml", 'w') as file:
            file.write(xml)
    

        #modificare il db e mantenere i programmi che mi servono
        packetIDs=Settings().config["winget"]["packetIDs"].split(",")
        
        db = winget_db(f"{Settings().workFolder}/sourceNew/Public/index.db")
        db.cleanByPacketIDs(packetIDs)       
        yamlToDownloads = db.getYaml()


        if Settings().config["DEFAULT"]["updateType"]=="update":
            myCurrentSource = f'{Settings().config["deploy-ftp"]["baseURL"]}/source.msix'
            myCurrentSourceLocal=f"{Settings().workFolder}/myCurrentSource.msix"
            download(myCurrentSource,myCurrentSourceLocal)
            #estraggo il file index.db dal sorgente scaricato 
            with zipfile.ZipFile(myCurrentSourceLocal, 'r') as zip:
                with open(f"{Settings().workFolder}/index_myCurrentSource.db", 'wb') as f:
                        f.write(zip.read("Public/index.db"))
            os.remove(myCurrentSourceLocal)

            db = winget_db(f"{Settings().workFolder}/index_myCurrentSource.db")     
            yamlOnMyServer = db.getYaml()
            filesyamlOnMyServer=[yaml["path"] for yaml in yamlOnMyServer]
           
            

            # - gli yaml già sul mio server
            alreadyDownloaded = [yaml for yaml in yamlToDownloads if yaml["path"] in filesyamlOnMyServer ]
            file_alreadyDownloaded = [yaml["path"] for yaml in alreadyDownloaded]

            # - gli yaml che devo scaricare 
            toDownload = [yaml for yaml in yamlToDownloads if yaml["path"] not in file_alreadyDownloaded ]

            
            # - gli yaml che devo cancellare
            toDelete = [yaml for yaml in yamlOnMyServer if yaml["path"] not in file_alreadyDownloaded ]

            
            #TODO:

            """
            scarico gli alreadyDownloaded sia dal mio server che da quello sorgente
            confronto le versioni ( "PackageVersion" e la "ManifestVersion" ) 
                se sono uguali -> non faccio nulla, non verranno riscaricati i file e nemmeno cancellati dal mio server
                se sono diversi ->  aggiungo a toDownload e a toDelete lo yaml 

            
            scorro tutti i toDownload e li scarico normalmente ( come se fosse clean )

            ATTENZIONE: in fase di cancellazione NON bisogna cancellare tutto!! 
            occorre cancellare:
            - source.msix
            - tutte le cartelle / file presenti in toDelete 
                prendo la cartella contenitore del file yaml da cancellare e la cancello ( dovrebbero esserci dentro anche tutti gli eseguibili )

            lancio poi il comando 
            ftp.removeAllEmptyFolder(Settings().config["deploy-ftp"]["FTPRemotePath"])
            che cancella tutte le cartelle vuote ricorsivamente 

            
            """
                       



        

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
            db.updateManifestSHA(el["id"],sha)


        db.close()

       

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







def pushViaFTP():
    ftp = FTPwrapper(Settings().config["deploy-ftp"]["host"],Settings().config["deploy-ftp"]["username"],Settings().config["deploy-ftp"]["password"] )

    
    ftp.remove_contents(Settings().config["deploy-ftp"]["FTPRemotePath"])
    ftp.push_contents(f'{Settings().workFolder}/ftp',Settings().config["deploy-ftp"]["FTPRemotePath"])
    pass








if __name__ == '__main__':
    #run as admin
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        print("IF YOU ARE IN VSCODE - RESTART VS CODE AS ADMIN!!!")
        pyuac.runAsAdmin()
    else:        
        main(sys.argv[1:])
        
    
