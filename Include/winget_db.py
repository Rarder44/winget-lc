import sqlite3
import gc



class winget_db:

    def __init__(self,db_path: str) -> None:
        self.db_path=db_path
        self.isClosed=True
        self.__reopenIfClosed()
        
        


    def cleanByPacketIDs(self,packetIDs: list[str]):
        self.__reopenIfClosed()
        #packetIDs = un vettore di packetID da TENERE nel db ( ciò che non fa riferimento a questi PacketID verrà cancellato )

        packetIDsFormatted=",".join([ f"'{s.strip()}'" for s in packetIDs])


        cur = self.con.cursor()
        cur.execute(f"DELETE from ids where ids.id not in ({packetIDsFormatted})")
        cur.execute(f"DELETE from manifest where id not in (SELECT rowid from ids) ")
        cur.execute(f"DELETE from names where rowid not in (SELECT DISTINCT name from manifest) ")
        cur.execute(f"DELETE from monikers where rowid not in (SELECT DISTINCT moniker from manifest) ")

        cur.execute(f"DELETE from versions where rowid not in (SELECT DISTINCT version from manifest union SELECT DISTINCT arp_min_version from manifest union SELECT DISTINCT arp_max_version from manifest) ")

        cur.execute(f"DELETE from commands_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from commands where rowid not in (SELECT DISTINCT command from commands_map)")
        cur.execute(f"DELETE from norm_names_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from norm_names where rowid not in (SELECT DISTINCT norm_name from norm_names_map)")
        cur.execute(f"DELETE from norm_publishers_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from norm_publishers where rowid not in (SELECT DISTINCT norm_publisher from norm_publishers_map)")
        cur.execute(f"DELETE from pfns_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from pfns where rowid not in (SELECT DISTINCT pfn from pfns_map)")
        cur.execute(f"DELETE from productcodes_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from productcodes where rowid not in (SELECT DISTINCT productcode from productcodes_map)")
        cur.execute(f"DELETE from tags_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from tags where rowid not in (SELECT DISTINCT tag from tags_map)")
        cur.execute(f"DELETE from upgradecodes_map where manifest not in (SELECT DISTINCT rowid from manifest) ")
        cur.execute(f"DELETE from upgradecodes where rowid not in (SELECT DISTINCT upgradecode from upgradecodes_map)")


        cur.execute(f"""WITH RECURSIVE all_tree_pathparts (parent,path,rowidLastElement) AS (
            SELECT p1.parent,p1.pathpart,p1.rowid 
            FROM pathparts p1
            WHERE p1.rowid in (SELECT pathpart from manifest ) 

            UNION ALL

            SELECT  p.parent,p.pathpart || '\' || c.path, c.rowidLastElement
            FROM pathparts p
            JOIN all_tree_pathparts c ON p.rowid = c.parent
        )
        delete from pathparts where rowid not in (
		select * from(
			SELECT DISTINCT parent FROM all_tree_pathparts 
				union 
			SELECT DISTINCT rowidLastElement FROM all_tree_pathparts
			) where parent not null
		)""")
        self.con.commit()

    def getYaml(self):
        self.__reopenIfClosed()
        cur = self.con.cursor()
        return [{"id":row[2],"path":row[1]} for row in cur.execute("""WITH RECURSIVE all_tree_pathparts (parent,path,rowidLastElement) AS (
            SELECT p1.parent,p1.pathpart,p1.rowid 
            FROM pathparts p1
            WHERE p1.rowid in (SELECT pathpart from (
								SELECT * from manifest INNER JOIN versions on ( versions.rowid = manifest.version ) GROUP BY id having versions.version = max(versions.version)
						) as t INNER JOIN versions on ( versions.rowid = t.version ) ) 
                                                                   
            UNION ALL

            SELECT  p.parent,p.pathpart || '/' || c.path, c.rowidLastElement
            FROM pathparts p
            JOIN all_tree_pathparts c ON p.rowid = c.parent
        )

        SELECT * FROM all_tree_pathparts where parent is NULL""")]


    def updateManifestSHA(self,manifestID,SHA):
        self.__reopenIfClosed()
        cur = self.con.cursor()
        cur.execute(f"UPDATE manifest SET hash = x'{SHA}' where pathpart= {manifestID}")
        self.con.commit()

    def close(self):
        self.con.close()
        self.isClosed=True
        gc.collect()        #se no potrebbe rimanere aperto il file...

    def __reopenIfClosed(self):
        if self.isClosed:
            self.con = sqlite3.connect(self.db_path)