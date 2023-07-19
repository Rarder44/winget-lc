from Include.settings import Settings
import subprocess
import os.path
import urllib.request
from tqdm import tqdm
import hashlib
import cgi
import re
import requests
import werkzeug

def powershell(command):
   return subprocess.run(["powershell", "-command", command], capture_output=True)


def getWindowsKitFolder():
   confFolder= Settings().config['DEFAULT']['WindowsKitFolder']
   if confFolder=='' or not os.path.exists(confFolder):
      #TODO: search in  C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64 or near...
        assert True,"WindowsKit not found"
   
   return confFolder
   

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

#è inutile, ma è più elegante da vedere e se devo implementare qualcosa in futuro è già qua
class UploadProgressBar(tqdm):
    pass



    


def getDownloadFileName(url):

    #url = "https://sourceforge.net/projects/winscp/files/WinSCP/6.1.1/WinSCP-6.1.1-Setup.exe/download"
    #url="https://cdn.winget.microsoft.com/cache/source.msix"
    try:
        with requests.get(url) as req:
            if content_disposition := req.headers.get("Content-Disposition"):
                param, options = werkzeug.http.parse_options_header(content_disposition)
                if param == 'attachment' and (filename := options.get('filename')):
                    return filename

            path = urllib.parse.urlparse(req.url).path
            name = path[path.rfind('/') + 1:]
            return name
    except requests.exceptions.RequestException as e:
        raise e


def download(url, output_path:str,overrideOutName):
    #ritorna un tupla con ( path completo del file sacricato, nome nome del file )

    #cerco di recupeare il nome dal sito
    if overrideOutName is None:
        #url = "https://sourceforge.net/projects/winscp/files/WinSCP/6.1.1/WinSCP-6.1.1-Setup.exe/download"
        overrideOutName = getDownloadFileName(url)


    outFilePath=output_path.rstrip("\\/")+"/"+overrideOutName
    with DownloadProgressBar(unit='B', unit_scale=True,miniters=1, desc=overrideOutName) as t:
        urllib.request.urlretrieve(url, filename=outFilePath, reporthook=t.update_to)
        
    return outFilePath ,overrideOutName



def sha256(filename):
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()