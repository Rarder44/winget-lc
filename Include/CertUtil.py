import os.path
from Include.settings import Settings
from Include.misc import *

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




def isCertificatePresent():
    savePath= Settings().config['certificate']['savePath']
    certName =Settings().config['certificate']['certificateName']
    if not os.path.isfile(f"{ savePath}/{ certName}.cer"):
       return False
    if not os.path.isfile(f"{ savePath}/{ certName}.pfx"):
       return False
       
    return True