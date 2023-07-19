# winget-lc
winget Local Cache - locally copies and manages installation packages to distribute them faster in a local network

this tool allows you to keep a series of packages in an FTP/HTTP cache in order to distribute them efficiently on a local network.


( TODO: to translate... ) 




## setup *AMP server



winget per funzionare ha bisogno che il sito da cui scarica il pacchetto sia https
	se è online usare cpanel e generare il certificato
	se è locale usare lo script nella cartella "HTTPS_cert_maker" per creare il certificato e registrarlo come c'è scritto nel readme della cartella

creare un account FTP che permetta di accedere all'area di "winget"


fine?



## setup IIS server

certificato
	se è locale usare lo script nella cartella "HTTPS_cert_maker" per creare il certificato e registrarlo come c'è scritto nel readme della cartella

creare un account FTP che permetta di accedere all'area di "winget"

per risolvere i problemi di url con il "+" modifica il file "web.config" ( presente nella cartella principale del sito ) in questo modo:
```
<system.webServer>
	<security>
	  <requestFiltering allowDoubleEscaping="true">
	  </requestFiltering>
	</security> 
</system.webServer>
```
( il tag <system.webServer> ) dovrebbe essere già presente ) 

registrare dentro "Tipi MIME" i tipi ( altrimenti i file non vengono scaricati e viene dato err 404):
.msix		application/msix
.yaml		application/x-yaml



## setup client

se il server è locale, registrare il certificato "rootCA" generato con HTTPS_cert_maker come "root trusted"
usare il certRegist.bat ( modificarlo inserndo il nome corretto del certificato impostato nel ini ) per registrare il certificato del source ( in modo che venga accettato da winget ) 

per ignorare il problema 0x8a15005e : The server certificate did not match any of the expected values
	winget settings --enable BypassCertificatePinningForMicrosoftStore.
