import sys
import logging
import argparse
import configparser
import os.path
import subprocess
import pyuac


class Settings(object):
  def __new__(cls):
    if not hasattr(cls, 'instance'):
      cls.instance = super(Settings, cls).__new__(cls)
      cls.config=None
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
            $CertPassword = ConvertTo-SecureString -String "{password}" -Force –AsPlainText;
            Export-PfxCertificate -Cert $cert -FilePath {outputPath}\{fileName}.pfx -Password $CertPassword;"""


    out=powershell(cmd)
    

    

def registerCertificate(cerPath):
    out=powershell(f"Certutil -addStore TrustedPeople {cerPath}")
    print(out)
    

def getWindowsKitFolder():
   confFolder= Settings().config['DEFAULT']['WindowsKitFolder']
   if confFolder=='' or not os.path.exists(confFolder):
      #TODO: ricerco nella cartella C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64 o qualcosa di simile...


      pass
   
   return confFolder
   

def isCertificatePresent():
    savePath= Settings().config['certificate']['savePath']
    certName =Settings().config['certificate']['certificateName']
    if not os.path.isfile(f"{ savePath}/{ certName}.cer"):
       return False
    if not os.path.isfile(f"{ savePath}/{ certName}.pfx"):
       return False
       
    return True


def main(argv):
    Settings().config = configparser.ConfigParser()
    Settings().config.read('config.ini')


    parser = argparse.ArgumentParser(description="Create Zip64 files.")
    parser.add_argument("-rk", "--regen_key", default=False, help="force regenerate key")
 
    args = parser.parse_args(argv)

    #print(args)


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


if __name__ == '__main__':
    #per avviare come admin
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        print("SE SEI IN VSCODE - RIAVVIA VS CODE COME AMMINISTRATORE!!!")
        pyuac.runAsAdmin()
    else:        
        main(sys.argv[1:])
    
