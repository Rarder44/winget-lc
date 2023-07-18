script bash per creare un certificato valido per qualsiasi dominio locale

viengono creati: 

	server.pfx ( da registrare dentro iis o simili ) 
	
	server.key e server.crt/pem ( chiave e certificato del server, non dovrebbero servire in quanto all'interno di server.pfx ) 
	
	rootCA.crt/key/pem ( il crt server perchè va registrato nel PC che utilizzerà il sito con certificato server.pfx
	
	
	
funzionamento ( è spiegato meglio nell'sh ... ):
creo prima un root, grazie a questo root firmo un certificato che va sul sito.
installo poi il root come "trusted" nel pc che userà il sito 
in questo modo il pc vede il certificato del sito come rilasciato da un root "trused" 	



durante la creazione verrà richiesta una password per creare il certificato di root, quello del server e il pfx
ho sempre messo sempre la stessa password per comodità... comunque funziona...

per sicurezza meglio mettere password diverse... bisogna capire quale password inserire in quale momento però....











IIS
	per configurare IIS basta installare il file pfx nella gestione dei certificati del sito
	andare nei "bindings" del sito e aggiungere la porta 443 e selezionare il certificato
	
	
APACHE
	usare il makecert cosi almeno un certificato lo crea e imposta già tutto "correttamente" ( usare la stessa password del certificato creato con questo script ) 
	andare nel file httpd-ssl
		modificare il ServerName in localhost
		aggiungere / decommentare la riga con SSLCertificateChainFile in modo che sia cosi:
			SSLCertificateChainFile "conf/ssl.crt/chain.pem"
	copiare il file chain.pem dentro la certella conf/ssl.crt/
	copiare il file server.pem dentro conf/ssl.crt/ e rinominarlo in server.crt ( si lo vuole così, non è un errore ) -> cancellare / rinominare il vecchio file server.crt
	copiare il file server.key dentro conf/ssl.key/ -> cancellare / rinominare il vecchio file server.key
	
	
	riavviare apache ( nel caso di problemi guarda il log di apache e bestemmia... forte ) 
	
	