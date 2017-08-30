#!/usr/bin/env python3
#-*-coding: utf-8 -*-


'''Script d'administration en Python
Usage : python majWP.py [options] [paramètres]
Options :
    -h --help ->aide
    -f --file= fichier de conf des sites
    -a --all ->tous les sites
    -c --clean ->supprime les anciennes sauvegardes
    -b --backup ->realise les sauvegardes
    -d --download ->telecharge la derniere version de Wordpress
    -o --old ->supprime les dossiers .old
    -u --update ->met a jour les sites
    -r --restore ->restaure les sites avec les sauvegardes effectuées

    Exemples :
    
    ./majWP.py -abcd 
        realise la suppression de toutes les sauvegardes, sauvegarde les fichiers et bases de donnees, telecharge la derniere version de Wordpress pour tous les sites

    ./majWP.py -f /home/sites.conf
        precise le chemin du fichier de configuration
'''
import getopt
import sys
import wget
import tarfile
import os
import shutil
import datetime
from configobj import ConfigObj
import re

def usage():
    print( __doc__ )

def init_sites(sitesf):
    listeSites = {}
    configSites = ConfigObj(sitesf)
    for site in configSites:
        if configSites[site]['update'] == '1':
            listeSites[site] = configSites[site]
    return listeSites

def recup_version(ficVersion):
    define_pattern = re.compile(r"""\bdefine\(\s*('|")(.*)\1\s*,\s*('|")(.*)\3\)\s*;""")
    assign_pattern = re.compile(r"""(^|;)\s*\$([a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*)\s*=\s*('|")(.*)\3\s*;""")

    php_vars = {}
    for line in open(ficVersion):
        for match in define_pattern.finditer(line):
            php_vars[match.group(2)]=match.group(4)
        for match in assign_pattern.finditer(line):
            php_vars[match.group(2)]=match.group(4)

    return php_vars['wp_version']

def compare_versions(listeSites,racine):
    print('----')
    newwp = os.path.join(racine,"wordpress")
    if os.path.isdir(newwp)==True:
        chemnewver = os.path.join(racine,'wordpress/wp-includes/version.php')
        newver = recup_version(chemnewver)
        print("Nouvelle version : ",newver)
    else:
        print("Aucune version de Wordpress n'est présente, utilisez l'option -d.")
        print('----')
        print('Fin anticipée du script.')
        sys.exit(0)
    for site in listeSites:
        chever = os.path.join(listeSites[site]['chem'],'wordpress/wp-includes/version.php')
        versite = recup_version(chever)
        print("Version du site",listeSites[site]['name']," : ",versite)

def menage(bkdir):
    print('----')
    shutil.rmtree(bkdir,'ignore_errors')
    os.mkdir(bkdir)
    print("Suppression des sauvegardes ok")
    verif_free_space(bkdir)

def downloadWP(tempdir,wpdir):
    print('----')
    print("Suppression de l'ancienne version de Wordpress")
    #supprime le repertoire wordpress
    shutil.rmtree(wpdir,'ignore_errors')    
    print("Téléchargement")
    #lance le telechargement
    url = 'https://wordpress.org/latest.tar.gz'
    tarwpname = wget.download(url,tempdir)
    print("")
    print("Décompactage")
    tarwp = tarfile.open(tarwpname)
    tarwp.extractall("./")
    tarwp.close
    print("Fin de téléchargement et décompactage")
    verif_free_space(wpdir)

def backupsites(bkupdir,siteslist):
    print('----')
    today = datetime.date.today()
    tod = today.strftime('%d-%m-%Y')
    print("Début de sauvegarde du "+tod)
    newbkup = os.path.join(bkupdir,tod)
    while os.path.isdir(newbkup)==True:
        newbkup = newbkup+"i"
    os.mkdir(newbkup)
    for site in siteslist:
        print("Sauvegarde du site",site)
        src = siteslist[site]['chem']
        print('src ',src)
        dest = os.path.join(newbkup,siteslist[site]['name'])
        print('dest ',dest)
        shutil.copytree(src,dest)
        print("Copie du site ",siteslist[site]['name']," terminée.")
    print("Sauvegarde des bases de données.")
    for site in siteslist:
        print("Sauvegarde de la bdd du site",siteslist[site]['name'])
        dumpfile = os.path.join(newbkup,siteslist[site]['name']+'.sql')
        if siteslist[site]['pwbdd'] == '':
            cmddump = '/usr/bin/mysqldump -h '+siteslist[site]['srvbdd']+' -u '+siteslist[site]['usrbdd']+' '+siteslist[site]['bdd']+' >'+dumpfile
        else:
            cmddump = '/usr/bin/mysqldump -h '+siteslist[site]['srvbdd']+' -u '+siteslist[site]['usrbdd']+' -p'+siteslist[site]['pwbdd']+' '+siteslist[site]['bdd']+' >'+dumpfile
        os.popen(cmddump)
    print("Fin de sauvegarde.")
    verif_free_space(bkupdir)

def restore(backupdir,listeSites):
    print('----')
    print("Restauration des sites")
    i = 1
    siterest = []
    for site in listeSites:
        print(i,"-",listeSites[site]['name'])
        siterest.append(listeSites[site]['name'])
        i += 1
    print("")
    numsit = input("Quel site souhaitez vous restaurer (numéro) ? ")
    print("Site à restaurer : ", siterest[int(numsit)-1])
    sitearestaurer = listeSites[siterest[int(numsit)-1]]
    if sitearestaurer == {}:
        print("Problème, pas de site trouvé.")
        sys.exit()
    #print(sitearestaurer)
    i = 1
    lchem = []
    for root, dirs, files in os.walk(backupdir):
        for rep in dirs:
            if rep == sitearestaurer['name']:
                print(i,"-",os.path.join(root,rep))
                lchem.append(os.path.join(root,rep))
                i += 1
    print("")
    if lchem == []:
        print("Aucune version de sauvegarde trouvée pour ce site. Fin du script.")
        sys.exit()

    numver = input("Quel version souhaitez-vous restaurer (numéro) ? ")
    if os.path.isdir(lchem[int(numver)-1]) == False:
        print("Pas de sauvegarde trouvée.")
        sys.exit()
    
    src = lchem[int(numver)-1]
    print("Version à restaurer : ",src)
    dest = sitearestaurer['chem']
    print("Chemin cible : ",dest)
    print("Suppression du dossier wordpress du site")
    if os.path.isdir(dest)==True:
        shutil.rmtree(dest,'ignore_errors')
        print("Répertoire destination supprimé")
    print("Restauration des fichiers à partir de la sauvegarde")
    shutil.copytree(src,dest)
    print("Restauration des droits sur le wp-content")
    newwpcont = os.path.join(listeSites[site]['chem'],'wordpress/wp-content')
    print("Répertoire wp-content : ",newwpcont)
    for root, dirs, files in os.walk(newwpcont):
        for rep in dirs:
            os.chown(os.path.join(root,rep),33,33)
        for fic in files:
            os.chown(os.path.join(root,fic),33,33)
    os.chown(newwpcont,33,33)
    print("Restauration de la base de données")
    lstsrc = src.split('/')
    repsrc = "/".join(lstsrc[0:-1])
    sqlf = os.path.join(repsrc,sitearestaurer['name']+".sql")
    if os.path.isfile(sqlf) == False:
        print("Pas de dump sql trouvé.")
        sys.exit()
    print("Fichier dump utilisé : ",sqlf)
    if sitearestaurer['pwbdd'] == '':
        cmdtxt = '/usr/bin/mysql -h '+sitearestaurer['srvbdd']+' -u '+sitearestaurer['usrbdd']+' '+sitearestaurer['bdd']+' <'+sqlf
    else:
        cmdtxt = '/usr/bin/mysql -h '+sitearestaurer['srvbdd']+' -u '+sitearestaurer['usrbdd']+' -p'+sitearestaurer['pwbdd']+' '+sitearestaurer['bdd']+' <'+sqlf
    os.popen(cmdtxt)
    print("Restauration de la base de données ok.")
    print("Fin de restauration.")

def rmoldf(listeSites):
    print('----')
    print("Suppression des dossiers .old")
    for site in listeSites:
        chemrepold = os.path.join(listeSites[site]['chem'],'wordpress.old')
        print("Suppression du dossier : ",chemrepold)
        if os.path.isdir(chemrepold)==False:
            print("Le répertoire n'existe pas !")
        else:
            shutil.rmtree(chemrepold,'ignore_errors')
            print("Répertoire supprimé.")
    print("Fin de suppression des dossiers .old")

def verif_free_space(racine):
    print('----')
    stat = os.statvfs(racine)
    freespace = stat.f_bfree*stat.f_bsize
    freespacek = freespace/1024
    freespacem = freespacek/1024
    freespaceg = freespacem/1024
    if freespaceg > 1:
        print("Espace libre : ",'%.2f' %freespaceg," Go")
    elif freespacem > 1:
        print("Espace libre : ",'%.2f' %freespacem," Mo")
    elif freespacek > 1 :
        print("Attention espace libre : ",'%.2f' %freespacek," ko !!!!!!!!!!!")
    elif freespace > 1 :
        print("Attention espcae libre ",'%.2f' %freespace," octets !!!!!!!")

def updateWP(listeSites,racine):
    print('++++----++++')
    print('Début de mise à jour des sites')
    print('++++----++++')
    for site in listeSites:
        print('============')
        print('Mise à jour du site',listeSites[site]['name'])
        print('============')
        src = os.path.join(listeSites[site]['chem'],'wordpress')
        dest = os.path.join(listeSites[site]['chem'],'wordpress.old')
        print('Conserve le site en .old')
        print(src)
        print(dest)
        shutil.move(src,dest)
        print('--')
        newwp = os.path.join(racine,'wordpress')
        destwp = os.path.join(listeSites[site]['chem'],'wordpress')
        print('Copie le nouveau wordpress')
        print(newwp)
        print(destwp)
        shutil.copytree(newwp,destwp)
        print('--')
        print("Copie l'ancien wp-config.php")
        wpconf = os.path.join(listeSites[site]['chem'],'wordpress.old/wp-config.php')
        newwpconf = os.path.join(listeSites[site]['chem'],'wordpress/wp-config.php')
        print(wpconf)
        print(newwpconf)
        shutil.copy2(wpconf,newwpconf)
        print('--')
        print("Copie l'ancien wp-content")
        wpcont = os.path.join(listeSites[site]['chem'],'wordpress.old/wp-content')
        newwpcont = os.path.join(listeSites[site]['chem'],'wordpress/wp-content')
        print(wpcont)
        print(newwpcont)
        #supprime l'ancien wp-content
        shutil.rmtree(newwpcont,'ignore_errors')
        #copie l'ancien wp-content dans le nouveau dossier wordpress
        shutil.copytree(wpcont,newwpcont)
        print('--')
        print("Remet les droits sur le wp-content : ",newwpcont)
        print(newwpcont)
        for root, dirs, files in os.walk(newwpcont):
            for rep in dirs:
                os.chown(os.path.join(root,rep),33,33)
            for fic in files:
                os.chown(os.path.join(root,fic),33,33)
        os.chown(newwpcont,33,33)
        print('--')
        urlupdate = listeSites[site]['url']+'/wordpress/wp-admin/upgrade.php'
        print("Mise à jour de la base de donnée sur",urlupdate)
        cont = input('Souhaitez-vous continuer y/N ? ')
        if cont != 'y':
            print('----')
            print('Arrêt anticipé du script')
            sys.exit(0)

def main(argv):
    timedeb = datetime.datetime.today()
    time = timedeb.strftime('%d-%m-%Y %H:%M:%S')
    print(time)
    racine = os.getcwd()
    verif_free_space(racine)
    #prepare l'arbo
    ##chemins
    fptemp = os.path.join(racine,'temp')
    fpwordpress = os.path.join(racine,'wordpress')
    fpbackup = os.path.join(racine,'backup')
    #supprime et recree le repertoire temp
    shutil.rmtree(fptemp,'ignore_errors')
    os.mkdir(fptemp)
    #cree le repertoire backup s'il n'existe pas
    if os.path.isdir(fpbackup)==False:
        os.mkdir(fpbackup)
    tous = 0
    menag = False
    backups = False
    downloadw = False
    rmold = False
    updatew = False
    resto = False
    sitesFile = os.path.join(racine,'sites.conf')
    
    try:
        opts, args = getopt.getopt(argv, "hf:acbdour", ["help", "file=","all","clean","backup","download","old","update","restore"])
    except getopt.GetoptError:
        usage()                       
        sys.exit(2)
    for opt, arg in opts:             
        if opt in ("-h", "--help"):   
            usage()                   
            sys.exit()                
        elif opt in ("-f", "--file"):
            sitesFile = os.path.join(racine,arg)
        elif opt in ("-a", "--all"):
            tous = 1
        elif opt in ("-c", "--clean"):
            menag = True
        elif opt in ("-b", "--backup"):
            backups = True
        elif opt in ("-d", "--download"):
            downloadw = True
        elif opt in ("-u", "--update"):
            updatew = True
        elif opt in ("-o", "--old"):
            rmold = True
        elif opt in ("-r", "--restore"):
            resto = True

    #lecture du fichier de conf des sites
    print('----')
    if tous == 1:
        sites = ConfigObj(sitesFile)
        print("Tous les sites seront pris en compte.")
    else:
        sites = init_sites(sitesFile)
        print("Les sites pris en compte sont les suivants :")
        for site in sites:
            print("- ",sites[site]['url'])
    if downloadw:
        downloadWP(fptemp,fpwordpress)
    compare_versions(sites,racine)
    if menag:
        menage(fpbackup)
    if backups:
        backupsites(fpbackup,sites)
    if rmold:
        rmoldf(sites)
    if updatew:
        print('----')
        y = input('Voulez-vous réaliser les mises à jour y/N ? ')
        if y != 'y':
            print('Mises à jour annulées.')
            sys.exit(0)
        else:
            print('mise à jour')
            updateWP(sites,racine)
    if resto:
        restore(fpbackup,sites)
    print('----')
    timefin = datetime.datetime.today()
    time = timefin.strftime('%d-%m-%Y %H:%M:%S')
    print(time)
    duree = timefin - timedeb
    print("Durée d'exécution : ",duree.seconds," s")
    print("Fin du script.")

if __name__ == "__main__":
    main(sys.argv[1:])
