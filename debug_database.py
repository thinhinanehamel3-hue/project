#!/usr/bin/env python3
"""
Script pour déboguer la base de données et vérifier les données
"""

import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
    'port': '5432'
}

def debug_database():
    """Afficher les statistiques de la base pour identifier les problèmes"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("🔍 DÉBOGAGE DE LA BASE DE DONNÉES")
    print("="*60)
    
    # 1. Vérifier le nombre de données dans chaque table
    tables = [
        'departements', 'formations', 'modules', 'etudiants',
        'professeurs', 'lieu_examen', 'creneaux_horaires',
        'inscriptions', 'examens_planifies'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"📊 {table}: {count}")
        except Exception as e:
            print(f"❌ {table}: ERREUR - {e}")
    
    print("\n" + "="*60)
    
    # 2. Vérifier spécifiquement les modules sans examens
    print("\n📚 MODULES SANS EXAMEN:")
    cursor.execute("""
        SELECT COUNT(*) 
        FROM modules m
        WHERE NOT EXISTS (
            SELECT 1 FROM examens_planifies ep 
            WHERE ep.module_id = m.id
        )
    """)
    modules_sans_examen = cursor.fetchone()[0]
    print(f"   Modules disponibles: {modules_sans_examen}")
    
    # 3. Vérifier les salles et leurs capacités
    print("\n🏫 SALLES DISPONIBLES:")
    cursor.execute("""
        SELECT type, COUNT(*), MIN(capacite), MAX(capacite), AVG(capacite)
        FROM lieu_examen 
        GROUP BY type
    """)
    for type_salle, count, min_cap, max_cap, avg_cap in cursor.fetchall():
        print(f"   {type_salle}: {count} salles, capacité: {min_cap}-{max_cap} (moy: {avg_cap:.1f})")
    
    # 4. Vérifier les professeurs par département
    print("\n👨‍🏫 PROFESSEURS PAR DÉPARTEMENT:")
    cursor.execute("""
        SELECT d.nom, COUNT(p.id)
        FROM professeurs p
        JOIN departements d ON p.dept_id = d.id
        GROUP BY d.nom
        ORDER BY COUNT(p.id) DESC
    """)
    for dept, count in cursor.fetchall():
        print(f"   {dept}: {count} professeurs")
    
    # 5. Tester une insertion simple
    print("\n🧪 TEST D'INSERTION SIMPLE:")
    try:
        # Trouver un module sans examen
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
        
        if module:
            module_id, module_nom = module
            print(f"   Module test: {module_nom}")
            
            # Trouver un professeur
            cursor.execute("SELECT id FROM professeurs LIMIT 1")
            prof_id = cursor.fetchone()[0]
            
            # Trouver une salle
            cursor.execute("SELECT id FROM lieu_examen LIMIT 1")
            salle_id = cursor.fetchone()[0]
            
            # Insérer un examen
            cursor.execute("""
                INSERT INTO examens_planifies 
                (module_id, prof_id, salle_id, date_heure, 
                 duree_minutes, mode_generation, statut, priorite)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 120, 'MANUEL', 'VALIDE', 1)
                RETURNING id
            """, (module_id, prof_id, salle_id))
            
            examen_id = cursor.fetchone()[0]
            conn.commit()
            print(f"   ✅ SUCCÈS! Examen #{examen_id} créé")
            
            # Nettoyer le test
            cursor.execute("DELETE FROM examens_planifies WHERE id = %s", (examen_id,))
            conn.commit()
            print(f"   Test nettoyé (examen supprimé)")
        else:
            print("   ❌ Aucun module disponible pour le test")
            
    except Exception as e:
        print(f"   ❌ ÉCHEC du test: {e}")
        conn.rollback()
    
    # 6. Vérifier les triggers
    print("\n⚙️ VÉRIFICATION DES TRIGGERS:")
    try:
        cursor.execute("""
            SELECT trigger_name, event_manipulation, action_statement
            FROM information_schema.triggers
            WHERE event_object_table = 'examens_planifies'
        """)
        triggers = cursor.fetchall()
        if triggers:
            for trigger in triggers:
                print(f"   ✓ {trigger[0]} ({trigger[1]})")
        else:
            print("   ℹ️ Aucun trigger trouvé sur examens_planifies")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    conn.close()
    
    print("\n" + "="*60)
    print("💡 CONSEILS:")
    print("1. Assurez-vous que toutes les tables contiennent des données")
    print("2. Vérifiez que les triggers ne bloquent pas les insertions")
    print("3. Utilisez le mode MANUEL pour contourner les contraintes")
    print("4. Exécutez d'abord le script de génération de données (01_generate_base_data.py)")

if __name__ == "__main__":
    debug_database()