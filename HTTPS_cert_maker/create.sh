#!/bin/bash

#creo le cartelle
mkdir out
mkdir out/ssl/
 
#creo il certificato di "root" ( i parametri sono in root.csr.cnf ) e dura 10 anni ( 3650 )
#creo prima la key che viene usata per firmare il certificato ( 2 comando ) 
#trasformo il formato PEM ( ascii ) in crt 		 (in teoria non serve, ma metti caso che mi serva il crt, lo ho già! ) 
openssl genrsa -des3 -out ./out/ssl/rootCA.key 2048
openssl req -x509 -new -nodes -key ./out/ssl/rootCA.key -sha256 -days 3650 -out ./out/ssl/rootCA.pem -config <( cat root.csr.cnf )
openssl x509 -in ./out/ssl/rootCA.pem -out ./out/ssl/rootCA.crt -inform PEM -outform DER 


#creo una richiesta di certificato "server.csr" con i dati di server.csr.cnf ed una chiave 
#( 2 comando ) do la richiesta in pasto al certificato root di prima e lui mi firma la richiesta dandomi un PEM relativo al sito che voglio firmare ( passo il file v3.ext che contiene info aggiuntive utili per evitare che chrome o altri browser diano problemi ) 
#trasformo il formato PEM ( ascii ) in crt 		 (in teoria non serve, ma metti caso che mi serva il crt, lo ho già! ) 
openssl req -new -sha256 -nodes -out ./out/server.csr -newkey rsa:2048 -keyout ./out/server.key -config <( cat server.csr.cnf )
openssl x509 -req -in ./out/server.csr -CA ./out/ssl/rootCA.pem -CAkey ./out/ssl/rootCA.key -CAcreateserial -out ./out/server.pem -days 3650 -sha256 -extfile v3.ext
openssl x509 -in ./out/server.pem -out ./out/server.crt -inform PEM -outform DER 


#unisco i PEM in una catena di certificati
cat ./out/server.pem ./out/ssl/rootCA.pem  > ./out/chain.pem
#esporto la catena e la chiave dell'ultimo certificato in un file pfx ( dovrebbe funzionare! ) 
cp ./out/server.key ./out/chain.key
openssl pkcs12 -export -certpbe PBE-SHA1-3DES -keypbe PBE-SHA1-3DES -nomac -inkey ./out/chain.key -in ./out/chain.pem -out ./out/server.pfx -name 'jmwinget_cert_https'


#SU WINDOWS ( SICURAMENTE FUNZIONA ) ... se l'ultimo comando sopra non funziona...
#devo rinominare il file che prima era server.key ( nella cartella out ) in chain.key 
#il nome del pem e della key devono combaciare!!
#il comando certutil fa tutto lui
#cd out
#certutil -mergepfx chain.pem cert.pfx




#occorre poi installare il pfx nel server di destinazione 
#e installare il rootCA.crt nel client di destinazione come radice trusted 