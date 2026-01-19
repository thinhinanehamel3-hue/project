#!/usr/bin/env python3
"""
Script d'urgence pour créer des examens MANUELS
"""

import psycopg2
import random
from datetime import datetime, timedelta

DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
    'port': '5432'
}

def create_emergency_exams(nb_examens=50):
    """Créer des examens en mode MANUEL pour contourner les problèmes"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print(f"🚨 CRÉATION D'URGENCE DE {nb_examens} EXAMENS")
    print("="*60)
    
    try:
        # 1. Désactiver TOUS les triggers
        print("1. Désactivation des triggers...")
        cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER ALL;")
        
        # 2. Récupérer des modules sans examen
        print("2. Récupération des modules...")
        cursor.execute("""
            SELECT m.id, m.nom
            FROM modules m
            WHERE NOT EXISTS (
                SELECT 1 FROM examens_planifies ep 
                WHERE ep.module_id = m.id
            )
            ORDER BY RANDOM()
            LIMIT %s
        """, (nb_examens,))
        
        modules = cursor.fetchall()
        
        if not modules:
            print("❌ Tous les modules ont déjà un examen!")
            return
        
        print(f"   Modules trouvés: {len(modules)}")
        
        # 3. Récupérer des professeurs
        cursor.execute("SELECT id FROM professeurs")
        professeurs = [row[0] for row in cursor.fetchall()]
        
        # 4. Récupérer des salles
        cursor.execute("SELECT id FROM lieu_examen")
        salles = [row[0] for row in cursor.fetchall()]
        
        # 5. Créer les examens
        print("3. Création des examens...")
        succes = 0
        
        for i, (module_id, module_nom) in enumerate(modules):
            try:
                # Choisir aléatoirement
                prof_id = random.choice(professeurs)
                salle_id = random.choice(salles)
                
                # Date dans les 30 prochains jours
                jours = random.randint(1, 30)
                heures = ['08:30', '10:45', '14:00', '16:15']
                heure = random.choice(heures)
                
                date_examen = datetime.now().date() + timedelta(days=jours)
                date_heure = f"{date_examen} {heure}"
                
                # Durée aléatoire
                duree = random.choice([60, 90, 120])
                
                # Insérer en mode MANUEL
                cursor.execute("""
                    INSERT INTO examens_planifies 
                    (module_id, prof_id, salle_id, date_heure, 
                     duree_minutes, mode_generation, statut, priorite, created_at, modifie_par)
                    VALUES (%s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 1, CURRENT_TIMESTAMP, 'emergency_fix')
                """, (module_id, prof_id, salle_id, date_heure, duree))
                
                succes += 1
                
                if succes % 10 == 0:
                    print(f"   {succes} examens créés...")
                    
            except Exception as e:
                print(f"   Erreur module {module_id}: {e}")
                continue
        
        # 6. Réactiver les triggers
        print("4. Réactivation des triggers...")
        cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER ALL;")
        
        # 7. Commit
        conn.commit()
        
        print(f"\n🎯 RÉSULTAT: {succes} examens créés avec succès!")
        
        # 8. Vérification
        cursor.execute("SELECT COUNT(*) FROM examens_planifies")
        total = cursor.fetchone()[0]
        print(f"   Total examens dans la base: {total}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ ERREUR: {e}")
    finally:
        conn.close()

def show_current_exams():
    """Afficher les examens actuels"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("\n📋 EXAMENS ACTUELS:")
    cursor.execute("""
        SELECT COUNT(*), 
               MIN(date_heure), 
               MAX(date_heure),
               COUNT(DISTINCT salle_id),
               COUNT(DISTINCT prof_id)
        FROM examens_planifies
    """)
    
    count, min_date, max_date, salles_utilisees, profs_utilises = cursor.fetchone()
    
    print(f"   Total: {count}")
    if count > 0:
        print(f"   Période: {min_date} à {max_date}")
        print(f"   Salles utilisées: {salles_utilisees}")
        print(f"   Professeurs impliqués: {profs_utilises}")
    
    conn.close()

if __name__ == "__main__":
    # Afficher l'état actuel
    show_current_exams()
    
    # Demander combien d'examens créer
    print("\n" + "="*60)
    nb = input("Combien d'examens voulez-vous créer? (défaut: 50): ")
    
    try:
        nb_examens = int(nb) if nb.strip() else 50
        if nb_examens > 0:
            create_emergency_exams(nb_examens)
            print("\n✅ Opération terminée!")
            print("💡 Lancez maintenant le dashboard pour voir les résultats.")
        else:
            print("❌ Nombre invalide")
    except ValueError:
        print("❌ Entrée invalide, utilisation de la valeur par défaut (50)")
        create_emergency_exams(50)