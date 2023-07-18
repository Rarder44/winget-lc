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