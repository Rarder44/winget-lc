from Include.settings import Settings
import subprocess
import os.path
import urllib.request
from tqdm import tqdm
import hashlib


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