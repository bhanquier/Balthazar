"""
Balthazar - Gestion des projets au format .balthazar
Un fichier .balthazar = archive ZIP contenant tout le projet
"""
import os
import json
import zipfile
import shutil
from datetime import datetime
import streamlit as st

from config import (
    BALTHAZAR_PROJECTS_DIR,
    BALTHAZAR_CURRENT_PROJECT_FILE,
    BALTHAZAR_NAME,
    BALTHAZAR_VERSION,
    BALTHAZAR_EMBED_MODEL,
    BALTHAZAR_LLM_MODEL
)


def balthazar_init_workspace():
    """Crée le dossier workspace s'il n'existe pas"""
    if not os.path.exists(BALTHAZAR_PROJECTS_DIR):
        os.makedirs(BALTHAZAR_PROJECTS_DIR)


def balthazar_get_current_project():
    """
    Récupère le chemin du fichier .balthazar actuel
    
    Returns:
        Chemin du fichier .balthazar ou None
    """
    if os.path.exists(BALTHAZAR_CURRENT_PROJECT_FILE):
        try:
            with open(BALTHAZAR_CURRENT_PROJECT_FILE, 'r') as f:
                return f.read().strip()
        except:
            return None
    return None


def balthazar_set_current_project(balthazar_path):
    """
    Définit le projet actuel
    
    Args:
        balthazar_path: Chemin du fichier .balthazar
    """
    try:
        with open(BALTHAZAR_CURRENT_PROJECT_FILE, 'w') as f:
            f.write(balthazar_path)
    except Exception as e:
        st.error(f"❌ Erreur définition projet actuel : {e}")


def balthazar_create_project(name, description, folder_path):
    """
    Crée un nouveau projet au format .balthazar
    
    Args:
        name: Nom du projet
        description: Description du projet
        folder_path: Chemin du dossier source
        
    Returns:
        Chemin du fichier .balthazar créé ou None si erreur
    """
    balthazar_init_workspace()
    
    # Vérifie que le dossier existe
    if not os.path.isdir(folder_path):
        st.error(f"❌ Dossier introuvable : {folder_path}")
        return None
    
    # Nom du fichier .balthazar
    safe_name = name.lower().replace(' ', '_').replace('/', '_')
    balthazar_file = os.path.join(BALTHAZAR_PROJECTS_DIR, f"{safe_name}.balthazar")
    
    # Métadonnées du projet
    project_meta = {
        'format_version': '2.0',
        'name': name,
        'description': description,
        'folder_path': os.path.abspath(folder_path),
        'created_at': datetime.now().isoformat(),
        'last_opened_at': datetime.now().isoformat(),
        'balthazar_version': BALTHAZAR_VERSION,
        'models': {
            'embedding': BALTHAZAR_EMBED_MODEL,
            'llm': BALTHAZAR_LLM_MODEL
        }
    }
    
    # Crée l'archive .balthazar (vide initialement)
    try:
        with zipfile.ZipFile(balthazar_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('project.json', json.dumps(project_meta, indent=2))
            
            # Crée des fichiers vides pour la structure
            zipf.writestr('index.db', '')
            zipf.writestr('metadata.json', json.dumps({}, indent=2))
        
        st.success(f"✅ Projet '{name}' créé : {balthazar_file}")
        return balthazar_file
        
    except Exception as e:
        st.error(f"❌ Erreur création projet : {e}")
        return None


def balthazar_open_project(balthazar_path):
    """
    Ouvre un projet .balthazar et extrait son contenu dans le workspace
    
    Args:
        balthazar_path: Chemin du fichier .balthazar
        
    Returns:
        Dictionnaire de configuration du projet ou None
    """
    if not os.path.exists(balthazar_path):
        st.error(f"❌ Fichier introuvable : {balthazar_path}")
        return None
    
    if not balthazar_path.endswith('.balthazar'):
        st.error("❌ Le fichier doit avoir l'extension .balthazar")
        return None
    
    try:
        # Extrait dans un dossier temporaire
        project_name = os.path.basename(balthazar_path).replace('.balthazar', '')
        extract_dir = os.path.join(BALTHAZAR_PROJECTS_DIR, f".{project_name}_extracted")
        
        # Nettoie l'ancien dossier si existant
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        
        os.makedirs(extract_dir)
        
        # Extrait l'archive
        with zipfile.ZipFile(balthazar_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        # Lit les métadonnées
        with open(os.path.join(extract_dir, 'project.json'), 'r') as f:
            project_meta = json.load(f)
        
        # Met à jour last_opened_at
        project_meta['last_opened_at'] = datetime.now().isoformat()
        
        # Configure les chemins
        project_config = {
            'balthazar_file': balthazar_path,
            'extract_dir': extract_dir,
            'db_path': os.path.join(extract_dir, 'index.db'),
            'metadata_path': os.path.join(extract_dir, 'metadata.json'),
            **project_meta
        }
        
        return project_config
        
    except Exception as e:
        st.error(f"❌ Erreur ouverture projet : {e}")
        return None


def balthazar_save_project(project_config):
    """
    Sauvegarde le projet actuel dans son fichier .balthazar
    
    Args:
        project_config: Configuration du projet
        
    Returns:
        True si succès, False sinon
    """
    try:
        balthazar_file = project_config['balthazar_file']
        extract_dir = project_config['extract_dir']
        
        # Met à jour les métadonnées
        project_meta = {
            'format_version': project_config['format_version'],
            'name': project_config['name'],
            'description': project_config['description'],
            'folder_path': project_config['folder_path'],
            'created_at': project_config['created_at'],
            'last_opened_at': datetime.now().isoformat(),
            'balthazar_version': project_config['balthazar_version'],
            'models': project_config['models']
        }
        
        with open(os.path.join(extract_dir, 'project.json'), 'w') as f:
            json.dump(project_meta, indent=2, fp=f)
        
        # Recrée l'archive
        with zipfile.ZipFile(balthazar_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    zipf.write(file_path, arcname)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde projet : {e}")
        return False


def balthazar_close_project(project_config):
    """
    Ferme un projet (sauvegarde et nettoie)
    
    Args:
        project_config: Configuration du projet
        
    Returns:
        True si succès, False sinon
    """
    # Sauvegarde d'abord
    if not balthazar_save_project(project_config):
        return False
    
    # Nettoie le dossier extrait
    try:
        extract_dir = project_config['extract_dir']
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        return True
    except Exception as e:
        st.warning(f"⚠️ Erreur nettoyage : {e}")
        return False


def balthazar_list_projects():
    """
    Liste tous les fichiers .balthazar dans le workspace
    
    Returns:
        Liste des projets avec leurs métadonnées
    """
    balthazar_init_workspace()
    
    projects = []
    
    for file in os.listdir(BALTHAZAR_PROJECTS_DIR):
        if file.endswith('.balthazar'):
            file_path = os.path.join(BALTHAZAR_PROJECTS_DIR, file)
            
            try:
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    project_meta = json.loads(zipf.read('project.json'))
                    projects.append({
                        'balthazar_file': file_path,
                        **project_meta
                    })
            except Exception as e:
                st.warning(f"⚠️ Erreur lecture {file}: {e}")
    
    # Trie par date de dernière ouverture
    projects.sort(key=lambda x: x.get('last_opened_at', ''), reverse=True)
    
    return projects


def balthazar_delete_project(balthazar_path):
    """
    Supprime un fichier .balthazar
    
    Args:
        balthazar_path: Chemin du fichier .balthazar
        
    Returns:
        True si succès, False sinon
    """
    try:
        if os.path.exists(balthazar_path):
            os.remove(balthazar_path)
            
            # Nettoie aussi le dossier extrait si existant
            project_name = os.path.basename(balthazar_path).replace('.balthazar', '')
            extract_dir = os.path.join(BALTHAZAR_PROJECTS_DIR, f".{project_name}_extracted")
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            
            st.success("✅ Projet supprimé")
            return True
        else:
            st.error("❌ Fichier introuvable")
            return False
    except Exception as e:
        st.error(f"❌ Erreur suppression : {e}")
        return False


def balthazar_export_project(project_config, output_path):
    """
    Exporte le projet vers un nouveau fichier .balthazar
    
    Args:
        project_config: Configuration du projet
        output_path: Chemin de destination
        
    Returns:
        Chemin du fichier créé ou None
    """
    # Sauvegarde d'abord
    if not balthazar_save_project(project_config):
        return None
    
    # Copie le fichier
    try:
        if not output_path.endswith('.balthazar'):
            output_path += '.balthazar'
        
        shutil.copy2(project_config['balthazar_file'], output_path)
        st.success(f"✅ Projet exporté : {output_path}")
        return output_path
        
    except Exception as e:
        st.error(f"❌ Erreur export : {e}")
        return None