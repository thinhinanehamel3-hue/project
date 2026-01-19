#!/usr/bin/env python3
"""
Test d'insertion simple pour vérifier le problème
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

def test_simple_insert():
    """Tester une insertion simple"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("🧪 TEST D'INSERTION SIMPLE")
    print("="*60)
    
    try:
        # 1. Trouver un module sans examen
        cursor.execute("""
            SELECT m.id, m.nom 
            FROM modules m
            WHERE NOT EXISTS (
                SELECT 1 FROM examens_planifies ep 
                WHERE ep.module_id = m.id
            )
            LIMIT 1
        """)
        
        module = cursor.fetchone()
        if not module:
            print("❌ Tous les modules ont déjà un examen")
            return
        
        module_id, module_nom = module
        print(f"Module: {module_nom} (ID: {module_id})")
        
        # 2. Trouver un professeur
        cursor.execute("SELECT id FROM professeurs LIMIT 1")
        prof_id = cursor.fetchone()[0]
        print(f"Professeur: ID {prof_id}")
        
        # 3. Trouver une salle
        cursor.execute("SELECT id FROM lieu_examen WHERE type = 'AMPHI' LIMIT 1")
        salle_id = cursor.fetchone()[0]
        print(f"Salle: ID {salle_id}")
        
        # 4. Insérer SANS triggers
        print("\nTest 1: Insertion SANS triggers...")
        cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER ALL;")
        
        cursor.execute("""
            INSERT INTO examens_planifies 
            (module_id, prof_id, salle_id, date_heure, 
             duree_minutes, mode_generation, statut, priorite)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '1 day', 
                    120, 'MANUEL', 'VALIDE', 1)
            RETURNING id
        """, (module_id, prof_id, salle_id))
        
        examen_id = cursor.fetchone()[0]
        print(f"✅ SUCCÈS! Examen #{examen_id} créé (triggers désactivés)")
        
        # 5. Réactiver les triggers et essayer de supprimer
        print("\nTest 2: Suppression avec triggers...")
        cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER ALL;")
        
        # D'abord supprimer les modifications manuelles
        cursor.execute("DELETE FROM modifications_manuelles WHERE examen_id = %s", (examen_id,))
        
        # Puis supprimer l'examen
        cursor.execute("DELETE FROM examens_planifies WHERE id = %s", (examen_id,))
        print("✅ SUCCÈS! Examen supprimé")
        
        conn.commit()
        print("\n🎯 TEST RÉUSSI: Le problème est dans les triggers!")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    test_simple_insert()