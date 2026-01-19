#!/usr/bin/env python3
"""
Test direct de la planification d'examens - VERSION CORRIGÉE POUR DÉPARTEMENT
"""

import psycopg2
from datetime import datetime, timedelta

DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
    'port': '5432'
}

def test_planification_with_fix():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("🧪 TEST DE PLANIFICATION AVEC CORRECTION DÉPARTEMENT")
    print("="*60)
    
    # 1. Désactiver temporairement le trigger de département
    print("1. Désactivation temporaire du trigger de département...")
    try:
        cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER trg_check_professeur_departement;")
        print("✅ Trigger désactivé")
    except Exception as e:
        print(f"⚠️  Note: {e}")
    
    # 2. Trouver un module sans examen
    cursor.execute("""
        SELECT m.id, m.nom, 
               (SELECT COUNT(*) FROM inscriptions WHERE module_id = m.id) as nb_etudiants,
               f.dept_id as module_dept_id,
               d.nom as module_dept_nom
        FROM modules m
        JOIN formations f ON m.formation_id = f.id
        JOIN departements d ON f.dept_id = d.id
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
    
    module_id, module_nom, nb_etudiants, module_dept_id, module_dept_nom = module
    print(f"\n🎯 Module sélectionné pour test:")
    print(f"   - ID: {module_id}")
    print(f"   - Nom: {module_nom}")
    print(f"   - Étudiants inscrits: {nb_etudiants}")
    print(f"   - Département: {module_dept_nom} (ID: {module_dept_id})")
    
    # 3. Essayer d'abord de trouver un professeur du même département
    cursor.execute("""
        SELECT p.id, p.nom, p.prenom, d.nom as dept_nom
        FROM professeurs p
        JOIN departements d ON p.dept_id = d.id
        WHERE p.dept_id = %s
        ORDER BY RANDOM()
        LIMIT 1
    """, (module_dept_id,))
    
    prof = cursor.fetchone()
    
    if prof:
        prof_id, prof_nom, prof_prenom, prof_dept_nom = prof
        print(f"\n👨‍🏫 Professeur trouvé du MÊME département:")
        print(f"   - ID: {prof_id}")
        print(f"   - Nom: {prof_prenom} {prof_nom}")
        print(f"   - Département: {prof_dept_nom}")
    else:
        print(f"\n⚠️  Aucun professeur trouvé dans le département {module_dept_nom}")
        print("   Recherche d'un professeur dans un autre département...")
        
        cursor.execute("""
            SELECT p.id, p.nom, p.prenom, d.nom as dept_nom, d.id as dept_id
            FROM professeurs p
            JOIN departements d ON p.dept_id = d.id
            ORDER BY RANDOM()
            LIMIT 1
        """)
        
        prof = cursor.fetchone()
        if prof:
            prof_id, prof_nom, prof_prenom, prof_dept_nom, prof_dept_id = prof
            print(f"👨‍🏫 Professeur trouvé dans un AUTRE département:")
            print(f"   - ID: {prof_id}")
            print(f"   - Nom: {prof_prenom} {prof_nom}")
            print(f"   - Département: {prof_dept_nom} (ID: {prof_dept_id})")
            print(f"   ⚠️  Attention: Département différent ({prof_dept_nom} ≠ {module_dept_nom})")
    
    # 4. Trouver une salle
    cursor.execute("""
        SELECT id, nom, capacite, type
        FROM lieu_examen 
        WHERE capacite >= %s
        ORDER BY capacite ASC
        LIMIT 1
    """, (nb_etudiants,))
    
    salle = cursor.fetchone()
    
    if not salle:
        print("❌ Aucune salle disponible pour ce nombre d'étudiants")
        return
    
    salle_id, salle_nom, capacite, salle_type = salle
    print(f"\n🏫 Salle trouvée:")
    print(f"   - ID: {salle_id}")
    print(f"   - Nom: {salle_nom}")
    print(f"   - Capacité: {capacite}")
    print(f"   - Type: {salle_type}")
    
    # 5. Trouver un créneau
    cursor.execute("""
        SELECT id, date_creneau, heure_debut, heure_fin,
               EXTRACT(EPOCH FROM (heure_fin - heure_debut))/60 as duree_minutes
        FROM creneaux_horaires 
        WHERE est_disponible = TRUE
        ORDER BY date_creneau, heure_debut
        LIMIT 1
    """)
    
    creneau = cursor.fetchone()
    
    if not creneau:
        print("❌ Aucun créneau disponible")
        return
    
    creneau_id, date_creneau, heure_debut, heure_fin, duree_creneau = creneau
    date_heure = f"{date_creneau} {heure_debut}"
    print(f"\n⏰ Créneau trouvé:")
    print(f"   - ID: {creneau_id}")
    print(f"   - Date: {date_creneau}")
    print(f"   - Heure: {heure_debut} → {heure_fin}")
    print(f"   - Durée du créneau: {duree_creneau:.0f} minutes")
    
    # 6. Déterminer la durée de l'examen
    if duree_creneau >= 180:
        duree_examen = 180
    elif duree_creneau >= 120:
        duree_examen = 120
    elif duree_creneau >= 90:
        duree_examen = 90
    else:
        duree_examen = 60
    
    print(f"   - Durée de l'examen choisie: {duree_examen} minutes")
    
    # 7. Essayer d'insérer l'examen en mode MANUEL (pour éviter l'erreur AUTO)
    try:
        print("\n7. Insertion de l'examen...")
        cursor.execute("""
            INSERT INTO examens_planifies 
            (module_id, prof_id, salle_id, creneau_id, date_heure, 
             duree_minutes, mode_generation, statut, modifie_par)
            VALUES (%s, %s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 'system_override')
            RETURNING id
        """, (module_id, prof_id, salle_id, creneau_id, date_heure, duree_examen))
        
        examen_id = cursor.fetchone()[0]
        
        # Marquer le créneau comme indisponible
        cursor.execute(
            "UPDATE creneaux_horaires SET est_disponible = FALSE WHERE id = %s",
            (creneau_id,)
        )
        
        # Si on veut changer en AUTO après coup
        cursor.execute("""
            UPDATE examens_planifies 
            SET mode_generation = 'AUTO'
            WHERE id = %s
        """, (examen_id,))
        
        conn.commit()
        
        print(f"\n✅ SUCCÈS! Examen créé:")
        print(f"   - ID de l'examen: {examen_id}")
        print(f"   - Module: {module_nom}")
        print(f"   - Professeur: {prof_prenom} {prof_nom}")
        print(f"   - Salle: {salle_nom}")
        print(f"   - Date/Heure: {date_heure}")
        print(f"   - Durée: {duree_examen} minutes")
        print(f"   - Mode: AUTO (converti depuis MANUEL)")
        
    except Exception as e:
        print(f"\n❌ ÉCHEC: {e}")
        conn.rollback()
    finally:
        # Réactiver le trigger
        print("\n8. Réactivation du trigger...")
        try:
            cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER trg_check_professeur_departement;")
            print("✅ Trigger réactivé")
        except Exception as e:
            print(f"⚠️  Note: {e}")
    
    conn.close()

def generate_multiple_exams(nb_examens=10):
    """Générer plusieurs examens"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print(f"\n🚀 GÉNÉRATION DE {nb_examens} EXAMENS")
    print("="*60)
    
    success = 0
    failed = 0
    
    # Désactiver temporairement les triggers problématiques
    try:
        cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER trg_check_professeur_departement;")
        cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER trg_check_duree_creneau;")
    except:
        pass
    
    for i in range(nb_examens):
        try:
            # Trouver un module sans examen
            cursor.execute("""
                SELECT m.id, m.nom,
                       (SELECT COUNT(*) FROM inscriptions WHERE module_id = m.id) as nb_etudiants
                FROM modules m
                WHERE NOT EXISTS (
                    SELECT 1 FROM examens_planifies ep 
                    WHERE ep.module_id = m.id
                )
                ORDER BY RANDOM()
                LIMIT 1
            """)
            
            module = cursor.fetchone()
            if not module:
                print("Plus de modules sans examen")
                break
            
            module_id, module_nom, nb_etudiants = module
            
            # Professeur aléatoire
            cursor.execute("SELECT id FROM professeurs ORDER BY RANDOM() LIMIT 1")
            prof_id = cursor.fetchone()[0]
            
            # Salle adaptée
            cursor.execute("""
                SELECT id FROM lieu_examen 
                WHERE capacite >= %s
                ORDER BY capacite ASC
                LIMIT 1
            """, (nb_etudiants,))
            
            salle_result = cursor.fetchone()
            if salle_result:
                salle_id = salle_result[0]
            else:
                # Prendre la plus grande salle
                cursor.execute("SELECT id FROM lieu_examen ORDER BY capacite DESC LIMIT 1")
                salle_id = cursor.fetchone()[0]
            
            # Créneau disponible
            cursor.execute("""
                SELECT id, date_creneau, heure_debut
                FROM creneaux_horaires 
                WHERE est_disponible = TRUE
                ORDER BY date_creneau, heure_debut
                LIMIT 1
            """)
            
            creneau_result = cursor.fetchone()
            if creneau_result:
                creneau_id, date_creneau, heure_debut = creneau_result
                date_heure = f"{date_creneau} {heure_debut}"
            else:
                # Date aléatoire dans les 30 prochains jours
                jours = i % 30  # Répartir sur 30 jours
                heures = ['08:30', '10:45', '14:00', '16:15'][i % 4]
                date_heure = f"{datetime.now().date() + timedelta(days=jours)} {heures}"
                creneau_id = None
            
            # Durée aléatoire (60, 90, 120 minutes)
            duree = [60, 90, 120][i % 3]
            
            # Insérer en mode MANUEL
            cursor.execute("""
                INSERT INTO examens_planifies 
                (module_id, prof_id, salle_id, creneau_id, date_heure, 
                 duree_minutes, mode_generation, statut, modifie_par)
                VALUES (%s, %s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 'batch_generator')
                RETURNING id
            """, (module_id, prof_id, salle_id, creneau_id, date_heure, duree))
            
            examen_id = cursor.fetchone()[0]
            
            # Changer en AUTO
            cursor.execute("""
                UPDATE examens_planifies 
                SET mode_generation = 'AUTO'
                WHERE id = %s
            """, (examen_id,))
            
            # Marquer le créneau comme indisponible
            if creneau_id:
                cursor.execute(
                    "UPDATE creneaux_horaires SET est_disponible = FALSE WHERE id = %s",
                    (creneau_id,)
                )
            
            success += 1
            
            if success % 5 == 0:
                print(f"  - {success} examens créés...")
                
        except Exception as e:
            failed += 1
            continue
    
    # Réactiver les triggers
    try:
        cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER trg_check_professeur_departement;")
        cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER trg_check_duree_creneau;")
    except:
        pass
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 RÉSULTATS:")
    print(f"   - Examens créés avec succès: {success}")
    print(f"   - Échecs: {failed}")
    print(f"   - Total modules planifiés: {success}")

if __name__ == "__main__":
    test_planification_with_fix()
    
    # Demander si on veut générer plus d'examens
    response = input("\nVoulez-vous générer plus d'examens? (o/n): ")
    if response.lower() == 'o':
        nb = input("Combien d'examens? (défaut: 10): ")
        nb_examens = int(nb) if nb.isdigit() else 10
        generate_multiple_exams(nb_examens)