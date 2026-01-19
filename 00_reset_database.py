#!/usr/bin/env python3
"""
Script pour réinitialiser complètement la base de données
Supprime tous les examens planifiés et réactive les créneaux
"""

import psycopg2
import sys

DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
    'port': '5432'
}

def reset_database():
    """Réinitialiser complètement les examens"""
    print("🔄 RÉINITIALISATION DE LA BASE DE DONNÉES")
    print("="*60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Réactiver tous les créneaux
        cursor.execute("UPDATE creneaux_horaires SET est_disponible = TRUE")
        print("✅ Créneaux horaires réactivés")
        
        # 2. Supprimer toutes les modifications manuelles
        cursor.execute("DELETE FROM modifications_manuelles")
        print("✅ Modifications manuelles supprimées")
        
        # 3. Supprimer tous les examens planifiés
        cursor.execute("DELETE FROM examens_planifies")
        print("✅ Examens planifiés supprimés")
        
        # 4. Vérifier les statistiques
        cursor.execute("SELECT COUNT(*) FROM examens_planifies")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("\n🎯 BASE RÉINITIALISÉE AVEC SUCCÈS!")
            print(f"✅ Examens restants: {count}")
        else:
            print(f"⚠️  Attention: {count} examens restants")
        
        conn.commit()
        conn.close()
        
        print("\n💡 La base est maintenant prête pour une nouvelle planification.")
        print("   Exécutez '04_dashboard_streamlit.py' pour générer de nouveaux examens.")
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    confirm = input("Êtes-vous sûr de vouloir réinitialiser tous les examens? (o/n): ")
    if confirm.lower() == 'o':
        reset_database()
    else:
        print("❌ Opération annulée")