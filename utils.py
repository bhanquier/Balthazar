"""
Balthazar - Fonctions utilitaires
Gestion des fichiers et hash MD5
"""
import os
import glob
import hashlib


def balthazar_is_temp_docx(path):
    """
    Balthazar - Vérifie si le fichier est un fichier temporaire Word
    
    Args:
        path: Chemin du fichier
        
    Returns:
        True si fichier temporaire (~$*.docx), False sinon
    """
    return os.path.basename(path).startswith("~$")


def balthazar_compute_md5(path):
    """
    Balthazar - Calcule le hash MD5 d'un fichier
    
    Args:
        path: Chemin du fichier
        
    Returns:
        Hash MD5 sous forme de chaîne hexadécimale
    """
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(10240), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def balthazar_scan_docs(folder):
    """
    Balthazar - Scanne récursivement tous les fichiers DOCX d'un dossier
    
    Args:
        folder: Chemin du dossier à scanner
        
    Returns:
        Liste des chemins des fichiers DOCX (sans fichiers temporaires)
    """
    all_files = glob.glob(os.path.join(folder, "**/*.docx"), recursive=True)
    return [f for f in all_files if not balthazar_is_temp_docx(f)]