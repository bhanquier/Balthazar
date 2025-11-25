"""
Script de migration pour raccourcir les noms de projets Balthazar
"""
import os
import json
import shutil
import hashlib
from datetime import datetime


def generate_short_id(name):
    """Génère un ID court"""
    timestamp = datetime.now().isoformat()
    hash_input = f"{name}_{timestamp}".encode('utf-8')
    hash_digest = hashlib.md5(hash_input).hexdigest()
    return hash_digest[:8]


def migrate_projects():
    """Migre les anciens projets vers le nouveau format"""
    
    # Fichiers
    projects_file = "balthazar_projects.json"
    projects_dir = "./balthazar_projects"
    
    if not os.path.exists(projects_file):
        print("✅ Aucun projet à migrer")
        return
    
    # Charge les anciens projets
    with open(projects_file, 'r') as f:
        old_projects = json.load(f)
    
    new_projects = {}
    
    print(f"🔄 Migration de {len(old_projects)} projet(s)...")
    
    for old_id, project in old_projects.items():
        # Génère un nouvel ID court
        new_id = generate_short_id(project['name'])
        
        print(f"\n📁 Projet: {project['name']}")
        print(f"   Ancien ID: {old_id}")
        print(f"   Nouvel ID: {new_id}")
        
        # Nouveaux chemins
        new_db_path = os.path.join(projects_dir, f"{new_id}.db")
        new_metadata_path = os.path.join(projects_dir, f"{new_id}_meta.json")
        
        # Copie les anciens fichiers s'ils existent
        if os.path.exists(project['db_path']):
            shutil.copy2(project['db_path'], new_db_path)
            print(f"   ✅ DB copiée: {new_db_path}")
        
        if os.path.exists(project['metadata_path']):
            shutil.copy2(project['metadata_path'], new_metadata_path)
            print(f"   ✅ Métadonnées copiées: {new_metadata_path}")
        
        # Crée le nouveau projet
        new_projects[new_id] = {
            'id': new_id,
            'name': project['name'],
            'description': project.get('description', ''),
            'folder_path': project['folder_path'],
            'created_at': project.get('created_at', datetime.now().isoformat()),
            'last_used_at': project.get('last_used_at', datetime.now().isoformat()),
            'db_path': new_db_path,
            'metadata_path': new_metadata_path
        }
    
    # Sauvegarde les nouveaux projets
    backup_file = f"{projects_file}.backup"
    shutil.copy2(projects_file, backup_file)
    print(f"\n💾 Backup créé: {backup_file}")
    
    with open(projects_file, 'w') as f:
        json.dump(new_projects, indent=2, fp=f)
    
    print(f"\n✅ Migration terminée!")
    print(f"   {len(new_projects)} projet(s) migré(s)")
    print(f"\nVous pouvez maintenant relancer Balthazar:")
    print(f"   streamlit run app.py")


if __name__ == "__main__":
    migrate_projects()