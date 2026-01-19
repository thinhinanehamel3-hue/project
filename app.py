

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import psycopg2
import numpy as np
import random
import time

# Configuration de la page
st.set_page_config(
    page_title="Plateforme d'Examens Universitaires",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration de la base de données
DB_CONFIG = {
    'host': 'dpg-d5mp9675r7bs73da5utg-a.frankfurt-postgres.render.com',
    'database': 'mydb_lubi',
    'user': 'mydb_lubi_user',
    'password': 'IdVcFHisd27xyAS6bJgkz1pv53xcdA7u',
    'port': '5432'
}

def get_connection():
    """Établir une connexion à la base de données"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Erreur de connexion à la base de données: {e}")
        return None

class ExamPlatform:
    def __init__(self):
        self.conn = get_connection()
        if self.conn:
            # CRITIQUE: Autocommit activé pour éviter les erreurs de transaction
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
        else:
            self.cursor = None
    
    def safe_execute(self, query, params=None):
        """Exécuter une requête SQL avec gestion d'erreur"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return True, None
        except Exception as e:
            return False, str(e)
    
    # ==================== FONCTIONS DE BASE ====================
    
    def get_departments(self):
        """Récupérer tous les départements"""
        success, error = self.safe_execute("SELECT id, nom FROM departements ORDER BY nom")
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def get_formations_by_department(self, dept_id):
        """Récupérer les formations d'un département"""
        success, error = self.safe_execute(
            "SELECT id, nom FROM formations WHERE dept_id = %s ORDER BY nom",
            (dept_id,)
        )
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def get_modules_by_formation(self, formation_id):
        """Récupérer les modules d'une formation"""
        success, error = self.safe_execute(
            "SELECT id, nom FROM modules WHERE formation_id = %s ORDER BY nom",
            (formation_id,)
        )
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def get_all_professeurs(self):
        """Récupérer tous les professeurs"""
        success, error = self.safe_execute(
            "SELECT id, CONCAT(prenom, ' ', nom) as nom_complet, dept_id FROM professeurs ORDER BY nom"
        )
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def get_all_salles(self):
        """Récupérer toutes les salles"""
        success, error = self.safe_execute(
            "SELECT id, nom, type, capacite FROM lieu_examen ORDER BY type, nom"
        )
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def get_modules_sans_examen(self):
        """Récupérer les modules sans examen"""
        success, error = self.safe_execute("""
            SELECT m.id, m.nom, f.nom as formation, d.nom as departement
            FROM modules m
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            WHERE NOT EXISTS (
                SELECT 1 FROM examens_planifies ep 
                WHERE ep.module_id = m.id
            )
            ORDER BY m.nom
        """)
        if success:
            return self.cursor.fetchall()
        else:
            return []
    
    def check_initial_state(self):
        """Vérifier l'état initial"""
        success, error = self.safe_execute("SELECT COUNT(*) FROM examens_planifies")
        if success:
            count = self.cursor.fetchone()[0]
            return count == 0
        return False
    
    def reset_all_exams(self):
        """Réinitialiser tous les examens"""
        try:
            success, error = self.safe_execute("SELECT 1 FROM examens_planifies LIMIT 1")
            if not success:
                return True, "Table déjà vide"
            
            try:
                success, error = self.safe_execute("TRUNCATE TABLE examens_planifies CASCADE")
                if success:
                    return True, "Tous les examens ont été réinitialisés"
            except:
                success, error = self.safe_execute("DELETE FROM examens_planifies")
                if success:
                    return True, "Tous les examens ont été réinitialisés"
                else:
                    return False, f"Erreur DELETE: {error}"
            
            return True, "Réinitialisation réussie"
            
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    def count_conflicts(self):
        """Compter les conflits"""
        try:
            success, error = self.safe_execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT e1.id
                    FROM examens_planifies e1
                    JOIN examens_planifies e2 ON e1.id != e2.id
                    WHERE e1.salle_id = e2.salle_id 
                    AND e1.date_heure = e2.date_heure
                    AND e1.statut IN ('PROPOSE', 'VALIDE') AND e2.statut IN ('PROPOSE', 'VALIDE')
                ) as conflits
            """)
            if success:
                return self.cursor.fetchone()[0]
        except:
            pass
        return 0
    
    def get_conflicts_details(self):
        """Récupérer les détails des conflits"""
        try:
            success, error = self.safe_execute("""
                SELECT DISTINCT
                    e1.id as id1, 
                    e2.id as id2,
                    l.nom as salle,
                    e1.date_heure as date_heure,
                    m1.nom as module1,
                    m2.nom as module2,
                    d1.nom as departement1,
                    d2.nom as departement2
                FROM examens_planifies e1
                JOIN examens_planifies e2 ON e1.id < e2.id
                JOIN lieu_examen l ON e1.salle_id = l.id
                JOIN modules m1 ON e1.module_id = m1.id
                JOIN modules m2 ON e2.module_id = m2.id
                JOIN formations f1 ON m1.formation_id = f1.id
                JOIN formations f2 ON m2.formation_id = f2.id
                JOIN departements d1 ON f1.dept_id = d1.id
                JOIN departements d2 ON f2.dept_id = d2.id
                WHERE e1.salle_id = e2.salle_id 
                AND e1.date_heure = e2.date_heure
                AND e1.statut IN ('PROPOSE', 'VALIDE') AND e2.statut IN ('PROPOSE', 'VALIDE')
                ORDER BY e1.date_heure
                LIMIT 20
            """)
            
            if success:
                conflicts = self.cursor.fetchall()
                if conflicts:
                    columns = ['Examen1', 'Examen2', 'Salle', 'Date/Heure', 'Module1', 'Module2', 'Département1', 'Département2']
                    return pd.DataFrame(conflicts, columns=columns)
        except Exception as e:
            st.error(f"Erreur détails conflits: {e}")
        
        return pd.DataFrame()
    
    # ==================== GÉNÉRATION AUTO (VERSION SIMPLIFIÉE QUI FONCTIONNE) ====================
    
    def generate_simple_timetable(self, nb_examens=30, duree_minutes=120):
        """
        Générer un emploi du temps SIMPLE qui fonctionne
        """
        start_time = time.time()
        
        try:
            # 1. Récupérer les modules disponibles
            success, error = self.safe_execute("""
                SELECT id, nom FROM modules 
                ORDER BY RANDOM() 
                LIMIT %s
            """, (nb_examens,))
            
            if not success:
                return False, f"Erreur modules: {error}", 0, {}
            
            modules = self.cursor.fetchall()
            
            if not modules:
                return False, "Aucun module disponible", 0, {}
            
            # 2. Récupérer les salles
            success, error = self.safe_execute("SELECT id, nom FROM lieu_examen ORDER BY RANDOM() LIMIT 10")
            if not success:
                return False, "Erreur salles", 0, {}
            salles = self.cursor.fetchall()
            
            # 3. Récupérer les professeurs
            success, error = self.safe_execute("SELECT id FROM professeurs ORDER BY RANDOM() LIMIT 20")
            if not success:
                return False, "Erreur professeurs", 0, {}
            professeurs = self.cursor.fetchall()
            
            # 4. Générer des dates (prochaines 2 semaines)
            dates = []
            for i in range(1, 15):
                date_base = datetime.now().date() + timedelta(days=i)
                if date_base.weekday() < 5:  # Lundi-Vendredi
                    dates.append(f"{date_base} 08:30:00")
                    dates.append(f"{date_base} 14:00:00")
            
            if not dates:
                dates = [f"{datetime.now().date() + timedelta(days=1)} 08:30:00"]
            
            succes_count = 0
            echecs_count = 0
            echecs_details = []
            
            # 5. Insérer les examens UN PAR UN pour éviter les erreurs en bloc
            for i, module in enumerate(modules[:nb_examens]):
                module_id, module_nom = module
                
                try:
                    # Choisir des valeurs aléatoires
                    salle_id = random.choice(salles)[0]
                    prof_id = random.choice(professeurs)[0]
                    date_heure = random.choice(dates)
                    
                    # ESSAYER PLUSIEURS MÉTHODES D'INSERTION
                    
                    # Méthode 1: Sans creneau_id, mode MANUEL
                    try:
                        insert_query = """
                        INSERT INTO examens_planifies 
                        (module_id, prof_id, salle_id, date_heure, duree_minutes, 
                         mode_generation, statut, priorite)
                        VALUES (%s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 1)
                        """
                        self.cursor.execute(insert_query, (module_id, prof_id, salle_id, date_heure, duree_minutes))
                        succes_count += 1
                        continue
                    except Exception as e1:
                        pass
                    
                    # Méthode 2: Avec mode AUTO et creneau_id NULL
                    try:
                        insert_query = """
                        INSERT INTO examens_planifies 
                        (module_id, prof_id, salle_id, date_heure, duree_minutes, 
                         mode_generation, statut, priorite, creneau_id)
                        VALUES (%s, %s, %s, %s, %s, 'AUTO', 'VALIDE', 1, NULL)
                        """
                        self.cursor.execute(insert_query, (module_id, prof_id, salle_id, date_heure, duree_minutes))
                        succes_count += 1
                        continue
                    except Exception as e2:
                        pass
                    
                    # Méthode 3: Avec toutes les colonnes possibles
                    try:
                        insert_query = """
                        INSERT INTO examens_planifies 
                        (module_id, prof_id, salle_id, date_heure, duree_minutes, 
                         mode_generation, statut, priorite, modifie_par)
                        VALUES (%s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 1, 'system')
                        """
                        self.cursor.execute(insert_query, (module_id, prof_id, salle_id, date_heure, duree_minutes))
                        succes_count += 1
                        continue
                    except Exception as e3:
                        echecs_count += 1
                        echecs_details.append(f"{module_nom[:30]}: toutes les méthodes ont échoué")
                        
                except Exception as e:
                    echecs_count += 1
                    echecs_details.append(f"{module_nom[:30]}: {str(e)[:100]}")
                    continue
            
            end_time = time.time()
            temps_execution = round(end_time - start_time, 2)
            
            details = {
                'modules_disponibles': len(modules),
                'examens_planifies': succes_count,
                'echecs': echecs_count,
                'taux_reussite': (succes_count / len(modules)) * 100 if modules else 0,
                'temps_execution': temps_execution,
                'echecs_details': echecs_details[:5]
            }
            
            if succes_count > 0:
                return True, f"{succes_count} examens planifiés", temps_execution, details
            else:
                error_msg = echecs_details[0] if echecs_details else "Erreur inconnue"
                return False, f"Échec: {error_msg}", temps_execution, details
            
        except Exception as e:
            error_msg = str(e)
            return False, f"Erreur système: {error_msg}", 0, {}
    
    # ==================== AJOUT MANUEL ====================
    
    def add_manual_exam(self, module_id, prof_id, salle_id, date_heure, duree_minutes):
        """Ajouter un examen manuellement"""
        try:
            # Vérifier si le module a déjà un examen
            success, error = self.safe_execute(
                "SELECT COUNT(*) FROM examens_planifies WHERE module_id = %s",
                (module_id,)
            )
            if success and self.cursor.fetchone()[0] > 0:
                return False, "Ce module a déjà un examen planifié"
            
            # Vérifier si la salle est disponible à cette heure
            success, error = self.safe_execute("""
                SELECT COUNT(*) FROM examens_planifies 
                WHERE salle_id = %s AND date_heure = %s AND statut IN ('PROPOSE', 'VALIDE')
            """, (salle_id, date_heure))
            
            if success and self.cursor.fetchone()[0] > 0:
                return False, "La salle n'est pas disponible à cette heure"
            
            # Insérer l'examen
            success, error = self.safe_execute("""
                INSERT INTO examens_planifies 
                (module_id, prof_id, salle_id, date_heure, 
                 duree_minutes, mode_generation, statut, priorite)
                VALUES (%s, %s, %s, %s, %s, 'MANUEL', 'VALIDE', 1)
                RETURNING id
            """, (module_id, prof_id, salle_id, date_heure, duree_minutes))
            
            if success:
                examen_id = self.cursor.fetchone()[0]
                return True, f"Examen ajouté avec succès (ID: {examen_id})"
            else:
                return False, f"Erreur d'insertion: {error}"
                
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    # ==================== OPTIMISATION ====================
    
    def optimize_timetable(self, mode='RAPIDE'):
        """Optimiser l'emploi du temps"""
        start_time = time.time()
        
        try:
            conflits_avant = self.count_conflicts()
            
            if conflits_avant == 0:
                return True, "Aucun conflit à résoudre", 0
            
            conflicts = self.get_conflicts_details()
            
            if conflicts.empty:
                return True, "Aucun conflit détecté", 0
            
            conflits_resolus = 0
            
            for idx, conflit in conflicts.iterrows():
                examen_id = conflit['Examen1']
                date_actuelle = conflit['Date/Heure']
                
                try:
                    date_obj = datetime.strptime(str(date_actuelle), '%Y-%m-%d %H:%M:%S')
                    nouvelle_date = date_obj + timedelta(days=2)
                    nouvelle_date_str = nouvelle_date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    success, error = self.safe_execute("""
                        SELECT COUNT(*) FROM examens_planifies 
                        WHERE salle_id = (
                            SELECT salle_id FROM examens_planifies WHERE id = %s
                        )
                        AND date_heure = %s
                        AND statut IN ('PROPOSE', 'VALIDE')
                    """, (examen_id, nouvelle_date_str))
                    
                    if success and self.cursor.fetchone()[0] == 0:
                        success, error = self.safe_execute("""
                            UPDATE examens_planifies 
                            SET date_heure = %s,
                                modifie_par = 'optimizer'
                            WHERE id = %s
                        """, (nouvelle_date_str, examen_id))
                        
                        if success:
                            conflits_resolus += 1
                except:
                    continue
            
            end_time = time.time()
            temps_execution = round(end_time - start_time, 2)
            
            conflits_apres = self.count_conflicts()
            
            message = f"Optimisation terminée en {temps_execution}s\n"
            message += f"Conflits résolus: {conflits_resolus}\n"
            message += f"Conflits restants: {conflits_apres}"
            
            return True, message, temps_execution
            
        except Exception as e:
            return False, f"Erreur: {str(e)[:200]}", 0
    
    # ==================== FONCTIONS DE DONNÉES POUR DASHBOARDS ====================
    
    def get_generated_timetable(self, limit=500):
        """Récupérer l'emploi du temps"""
        success, error = self.safe_execute("""
            SELECT 
                ep.id as examen_id,
                ep.date_heure,
                m.nom as module,
                f.nom as formation,
                d.nom as departement,
                CONCAT(p.prenom, ' ', p.nom) as professeur,
                l.nom as salle,
                ep.duree_minutes,
                ep.mode_generation,
                ep.statut
            FROM examens_planifies ep
            LEFT JOIN modules m ON ep.module_id = m.id
            LEFT JOIN formations f ON m.formation_id = f.id
            LEFT JOIN departements d ON f.dept_id = d.id
            LEFT JOIN professeurs p ON ep.prof_id = p.id
            LEFT JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
            ORDER BY ep.date_heure
            LIMIT %s
        """, (limit,))
        
        if success:
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        else:
            return pd.DataFrame()
    
    def get_timetable_statistics(self):
        """Statistiques"""
        stats = {}
        
        success, error = self.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut IN ('PROPOSE', 'VALIDE')")
        if success:
            stats['total_examens'] = self.cursor.fetchone()[0]
        
        success, error = self.safe_execute("""
            SELECT DATE(date_heure) as jour, COUNT(*) 
            FROM examens_planifies 
            WHERE statut IN ('PROPOSE', 'VALIDE')
            GROUP BY DATE(date_heure)
            ORDER BY DATE(date_heure)
        """)
        if success:
            data = self.cursor.fetchall()
            if data:
                stats['examens_par_jour'] = pd.DataFrame(data, columns=['Date', 'Examens'])
        
        success, error = self.safe_execute("""
            SELECT d.nom, COUNT(ep.id) 
            FROM examens_planifies ep
            LEFT JOIN modules m ON ep.module_id = m.id
            LEFT JOIN formations f ON m.formation_id = f.id
            LEFT JOIN departements d ON f.dept_id = d.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
            GROUP BY d.nom
            HAVING d.nom IS NOT NULL
            ORDER BY COUNT(ep.id) DESC
        """)
        if success:
            data = self.cursor.fetchall()
            if data:
                stats['repartition_par_departement'] = pd.DataFrame(data, columns=['Département', 'Examens'])
        
        return stats
    
    # ==================== FONCTIONS SPÉCIFIQUES AUX RÔLES ====================
    
    def get_student_exams(self, filters=None):
        """Récupérer les examens pour un étudiant"""
        query = """
            SELECT 
                ep.date_heure,
                m.nom as module,
                f.nom as formation,
                d.nom as departement,
                l.nom as salle,
                CONCAT(p.prenom, ' ', p.nom) as professeur,
                ep.duree_minutes
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN professeurs p ON ep.prof_id = p.id
            JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
        """
        
        params = []
        
        if filters:
            if 'departement' in filters and filters['departement'] != 'Tous':
                query += " AND d.nom = %s"
                params.append(filters['departement'])
            
            if 'formation' in filters and filters['formation'] != 'Toutes':
                query += " AND f.nom = %s"
                params.append(filters['formation'])
            
            if 'date_debut' in filters:
                query += " AND ep.date_heure >= %s"
                params.append(filters['date_debut'])
            
            if 'date_fin' in filters:
                query += " AND ep.date_heure <= %s"
                params.append(filters['date_fin'])
        
        query += " ORDER BY ep.date_heure"
        
        success, error = self.safe_execute(query, params)
        
        if success:
            exams = self.cursor.fetchall()
            columns = ['Date/Heure', 'Module', 'Formation', 'Département', 'Salle', 'Professeur', 'Durée (min)']
            return pd.DataFrame(exams, columns=columns)
        else:
            return pd.DataFrame()
    
    def get_teacher_exams(self, teacher_name=None):
        """Récupérer les examens pour un professeur"""
        query = """
            SELECT 
                ep.date_heure,
                m.nom as module,
                d.nom as departement,
                l.nom as salle,
                ep.duree_minutes
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
        """
        
        params = []
        
        if teacher_name:
            query += " AND ep.prof_id IN (SELECT id FROM professeurs WHERE CONCAT(prenom, ' ', nom) = %s)"
            params.append(teacher_name)
        
        query += " ORDER BY ep.date_heure"
        
        success, error = self.safe_execute(query, params)
        
        if success:
            exams = self.cursor.fetchall()
            columns = ['Date/Heure', 'Module', 'Département', 'Salle', 'Durée (min)']
            return pd.DataFrame(exams, columns=columns)
        else:
            return pd.DataFrame()
    
    def get_department_exams(self, dept_name):
        """Récupérer les examens d'un département"""
        query = """
            SELECT 
                ep.date_heure,
                m.nom as module,
                f.nom as formation,
                CONCAT(p.prenom, ' ', p.nom) as professeur,
                l.nom as salle,
                ep.duree_minutes,
                ep.mode_generation
            FROM examens_planifiques ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN professeurs p ON ep.prof_id = p.id
            JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
            AND d.nom = %s
            ORDER BY ep.date_heure
        """
        
        success, error = self.safe_execute(query, (dept_name,))
        
        if success:
            exams = self.cursor.fetchall()
            columns = ['Date/Heure', 'Module', 'Formation', 'Professeur', 'Salle', 'Durée', 'Mode']
            return pd.DataFrame(exams, columns=columns)
        else:
            return pd.DataFrame()
    
    def get_room_occupation_stats(self):
        """Statistiques d'occupation des salles"""
        try:
            success, error = self.safe_execute("""
                SELECT 
                    l.type,
                    COUNT(DISTINCT l.id) as nb_salles,
                    COUNT(ep.id) as nb_examens,
                    CASE 
                        WHEN COUNT(DISTINCT l.id) * 20 > 0 
                        THEN ROUND(COUNT(ep.id) * 100.0 / (COUNT(DISTINCT l.id) * 20), 1)
                        ELSE 0
                    END as taux_occupation
                FROM lieu_examen l
                LEFT JOIN examens_planifies ep ON l.id = ep.salle_id AND ep.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY l.type
                ORDER BY l.type
            """)
            
            if success:
                data = self.cursor.fetchall()
                df = pd.DataFrame(data, 
                                 columns=['Type', 'Nb Salles', 'Nb Examens', 'Taux Occupation (%)'])
                # Conversion en numérique
                df['Taux Occupation (%)'] = pd.to_numeric(df['Taux Occupation (%)'], errors='coerce')
                df['Nb Salles'] = pd.to_numeric(df['Nb Salles'], errors='coerce')
                df['Nb Examens'] = pd.to_numeric(df['Nb Examens'], errors='coerce')
                return df
        except Exception as e:
            st.error(f"Erreur occupation salles: {e}")
        return pd.DataFrame()
    
    def get_detailed_room_occupation(self):
        """Occupation détaillée par salle"""
        try:
            success, error = self.safe_execute("""
                SELECT 
                    l.nom as salle,
                    l.type,
                    l.capacite,
                    COUNT(ep.id) as nb_examens,
                    CASE 
                        WHEN SUM(ep.duree_minutes) IS NOT NULL 
                        THEN SUM(ep.duree_minutes) / 60.0
                        ELSE 0
                    END as total_heures,
                    CASE 
                        WHEN 20 > 0 
                        THEN ROUND(COUNT(ep.id) * 100.0 / 20, 1)
                        ELSE 0
                    END as taux_occupation
                FROM lieu_examen l
                LEFT JOIN examens_planifies ep ON l.id = ep.salle_id AND ep.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY l.id, l.nom, l.type, l.capacite
                ORDER BY l.type, taux_occupation DESC
            """)
            
            if success:
                data = self.cursor.fetchall()
                df = pd.DataFrame(data,
                                  columns=['Salle', 'Type', 'Capacité', 'Examens', 'Heures', 'Taux Occupation (%)'])
                # Conversion en numérique
                df['Taux Occupation (%)'] = pd.to_numeric(df['Taux Occupation (%)'], errors='coerce')
                df['Heures'] = pd.to_numeric(df['Heures'], errors='coerce')
                df['Examens'] = pd.to_numeric(df['Examens'], errors='coerce')
                df['Capacité'] = pd.to_numeric(df['Capacité'], errors='coerce')
                return df
        except Exception as e:
            st.error(f"Erreur occupation détaillée: {e}")
        return pd.DataFrame()
    
    def get_professor_workload(self):
        """Charge de travail des professeurs"""
        try:
            success, error = self.safe_execute("""
                SELECT 
                    CONCAT(p.prenom, ' ', p.nom) as professeur,
                    d.nom as departement,
                    COUNT(ep.id) as nb_examens,
                    CASE 
                        WHEN SUM(ep.duree_minutes) IS NOT NULL 
                        THEN SUM(ep.duree_minutes) / 60.0
                        ELSE 0
                    END as total_heures,
                    CASE 
                        WHEN COUNT(ep.id) > 0 
                        THEN ROUND(AVG(ep.duree_minutes), 0)
                        ELSE 0
                    END as duree_moyenne_min
                FROM professeurs p
                JOIN examens_planifies ep ON p.id = ep.prof_id
                JOIN departements d ON p.dept_id = d.id
                WHERE ep.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY p.id, p.prenom, p.nom, d.nom
                ORDER BY total_heures DESC
                LIMIT 50
            """)
            
            if success:
                data = self.cursor.fetchall()
                df = pd.DataFrame(data,
                                  columns=['Professeur', 'Département', 'Examens', 'Heures Total', 'Durée Moyenne (min)'])
                # Conversion en numérique
                df['Heures Total'] = pd.to_numeric(df['Heures Total'], errors='coerce')
                df['Examens'] = pd.to_numeric(df['Examens'], errors='coerce')
                df['Durée Moyenne (min)'] = pd.to_numeric(df['Durée Moyenne (min)'], errors='coerce')
                return df
        except Exception as e:
            st.error(f"Erreur charge professeurs: {e}")
        return pd.DataFrame()
    
    def get_all_exams_for_visualizations(self, limit=5000):
        """Récupérer tous les examens pour les visualisations"""
        success, error = self.safe_execute("""
            SELECT 
                ep.date_heure,
                m.nom as module,
                f.nom as formation,
                d.nom as departement,
                l.nom as salle,
                CONCAT(p.prenom, ' ', p.nom) as professeur,
                ep.duree_minutes,
                ep.mode_generation
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN professeurs p ON ep.prof_id = p.id
            JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
            ORDER BY ep.date_heure
            LIMIT %s
        """, (limit,))
        
        if success:
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            df = pd.DataFrame(data, columns=columns)
            # Conversion en numérique
            df['duree_minutes'] = pd.to_numeric(df['duree_minutes'], errors='coerce')
            return df
        else:
            return pd.DataFrame()
    
    # ==================== FONCTIONS STRATÉGIQUES POUR VICE-DOYEN/DOYEN ====================
    
    def get_kpi_academiques(self):
        """Récupérer les KPIs académiques stratégiques"""
        kpis = {}
        
        # 1. Taux de conflits
        success, error = self.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut IN ('PROPOSE', 'VALIDE')")
        if success:
            total_examens = self.cursor.fetchone()[0]
            if total_examens > 0:
                conflits = self.count_conflicts()
                kpis['taux_conflits'] = (conflits / total_examens) * 100 if conflits > 0 else 0
            else:
                kpis['taux_conflits'] = 0
        
        # 2. Heures totales de surveillance
        success, error = self.safe_execute("""
            SELECT SUM(duree_minutes)/60.0 FROM examens_planifies 
            WHERE statut IN ('PROPOSE', 'VALIDE')
        """)
        if success:
            total_heures = self.cursor.fetchone()[0]
            kpis['total_heures_surveillance'] = total_heures or 0
        
        # 3. Taux d'utilisation des salles
        success, error = self.safe_execute("SELECT COUNT(*) FROM lieu_examen")
        if success:
            total_salles = self.cursor.fetchone()[0]
            if total_salles > 0:
                success, error = self.safe_execute("""
                    SELECT COUNT(DISTINCT salle_id) FROM examens_planifies 
                    WHERE statut IN ('PROPOSE', 'VALIDE')
                """)
                if success:
                    salles_utilisees = self.cursor.fetchone()[0]
                    kpis['taux_salles_utilisees'] = (salles_utilisees / total_salles) * 100 if total_salles > 0 else 0
        
        # 4. Nombre de professeurs impliqués
        success, error = self.safe_execute("""
            SELECT COUNT(DISTINCT prof_id) FROM examens_planifies 
            WHERE statut IN ('PROPOSE', 'VALIDE')
        """)
        if success:
            profs_impliques = self.cursor.fetchone()[0]
            kpis['profs_impliques'] = profs_impliques or 0
        
        # 5. Répartition amphis vs salles
        success, error = self.safe_execute("""
            SELECT 
                SUM(CASE WHEN l.type = 'AMPHI' THEN 1 ELSE 0 END) as amphis,
                SUM(CASE WHEN l.type = 'SALLE' THEN 1 ELSE 0 END) as salles
            FROM lieu_examen l
            JOIN examens_planifies ep ON l.id = ep.salle_id
            WHERE ep.statut IN ('PROPOSE', 'VALIDE')
        """)
        if success:
            repartition = self.cursor.fetchone()
            if repartition:
                kpis['examens_amphis'] = repartition[0] or 0
                kpis['examens_salles'] = repartition[1] or 0
            else:
                kpis['examens_amphis'] = 0
                kpis['examens_salles'] = 0
        
        # 6. Charge moyenne par professeur
        if kpis.get('profs_impliques', 0) > 0 and kpis.get('total_heures_surveillance', 0) > 0:
            kpis['charge_moyenne_par_prof'] = kpis['total_heures_surveillance'] / kpis['profs_impliques']
        else:
            kpis['charge_moyenne_par_prof'] = 0
        
        return kpis
    
    def get_conflits_par_departement(self):
        """Récupérer les conflits par département"""
        try:
            success, error = self.safe_execute("""
                SELECT 
                    d.nom as departement,
                    COUNT(DISTINCT e1.id) as examens_en_conflit,
                    COUNT(DISTINCT 
                        CASE 
                            WHEN e1.id < e2.id THEN e1.id 
                            ELSE e2.id 
                        END
                    ) as nb_conflits
                FROM examens_planifies e1
                JOIN examens_planifies e2 ON e1.id != e2.id 
                    AND e1.salle_id = e2.salle_id 
                    AND e1.date_heure = e2.date_heure
                JOIN modules m ON e1.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE e1.statut IN ('PROPOSE', 'VALIDE') 
                    AND e2.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY d.nom
                ORDER BY nb_conflits DESC
            """)
            
            if success:
                data = self.cursor.fetchall()
                df = pd.DataFrame(data, 
                                 columns=['Département', 'Examens en conflit', 'Nombre de conflits'])
                # Conversion en numérique
                df['Examens en conflit'] = pd.to_numeric(df['Examens en conflit'], errors='coerce')
                df['Nombre de conflits'] = pd.to_numeric(df['Nombre de conflits'], errors='coerce')
                return df
        except Exception as e:
            st.error(f"Erreur conflits par département: {e}")
        return pd.DataFrame()
    
    def get_occupation_strategique(self):
        """Occupation stratégique des ressources"""
        stats = {}
        
        # Occupation par type de salle
        success, error = self.safe_execute("""
            SELECT 
                l.type,
                COUNT(ep.id) as nb_examens,
                CASE 
                    WHEN SUM(ep.duree_minutes) IS NOT NULL 
                    THEN SUM(ep.duree_minutes)/60.0
                    ELSE 0
                END as heures_occupees,
                COUNT(DISTINCT DATE(ep.date_heure)) as jours_occupes
            FROM lieu_examen l
            LEFT JOIN examens_planifies ep ON l.id = ep.salle_id AND ep.statut IN ('PROPOSE', 'VALIDE')
            GROUP BY l.type
            ORDER BY l.type
        """)
        
        if success:
            data = self.cursor.fetchall()
            stats['occupation_par_type'] = pd.DataFrame(data, 
                                                       columns=['Type', 'Examens', 'Heures', 'Jours occupés'])
            # Conversion en numérique
            if not stats['occupation_par_type'].empty:
                stats['occupation_par_type']['Examens'] = pd.to_numeric(stats['occupation_par_type']['Examens'], errors='coerce')
                stats['occupation_par_type']['Heures'] = pd.to_numeric(stats['occupation_par_type']['Heures'], errors='coerce')
                stats['occupation_par_type']['Jours occupés'] = pd.to_numeric(stats['occupation_par_type']['Jours occupés'], errors='coerce')
        
        # Distribution des examens dans le temps
        success, error = self.safe_execute("""
            SELECT 
                EXTRACT(HOUR FROM date_heure) as heure,
                COUNT(*) as nb_examens
            FROM examens_planifies
            WHERE statut IN ('PROPOSE', 'VALIDE')
            GROUP BY EXTRACT(HOUR FROM date_heure)
            ORDER BY heure
        """)
        
        if success:
            data = self.cursor.fetchall()
            stats['distribution_par_heure'] = pd.DataFrame(data, 
                                                          columns=['Heure', 'Examens'])
            # Conversion en numérique
            if not stats['distribution_par_heure'].empty:
                stats['distribution_par_heure']['Heure'] = pd.to_numeric(stats['distribution_par_heure']['Heure'], errors='coerce')
                stats['distribution_par_heure']['Examens'] = pd.to_numeric(stats['distribution_par_heure']['Examens'], errors='coerce')
        
        # Taux de réussite de planification
        success, error = self.safe_execute("""
            SELECT 
                mode_generation,
                COUNT(*) as nb_examens,
                AVG(duree_minutes) as duree_moyenne
            FROM examens_planifies
            WHERE statut IN ('PROPOSE', 'VALIDE')
            GROUP BY mode_generation
        """)
        
        if success:
            data = self.cursor.fetchall()
            stats['reussite_planification'] = pd.DataFrame(data, 
                                                          columns=['Mode', 'Examens', 'Durée moyenne'])
            # Conversion en numérique
            if not stats['reussite_planification'].empty:
                stats['reussite_planification']['Examens'] = pd.to_numeric(stats['reussite_planification']['Examens'], errors='coerce')
                stats['reussite_planification']['Durée moyenne'] = pd.to_numeric(stats['reussite_planification']['Durée moyenne'], errors='coerce')
        
        return stats

# ==================== INTERFACE STREAMLIT COMPLÈTE ====================

def show_login_page():
    """Page de connexion"""
    st.title("Plateforme d'Optimisation des Examens Universitaires")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Bienvenue sur la plateforme")
        st.markdown("""
        Cette plateforme vous permet de gérer et optimiser les examens universitaires.
        Sélectionnez votre rôle dans le menu ci-contre pour accéder aux fonctionnalités adaptées à votre profil.
        """)
        
        st.markdown("---")
        st.markdown("**Sélectionnez votre rôle ci-contre pour accéder à votre tableau de bord.**")
    
    with col2:
        st.header("Connexion")
        role = st.selectbox(
            "Sélectionnez votre rôle :",
            ["Étudiant", "Professeur", "Chef de département", 
             "Administrateur", "Vice-doyen/Doyen"]
        )
        
        if st.button("Se connecter", type="primary", use_container_width=True):
            st.session_state['role'] = role
            st.rerun()

def show_etudiant_dashboard(platform):
    """Dashboard pour étudiant"""
    st.title("Tableau de bord Étudiant")
    st.markdown("---")
    
    st.subheader("Recherche de vos examens")
    
    col1, col2 = st.columns(2)
    
    with col1:
        departments = platform.get_departments()
        dept_names = [d[1] for d in departments]
        selected_dept = st.selectbox("Département", ["Tous"] + dept_names)
    
    with col2:
        formation_options = ["Toutes"]
        if selected_dept != "Tous":
            dept_id = [d[0] for d in departments if d[1] == selected_dept][0]
            formations = platform.get_formations_by_department(dept_id)
            formation_options += [f[1] for f in formations]
        
        selected_formation = st.selectbox("Formation", formation_options)
    
    col3, col4 = st.columns(2)
    with col3:
        date_debut = st.date_input("Date de début", datetime.now().date())
    with col4:
        date_fin = st.date_input("Date de fin", datetime.now().date() + timedelta(days=30))
    
    filters = {
        'departement': selected_dept if selected_dept != 'Tous' else None,
        'formation': selected_formation if selected_formation != 'Toutes' else None,
        'date_debut': f"{date_debut} 00:00:00",
        'date_fin': f"{date_fin} 23:59:59"
    }
    
    exams_df = platform.get_student_exams(filters={k: v for k, v in filters.items() if v})
    
    if not exams_df.empty:
        st.subheader(f"{len(exams_df)} examens trouvés")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Examens", len(exams_df))
        with col2:
            st.metric("Départements", exams_df['Département'].nunique())
        with col3:
            st.metric("Formations", exams_df['Formation'].nunique())
        
        st.dataframe(exams_df, use_container_width=True, height=400)
        
        csv = exams_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Télécharger le planning",
            data=csv,
            file_name=f"planning_examens_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("---")
        st.subheader("Calendrier des examens")
        
        exams_df['Date'] = pd.to_datetime(exams_df['Date/Heure']).dt.date
        exams_df['Heure'] = pd.to_datetime(exams_df['Date/Heure']).dt.strftime('%H:%M')
        exams_df['Jour'] = pd.to_datetime(exams_df['Date/Heure']).dt.strftime('%A %d %B')
        
        fig = px.timeline(exams_df, x_start="Date/Heure", x_end=pd.to_datetime(exams_df['Date/Heure']) + pd.to_timedelta(exams_df['Durée (min)'], unit='m'),
                          y="Module", color="Département", title="Calendrier des examens",
                          hover_data=["Formation", "Salle", "Professeur"])
        fig.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Statistiques personnelles")
        
        col1, col2 = st.columns(2)
        with col1:
            module_count = exams_df['Module'].nunique()
            st.metric("Modules différents", module_count)
            
            total_duration = exams_df['Durée (min)'].sum()
            st.metric("Temps total d'examens", f"{total_duration/60:.1f} heures")
        
        with col2:
            room_count = exams_df['Salle'].nunique()
            st.metric("Salles différentes", room_count)
            
            prof_count = exams_df['Professeur'].nunique()
            st.metric("Professeurs différents", prof_count)
        
    else:
        st.info("Aucun examen trouvé avec ces critères.")

def show_professeur_dashboard(platform):
    """Dashboard pour professeur"""
    st.title("Tableau de bord Professeur")
    st.markdown("---")
    
    st.subheader("Sélection du professeur")
    
    success, error = platform.safe_execute("""
        SELECT DISTINCT CONCAT(p.prenom, ' ', p.nom) as nom_complet
        FROM professeurs p
        JOIN examens_planifies ep ON p.id = ep.prof_id
        WHERE ep.statut IN ('PROPOSE', 'VALIDE')
        ORDER BY nom_complet
    """)
    
    if success:
        profs = platform.cursor.fetchall()
        prof_names = [p[0] for p in profs] if profs else ["Professeur Test"]
        
        if prof_names:
            selected_prof = st.selectbox("Sélectionnez votre nom", prof_names)
            
            exams_df = platform.get_teacher_exams(teacher_name=selected_prof)
            
            if not exams_df.empty:
                st.subheader(f"{len(exams_df)} surveillances programmées")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Surveillances", len(exams_df))
                with col2:
                    unique_departements = exams_df['Département'].nunique()
                    st.metric("Départements", unique_departements)
                with col3:
                    total_duree = exams_df['Durée (min)'].sum()
                    st.metric("Heures totales", f"{total_duree/60:.1f}h")
                
                st.dataframe(exams_df, use_container_width=True, height=400)
                
                st.markdown("---")
                st.subheader("Calendrier des surveillances")
                
                exams_df['Date'] = pd.to_datetime(exams_df['Date/Heure']).dt.date
                exams_df['Heure'] = pd.to_datetime(exams_df['Date/Heure']).dt.strftime('%H:%M')
                
                fig = px.timeline(exams_df, x_start="Date/Heure", 
                                 x_end=pd.to_datetime(exams_df['Date/Heure']) + pd.to_timedelta(exams_df['Durée (min)'], unit='m'),
                                 y="Module", color="Département", title="Vos surveillances",
                                 hover_data=["Salle"])
                fig.update_yaxes(categoryorder="total ascending")
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                st.subheader("Statistiques de vos surveillances")
                
                col1, col2 = st.columns(2)
                with col1:
                    dept_stats = exams_df['Département'].value_counts().reset_index()
                    dept_stats.columns = ['Département', 'Surveillances']
                    fig1 = px.pie(dept_stats, values='Surveillances', names='Département',
                                 title="Répartition par département")
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    exams_df['Jour'] = pd.to_datetime(exams_df['Date/Heure']).dt.date
                    daily_stats = exams_df.groupby('Jour').size().reset_index(name='Surveillances')
                    fig2 = px.bar(daily_stats, x='Jour', y='Surveillances',
                                 title="Surveillances par jour")
                    st.plotly_chart(fig2, use_container_width=True)
                
                csv = exams_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Télécharger mes surveillances",
                    data=csv,
                    file_name=f"surveillances_{selected_prof.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Aucune surveillance programmée pour ce professeur.")
        else:
            st.warning("Aucun professeur n'a d'examens programmés.")
    else:
        st.error("Erreur lors de la récupération des professeurs.")

def show_chef_departement_dashboard(platform):
    """Dashboard pour chef de département"""
    st.title("Tableau de bord Chef de Département")
    st.markdown("---")
    
    departments = platform.get_departments()
    dept_names = [d[1] for d in departments]
    
    if not dept_names:
        st.error("Aucun département trouvé")
        return
    
    selected_dept = st.selectbox("Votre département", dept_names)
    
    st.markdown(f"### Département : **{selected_dept}**")
    
    tab1, tab2, tab3 = st.tabs(["Vue d'ensemble", "Examens", "Professeurs"])
    
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT ep.id) 
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut IN ('PROPOSE', 'VALIDE')
            """, (selected_dept,))
            if success:
                examens_count = platform.cursor.fetchone()[0] or 0
                st.metric("Examens validés", examens_count)
        
        with col2:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT p.id)
                FROM professeurs p
                JOIN examens_planifies ep ON p.id = ep.prof_id
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut IN ('PROPOSE', 'VALIDE')
            """, (selected_dept,))
            if success:
                profs_count = platform.cursor.fetchone()[0] or 0
                st.metric("Professeurs impliqués", profs_count)
        
        with col3:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM formations f
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s
            """, (selected_dept,))
            if success:
                formations_count = platform.cursor.fetchone()[0] or 0
                st.metric("Formations", formations_count)
        
        with col4:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT m.id)
                FROM modules m
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s
            """, (selected_dept,))
            if success:
                modules_count = platform.cursor.fetchone()[0] or 0
                st.metric("Modules", modules_count)
        
        col1, col2 = st.columns(2)
        
        with col1:
            success, error = platform.safe_execute("""
                SELECT f.nom, COUNT(ep.id) as examens
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY f.nom
                ORDER BY examens DESC
            """, (selected_dept,))
            
            if success:
                formation_data = platform.cursor.fetchall()
                if formation_data:
                    df_formation = pd.DataFrame(formation_data, columns=['Formation', 'Examens'])
                    fig = px.bar(df_formation, x='Formation', y='Examens',
                                title="Examens par formation")
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            success, error = platform.safe_execute("""
                SELECT DATE(ep.date_heure) as jour, COUNT(*) as examens
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut IN ('PROPOSE', 'VALIDE')
                GROUP BY DATE(ep.date_heure)
                ORDER BY jour
            """, (selected_dept,))
            
            if success:
                daily_data = platform.cursor.fetchall()
                if daily_data:
                    df_daily = pd.DataFrame(daily_data, columns=['Jour', 'Examens'])
                    fig = px.line(df_daily, x='Jour', y='Examens',
                                 title="Évolution des examens par jour")
                    st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        exams_df = platform.get_department_exams(selected_dept)
        
        if not exams_df.empty:
            st.subheader(f"{len(exams_df)} examens dans le département")
            
            st.dataframe(exams_df, use_container_width=True, height=400)
            
            csv = exams_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Télécharger la liste",
                data=csv,
                file_name=f"examens_{selected_dept.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("Aucun examen trouvé pour ce département.")
    
    with tab3:
        workload_df = platform.get_professor_workload()
        if not workload_df.empty:
            st.subheader("Charge de travail des professeurs")
            
            filtered_workload = workload_df[workload_df['Département'] == selected_dept]
            
            if not filtered_workload.empty:
                st.dataframe(filtered_workload, use_container_width=True, height=400)
                
                fig = px.bar(filtered_workload.head(10), x='Professeur', y='Heures Total',
                            title="Top 10 professeurs (heures de surveillance)",
                            color='Examens')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Aucune donnée de charge pour le département {selected_dept}")

def show_administrateur_dashboard(platform):
    """Dashboard administrateur"""
    st.title("Tableau de bord Administrateur")
    st.markdown("---")
    
    if 'reset_before_generate' not in st.session_state:
        st.session_state.reset_before_generate = True
    
    if platform.check_initial_state():
        st.success("Base prête pour la planification (0 examens existants)")
    else:
        st.warning("Il y a déjà des examens planifiés")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Réinitialiser", type="secondary", use_container_width=True):
                with st.spinner("Réinitialisation en cours..."):
                    success, message = platform.reset_all_exams()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Génération AUTO", "Ajout MANUEL", "EDT Généré", 
                                                  "Optimisation", "Visualisations", "Occupation"])
    
    with tab1:
        st.subheader("Génération Automatique d'Emploi du Temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nb_examens = st.slider("Nombre d'examens", 10, 200, 30)
            duree_moyenne = st.select_slider("Durée (minutes)", [60, 90, 120, 150, 180], value=120)
            
            st.session_state.reset_before_generate = st.checkbox(
                "Réinitialiser avant de générer", value=True
            )
            
            st.markdown("---")
            st.info("""
            **Mode de génération simplifiée :**
            - Tente plusieurs méthodes d'insertion
            - Gère automatiquement les contraintes
            - Utilise autocommit=True
            - Gère les erreurs une par une
            """)
        
        with col2:
            success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut IN ('PROPOSE', 'VALIDE')")
            if success:
                total_examens = platform.cursor.fetchone()[0]
                st.metric("Examens existants", total_examens)
            
            conflits = platform.count_conflicts()
            if conflits > 0:
                st.error(f"{conflits} conflit(s)")
            else:
                st.success("Aucun conflit")
            
            estimated_time = nb_examens * 0.2
            st.info(f"Temps estimé: {estimated_time:.1f}s")
            
            st.markdown("---")
            if st.button("Test génération (5 examens)"):
                with st.spinner("Test en cours..."):
                    if st.session_state.reset_before_generate:
                        platform.reset_all_exams()
                    
                    succes, message, temps_exec, details = platform.generate_simple_timetable(
                        nb_examens=5,
                        duree_minutes=120
                    )
                    
                    if succes:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        st.markdown("---")
        if st.button("GÉNÉRER L'EMPLOI DU TEMPS", type="primary", use_container_width=True):
            with st.spinner("Génération en cours..."):
                if st.session_state.reset_before_generate:
                    platform.reset_all_exams()
                
                succes, message, temps_exec, details = platform.generate_simple_timetable(
                    nb_examens=nb_examens,
                    duree_minutes=duree_moyenne
                )
                
                if succes:
                    st.success(f"{message}")
                    st.metric("Temps d'exécution", f"{temps_exec}s")
                    
                    if temps_exec <= 45:
                        st.balloons()
                        st.success("OBJECTIF ATTEINT: < 45 secondes!")
                    
                    with st.expander("Détails de la génération"):
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Examens créés", details.get('examens_planifies', 0))
                        with col_b:
                            st.metric("Échecs", details.get('echecs', 0))
                        with col_c:
                            taux = details.get('taux_reussite', 0)
                            st.metric("Taux réussite", f"{taux:.1f}%")
                    
                    st.rerun()
                else:
                    st.error(f"{message}")
                    
                    if 'echecs_details' in details and details['echecs_details']:
                        with st.expander("Voir les erreurs détaillées"):
                            for err in details['echecs_details']:
                                st.write(f"- {err}")
    
    with tab2:
        st.subheader("Ajout Manuel d'Examen")
        
        modules = platform.get_modules_sans_examen()
        professeurs = platform.get_all_professeurs()
        salles = platform.get_all_salles()
        
        if not modules:
            st.error("Tous les modules ont déjà un examen planifié!")
        else:
            with st.form("form_ajout_manuel"):
                col1, col2 = st.columns(2)
                
                with col1:
                    module_options = {f"{m[1]} ({m[3]} - {m[2]})": m[0] for m in modules}
                    module_choice = st.selectbox("Module à planifier", list(module_options.keys()))
                    module_id = module_options[module_choice]
                    
                    prof_options = {p[1]: p[0] for p in professeurs}
                    prof_choice = st.selectbox("Professeur responsable", list(prof_options.keys()))
                    prof_id = prof_options[prof_choice]
                
                with col2:
                    salle_options = {f"{s[1]} ({s[2]}, {s[3]} places)": s[0] for s in salles}
                    salle_choice = st.selectbox("Salle d'examen", list(salle_options.keys()))
                    salle_id = salle_options[salle_choice]
                    
                    date_examen = st.date_input("Date de l'examen", datetime.now().date() + timedelta(days=7))
                    heure_examen = st.selectbox("Heure de début", ["08:30", "10:45", "14:00", "16:15"])
                    date_heure = f"{date_examen} {heure_examen}:00"
                    
                    duree_minutes = st.selectbox("Durée (minutes)", [60, 90, 120, 150, 180])
                
                st.markdown("---")
                st.subheader("Aperçu de l'examen")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Module :** {module_choice}")
                    st.write(f"**Professeur :** {prof_choice}")
                with col_b:
                    st.write(f"**Salle :** {salle_choice}")
                    st.write(f"**Date/Heure :** {date_heure}")
                    st.write(f"**Durée :** {duree_minutes} minutes")
                
                submitted = st.form_submit_button("AJOUTER L'EXAMEN", type="primary", use_container_width=True)
                
                if submitted:
                    with st.spinner("Ajout en cours..."):
                        success, message = platform.add_manual_exam(
                            module_id=module_id,
                            prof_id=prof_id,
                            salle_id=salle_id,
                            date_heure=date_heure,
                            duree_minutes=duree_minutes
                        )
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
    
    with tab3:
        st.subheader("Emploi du Temps Généré")
        
        show_limit = st.selectbox("Nombre d'examens à afficher", [50, 100, 200, 500], index=0)
        timetable = platform.get_generated_timetable(limit=show_limit)
        
        if not timetable.empty:
            st.write(f"**{len(timetable)} examens planifiés**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if 'departement' in timetable.columns:
                    dept_count = timetable['departement'].nunique()
                    st.metric("Départements", dept_count)
            
            with col2:
                if 'salle' in timetable.columns:
                    salle_count = timetable['salle'].nunique()
                    st.metric("Salles utilisées", salle_count)
            
            with col3:
                conflits = platform.count_conflicts()
                st.metric("Conflits", conflits)
            
            # MODIFICATION : Supprimer 'mode_generation' de la liste des colonnes à afficher
            display_cols = ['date_heure', 'module', 'departement', 'salle', 'professeur', 'duree_minutes']
            available_cols = [col for col in display_cols if col in timetable.columns]
            
            if available_cols:
                st.dataframe(
                    timetable[available_cols],
                    use_container_width=True,
                    height=400
                )
            
            csv = timetable[available_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Télécharger l'EDT",
                data=csv,
                file_name=f"emploi_du_temps_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            if st.button("Réinitialiser cet emploi du temps", type="secondary"):
                with st.spinner("Réinitialisation en cours..."):
                    success, message = platform.reset_all_exams()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        else:
            st.info("Aucun emploi du temps généré")
            
            if st.button("Générer un EDT (20 examens)"):
                with st.spinner("Génération en cours..."):
                    platform.reset_all_exams()
                    succes, message, temps_exec, details = platform.generate_simple_timetable(
                        nb_examens=20,
                        duree_minutes=120
                    )
                    
                    if succes:
                        st.success(f"{message}")
                        st.rerun()
                    else:
                        st.error(f"{message}")
    
    with tab4:
        st.subheader("Optimisation des Conflits")
        
        conflits_actuels = platform.count_conflicts()
        
        if conflits_actuels == 0:
            st.success("Aucun conflit détecté!")
        else:
            st.error(f"{conflits_actuels} conflit(s) détecté(s)")
            
            if st.button("Voir les détails des conflits"):
                conflicts_df = platform.get_conflicts_details()
                if not conflicts_df.empty:
                    st.dataframe(conflicts_df, use_container_width=True)
                else:
                    st.info("Aucun détail disponible")
        
        st.markdown("---")
        
        if st.button("Lancer l'optimisation", use_container_width=True):
            with st.spinner("Optimisation en cours..."):
                succes, message, temps_exec = platform.optimize_timetable(mode='RAPIDE')
                
                if succes:
                    st.success(message)
                    st.metric("Temps", f"{temps_exec}s")
                    st.rerun()
                else:
                    st.error(message)
    
    with tab5:
        st.subheader("Visualisations Avancées")
        
        exams_df = platform.get_all_exams_for_visualizations(limit=5000)
        
        if not exams_df.empty:
            st.write(f"**{len(exams_df)} examens analysés**")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total examens", len(exams_df))
            with col2:
                st.metric("Départements", exams_df['departement'].nunique())
            with col3:
                st.metric("Salles utilisées", exams_df['salle'].nunique())
            with col4:
                st.metric("Professeurs", exams_df['professeur'].nunique())
            
            st.subheader("Examens par jour")
            exams_df['Date'] = pd.to_datetime(exams_df['date_heure']).dt.date
            daily_counts = exams_df.groupby('Date').size().reset_index(name='Examens')
            
            fig1 = px.bar(daily_counts, x='Date', y='Examens',
                         title="Nombre d'examens par jour",
                         color='Examens',
                         color_continuous_scale='Blues')
            st.plotly_chart(fig1, use_container_width=True)
            
            st.subheader("Répartition par département")
            dept_counts = exams_df['departement'].value_counts().reset_index()
            dept_counts.columns = ['Département', 'Examens']
            
            fig2 = px.pie(dept_counts, values='Examens', names='Département',
                         title="Répartition des examens par département",
                         hole=0.3)
            st.plotly_chart(fig2, use_container_width=True)
            
            st.subheader("Occupation des salles")
            salle_counts = exams_df['salle'].value_counts().reset_index()
            salle_counts.columns = ['Salle', 'Examens']
            
            fig3 = px.bar(salle_counts.head(20), x='Salle', y='Examens',
                         title="Top 20 salles les plus utilisées",
                         color='Examens',
                         color_continuous_scale='Viridis')
            st.plotly_chart(fig3, use_container_width=True)
            
            st.subheader("Distribution des durées d'examen")
            fig5 = px.histogram(exams_df, x='duree_minutes',
                               title="Distribution des durées d'examen (minutes)",
                               nbins=10,
                               color_discrete_sequence=['#636EFA'])
            st.plotly_chart(fig5, use_container_width=True)
            
        else:
            st.info("Aucun examen disponible pour les visualisations")
    
    with tab6:
        st.subheader("Occupation des Salles")
        
        occupation_details = platform.get_detailed_room_occupation()
        
        if not occupation_details.empty:
            col_occ1, col_occ2, col_occ3 = st.columns(3)
            
            with col_occ1:
                amphi_count = len(occupation_details[occupation_details['Type'] == 'AMPHI'])
                st.metric("Amphithéâtres utilisés", amphi_count)
            
            with col_occ2:
                salle_count = len(occupation_details[occupation_details['Type'] == 'SALLE'])
                st.metric("Salles utilisées", salle_count)
            
            with col_occ3:
                taux_moyen = occupation_details['Taux Occupation (%)'].mean()
                st.metric("Taux occupation moyen", f"{taux_moyen:.1f}%")
            
            # CORRECTION : Conversion de la colonne en numérique avant nlargest
            occupation_details['Taux Occupation (%)'] = pd.to_numeric(occupation_details['Taux Occupation (%)'], errors='coerce')
            top_salles = occupation_details.nlargest(10, 'Taux Occupation (%)')
            
            fig = px.bar(top_salles, x='Salle', y='Taux Occupation (%)',
                        color='Type',
                        title="Top 10 salles par taux d'occupation",
                        hover_data=['Examens', 'Heures', 'Capacité'])
            st.plotly_chart(fig, use_container_width=True)
            
            occupation_stats = platform.get_room_occupation_stats()
            if not occupation_stats.empty:
                fig2 = px.pie(occupation_stats, values='Nb Examens', names='Type',
                             title="Répartition des examens par type de salle")
                st.plotly_chart(fig2, use_container_width=True)

def show_doyen_dashboard(platform):
    """Dashboard vice-doyen/doyen - Vue stratégique globale"""
    st.title("Tableau de bord Direction - Vue Stratégique")
    st.markdown("---")
    
    # KPIs Principaux en haut
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut IN ('PROPOSE', 'VALIDE')")
        if success:
            total_examens = platform.cursor.fetchone()[0]
            st.metric("Examens planifiés", total_examens)
    
    with col2:
        conflits = platform.count_conflicts()
        if conflits > 0:
            st.error(f"Conflits: {conflits}")
        else:
            st.success("Conflits: 0")
    
    with col3:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM etudiants")
        if success:
            total_etudiants = platform.cursor.fetchone()[0]
            st.metric("Étudiants", total_etudiants)
    
    with col4:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM professeurs")
        if success:
            total_profs = platform.cursor.fetchone()[0]
            st.metric("Professeurs", total_profs)
    
    with col5:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM lieu_examen")
        if success:
            total_salles = platform.cursor.fetchone()[0]
            st.metric("Salles", total_salles)
    
    st.markdown("---")
    
    # Onglets pour la vue stratégique
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["KPIs Académiques", "Occupation Globale", "Conflits par Département", 
                                            "Charge des Professeurs", "Validation Finale"])
    
    with tab1:
        st.subheader("Indicateurs Clés de Performance Académiques")
        
        # Récupérer les KPIs
        kpis = platform.get_kpi_academiques()
        
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        with col_kpi1:
            if 'taux_conflits' in kpis:
                st.metric("Taux de conflits", f"{kpis['taux_conflits']:.1f}%")
            else:
                st.metric("Taux de conflits", "N/A")
        
        with col_kpi2:
            if 'total_heures_surveillance' in kpis:
                st.metric("Heures surveillance", f"{kpis['total_heures_surveillance']:.0f}h")
        
        with col_kpi3:
            if 'taux_salles_utilisees' in kpis:
                st.metric("Salles utilisées", f"{kpis['taux_salles_utilisees']:.1f}%")
        
        with col_kpi4:
            if 'charge_moyenne_par_prof' in kpis:
                st.metric("Charge moyenne/prof", f"{kpis['charge_moyenne_par_prof']:.1f}h")
        
        st.markdown("---")
        
        # Visualisations des KPIs
        col_viz1, col_viz2 = st.columns(2)
        
        with col_viz1:
            # Répartition amphis vs salles
            if 'examens_amphis' in kpis and 'examens_salles' in kpis:
                fig = go.Figure(data=[go.Pie(
                    labels=['Amphithéâtres', 'Salles'],
                    values=[kpis['examens_amphis'], kpis['examens_salles']],
                    hole=0.3,
                    marker=dict(colors=['#FF6B6B', '#4ECDC4'])
                )])
                fig.update_layout(title="Répartition examens par type de salle")
                st.plotly_chart(fig, use_container_width=True)
        
        with col_viz2:
            # Diagramme de Gantt simplifié
            exams_df = platform.get_all_exams_for_visualizations(limit=100)
            if not exams_df.empty:
                exams_df['Date'] = pd.to_datetime(exams_df['date_heure']).dt.date
                daily_counts = exams_df.groupby('Date').size().reset_index(name='Examens')
                
                fig = px.line(daily_counts, x='Date', y='Examens',
                             title="Densité des examens dans le temps",
                             markers=True)
                fig.update_traces(line=dict(width=3))
                st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Vue Stratégique de l'Occupation")
        
        occupation_details = platform.get_detailed_room_occupation()
        
        if not occupation_details.empty:
            # CORRECTION : S'assurer que la colonne est numérique
            occupation_details['Taux Occupation (%)'] = pd.to_numeric(occupation_details['Taux Occupation (%)'], errors='coerce')
            occupation_details['Heures'] = pd.to_numeric(occupation_details['Heures'], errors='coerce')
            
            col_occ1, col_occ2, col_occ3 = st.columns(3)
            
            with col_occ1:
                amphi_count = len(occupation_details[occupation_details['Type'] == 'AMPHI'])
                st.metric("Amphithéâtres", amphi_count)
            
            with col_occ2:
                salle_count = len(occupation_details[occupation_details['Type'] == 'SALLE'])
                st.metric("Salles normales", salle_count)
            
            with col_occ3:
                taux_moyen = occupation_details['Taux Occupation (%)'].mean()
                st.metric("Taux moyen", f"{taux_moyen:.1f}%")
            
            st.subheader("Top 10 des salles les plus utilisées")
            # CORRECTION : Utiliser nlargest sur la colonne maintenant numérique
            top_salles = occupation_details.nlargest(10, 'Taux Occupation (%)')
            
            fig = px.bar(top_salles, x='Salle', y='Taux Occupation (%)',
                        color='Type',
                        title="Top 10 salles par taux d'occupation",
                        hover_data=['Examens', 'Heures', 'Capacité'])
            st.plotly_chart(fig, use_container_width=True)
        
        # Occupation par type
        occupation_stats = platform.get_room_occupation_stats()
        if not occupation_stats.empty:
            # CORRECTION : S'assurer que les colonnes sont numériques
            occupation_stats['Taux Occupation (%)'] = pd.to_numeric(occupation_stats['Taux Occupation (%)'], errors='coerce')
            occupation_stats['Nb Salles'] = pd.to_numeric(occupation_stats['Nb Salles'], errors='coerce')
            occupation_stats['Nb Examens'] = pd.to_numeric(occupation_stats['Nb Examens'], errors='coerce')
            
            col_occ4, col_occ5 = st.columns(2)
            
            with col_occ4:
                fig2 = px.bar(occupation_stats, x='Type', y='Taux Occupation (%)',
                             title="Taux d'occupation par type de salle",
                             color='Type',
                             text='Taux Occupation (%)')
                fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig2, use_container_width=True)
            
            with col_occ5:
                fig3 = px.pie(occupation_stats, values='Nb Examens', names='Type',
                             title="Répartition des examens par type de salle",
                             hole=0.3)
                st.plotly_chart(fig3, use_container_width=True)
    
    with tab3:
        st.subheader("Analyse des Conflits par Département")
        
        # Conflits par département
        conflicts_by_dept = platform.get_conflits_par_departement()
        
        if not conflicts_by_dept.empty:
            col_conf1, col_conf2 = st.columns([2, 1])
            
            with col_conf1:
                # CORRECTION : S'assurer que les colonnes sont numériques
                conflicts_by_dept['Nombre de conflits'] = pd.to_numeric(conflicts_by_dept['Nombre de conflits'], errors='coerce')
                conflicts_by_dept['Examens en conflit'] = pd.to_numeric(conflicts_by_dept['Examens en conflit'], errors='coerce')
                
                fig = px.bar(conflicts_by_dept, x='Département', y='Nombre de conflits',
                            title="Conflits par département",
                            color='Examens en conflit',
                            color_continuous_scale='Reds')
                st.plotly_chart(fig, use_container_width=True)
            
            with col_conf2:
                st.dataframe(conflicts_by_dept, use_container_width=True, height=400)
            
            # Analyse des causes de conflits
            st.subheader("Détails des conflits critiques")
            conflicts_details = platform.get_conflicts_details()
            if not conflicts_details.empty:
                st.dataframe(conflicts_details, use_container_width=True, height=300)
        else:
            st.success("Aucun conflit détecté entre départements")
    
    with tab4:
        st.subheader("Charge de Travail des Professeurs - Vue Stratégique")
        
        workload_df = platform.get_professor_workload()
        if not workload_df.empty:
            # CORRECTION : S'assurer que les colonnes sont numériques
            workload_df['Heures Total'] = pd.to_numeric(workload_df['Heures Total'], errors='coerce')
            workload_df['Examens'] = pd.to_numeric(workload_df['Examens'], errors='coerce')
            workload_df['Durée Moyenne (min)'] = pd.to_numeric(workload_df['Durée Moyenne (min)'], errors='coerce')
            
            col_work1, col_work2 = st.columns(2)
            
            with col_work1:
                # Top 10 professeurs les plus sollicités
                top_profs = workload_df.nlargest(10, 'Heures Total')
                fig1 = px.bar(top_profs, x='Professeur', y='Heures Total',
                             title="Top 10 professeurs par heures de surveillance",
                             color='Département',
                             hover_data=['Examens', 'Durée Moyenne (min)'])
                st.plotly_chart(fig1, use_container_width=True)
            
            with col_work2:
                # Répartition par département
                dept_workload = workload_df.groupby('Département').agg({
                    'Heures Total': 'sum',
                    'Examens': 'sum'
                }).reset_index()
                
                fig2 = px.pie(dept_workload, values='Heures Total', names='Département',
                             title="Répartition des heures de surveillance par département",
                             hole=0.3)
                st.plotly_chart(fig2, use_container_width=True)
            
            # Distribution de la charge
            st.subheader("Distribution de la charge de travail")
            col_dist1, col_dist2 = st.columns(2)
            
            with col_dist1:
                fig3 = px.histogram(workload_df, x='Heures Total',
                                   title="Distribution des heures de surveillance",
                                   nbins=20,
                                   color_discrete_sequence=['#636EFA'])
                st.plotly_chart(fig3, use_container_width=True)
            
            with col_dist2:
                fig4 = px.scatter(workload_df, x='Examens', y='Heures Total',
                                 color='Département',
                                 title="Correlation Examens vs Heures",
                                 hover_name='Professeur',
                                 size='Heures Total')
                st.plotly_chart(fig4, use_container_width=True)
    
    with tab5:
        st.subheader("Validation Finale de l'Emploi du Temps")
        
        # Résumé global
        col_val1, col_val2, col_val3 = st.columns(3)
        
        with col_val1:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT m.id) 
                FROM modules m
                WHERE EXISTS (
                    SELECT 1 FROM examens_planifies ep 
                    WHERE ep.module_id = m.id AND ep.statut IN ('PROPOSE', 'VALIDE')
                )
            """)
            if success:
                modules_couverts = platform.cursor.fetchone()[0]
                st.metric("Modules couverts", modules_couverts)
        
        with col_val2:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT DATE(date_heure)) 
                FROM examens_planifies 
                WHERE statut IN ('PROPOSE', 'VALIDE')
            """)
            if success:
                jours_utilises = platform.cursor.fetchone()[0]
                st.metric("Jours utilisés", jours_utilises)
        
        with col_val3:
            conflits = platform.count_conflicts()
            if conflits == 0:
                st.success("Aucun conflit")
            else:
                st.error(f"{conflits} conflit(s)")
        
        st.markdown("---")
        
        # Tableau de bord de validation
        st.subheader("Résumé par département")
        
        departments = platform.get_departments()
        dept_names = [d[1] for d in departments]
        
        validation_data = []
        for dept_name in dept_names:
            # Compter les examens par département
            success, error = platform.safe_execute("""
                SELECT COUNT(ep.id)
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut IN ('PROPOSE', 'VALIDE')
            """, (dept_name,))
            
            if success:
                exam_count = platform.cursor.fetchone()[0] or 0
                
                # Vérifier les conflits par département
                conflicts_dept = 0
                conflicts_df = platform.get_conflits_par_departement()
                if not conflicts_df.empty and dept_name in conflicts_df['Département'].values:
                    conflicts_dept = conflicts_df[conflicts_df['Département'] == dept_name]['Nombre de conflits'].iloc[0]
                
                validation_data.append({
                    'Département': dept_name,
                    'Examens planifiés': exam_count,
                    'Conflits': conflicts_dept,
                    'Statut': 'Valide' if conflicts_dept == 0 else 'À revoir'
                })
        
        if validation_data:
            df_validation = pd.DataFrame(validation_data)
            st.dataframe(df_validation, use_container_width=True, height=400)
            
            # Bouton de validation finale
            st.markdown("---")
            st.subheader("Validation Finale")
            
            col_val_btn1, col_val_btn2, col_val_btn3 = st.columns([1, 2, 1])
            with col_val_btn2:
                if st.button("VALIDER L'EMPLOI DU TEMPS COMPLET", type="primary", use_container_width=True):
                    if conflits == 0:
                        st.balloons()
                        st.success("L'emploi du temps est validé avec succès !")
                        
                        # Optionnel: Marquer tous les examens comme validés définitivement
                        success, error = platform.safe_execute("""
                            UPDATE examens_planifies 
                            SET statut = 'VALIDE'
                            WHERE statut = 'PROPOSE'
                        """)
                        
                        if success:
                            st.success("Tous les examens ont été marqués comme validés.")
                    else:
                        st.error("Impossible de valider : des conflits sont encore présents.")

def main():
    """Fonction principale"""
    
    platform = ExamPlatform()
    
    if not platform.conn:
        st.error("Connexion base de données échouée")
        st.stop()
    
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    
    if st.session_state.get('role') is None:
        show_login_page()
    else:
        with st.sidebar:
            st.image("https://img.icons8.com/color/96/000000/university.png", width=80)
            st.success(f"Connecté: **{st.session_state['role']}**")
            
            if st.session_state['role'] in ["Administrateur", "Vice-doyen/Doyen", "Chef de département"]:
                success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut IN ('PROPOSE', 'VALIDE')")
                if success:
                    total_examens = platform.cursor.fetchone()[0]
                    st.metric("Examens planifiés", total_examens)
                
                conflits = platform.count_conflicts()
                if conflits > 0:
                    st.error(f"{conflits} conflit(s)")
                else:
                    st.success("Aucun conflit")
            
            st.markdown("---")
            if st.button("Déconnexion", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        role = st.session_state['role']
        
        if role == "Étudiant":
            show_etudiant_dashboard(platform)
        elif role == "Professeur":
            show_professeur_dashboard(platform)
        elif role == "Chef de département":
            show_chef_departement_dashboard(platform)
        elif role == "Administrateur":
            show_administrateur_dashboard(platform)
        elif role in ["Vice-doyen/Doyen"]:
            show_doyen_dashboard(platform)

if __name__ == "__main__":
    main()
