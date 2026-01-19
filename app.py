#!/usr/bin/env python3
"""
DASHBOARD COMPLET - Version FINALE COMPLÈTE
"""

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
            # MODIFICATION IMPORTANTE: Autocommit activé
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
        else:
            self.cursor = None
    
    def safe_execute(self, query, params=None):
        """Exécuter une requête SQL"""
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
            # Vérifier d'abord si la table existe
            success, error = self.safe_execute("SELECT 1 FROM examens_planifies LIMIT 1")
            if not success:
                return True, "✅ Table déjà vide"
            
            # Supprimer avec TRUNCATE si possible, sinon DELETE
            try:
                success, error = self.safe_execute("TRUNCATE examens_planifies CASCADE")
                if success:
                    return True, "✅ Tous les examens ont été réinitialisés"
            except:
                # Fallback: DELETE
                success, error = self.safe_execute("DELETE FROM examens_planifies")
                if success:
                    return True, "✅ Tous les examens ont été réinitialisés"
                else:
                    return False, f"❌ Erreur DELETE: {error}"
            
            return True, "✅ Réinitialisation réussie"
            
        except Exception as e:
            return False, f"❌ Erreur: {str(e)}"
    
    def count_conflicts(self):
        """Compter les conflits"""
        try:
            # Compter les conflits de salle
            success, error = self.safe_execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT e1.id
                    FROM examens_planifies e1
                    JOIN examens_planifies e2 ON e1.id != e2.id
                    WHERE e1.salle_id = e2.salle_id 
                    AND e1.date_heure = e2.date_heure
                    AND e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
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
                AND e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
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
    
    # ==================== GÉNÉRATION AUTO (VERSION SIMPLE) ====================
    
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
            self.cursor.execute("SELECT id, nom FROM lieu_examen ORDER BY RANDOM() LIMIT 10")
            salles = self.cursor.fetchall()
            
            # 3. Récupérer les professeurs
            self.cursor.execute("SELECT id FROM professeurs ORDER BY RANDOM() LIMIT 20")
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
                return True, f"✅ {succes_count} examens planifiés", temps_execution, details
            else:
                error_msg = echecs_details[0] if echecs_details else "Erreur inconnue"
                return False, f"❌ Échec: {error_msg}", temps_execution, details
            
        except Exception as e:
            error_msg = str(e)
            return False, f"❌ Erreur système: {error_msg}", 0, {}
    
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
                return False, "❌ Ce module a déjà un examen planifié"
            
            # Vérifier si la salle est disponible à cette heure
            success, error = self.safe_execute("""
                SELECT COUNT(*) FROM examens_planifies 
                WHERE salle_id = %s AND date_heure = %s AND statut = 'VALIDE'
            """, (salle_id, date_heure))
            
            if success and self.cursor.fetchone()[0] > 0:
                return False, "❌ La salle n'est pas disponible à cette heure"
            
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
                return True, f"✅ Examen ajouté avec succès (ID: {examen_id})"
            else:
                return False, f"❌ Erreur d'insertion: {error}"
                
        except Exception as e:
            return False, f"❌ Erreur: {str(e)}"
    
    # ==================== OPTIMISATION ====================
    
    def optimize_timetable(self, mode='RAPIDE'):
        """Optimiser l'emploi du temps"""
        start_time = time.time()
        
        try:
            # Vérifier les conflits actuels
            conflits_avant = self.count_conflicts()
            
            if conflits_avant == 0:
                return True, "✅ Aucun conflit à résoudre", 0
            
            # Récupérer les conflits
            conflicts = self.get_conflicts_details()
            
            if conflicts.empty:
                return True, "✅ Aucun conflit détecté", 0
            
            conflits_resolus = 0
            
            for idx, conflit in conflicts.iterrows():
                examen_id = conflit['Examen1']
                date_actuelle = conflit['Date/Heure']
                
                # Générer une nouvelle date (2 jours plus tard)
                try:
                    date_obj = datetime.strptime(str(date_actuelle), '%Y-%m-%d %H:%M:%S')
                    nouvelle_date = date_obj + timedelta(days=2)
                    nouvelle_date_str = nouvelle_date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Vérifier si la nouvelle date est disponible
                    success, error = self.safe_execute("""
                        SELECT COUNT(*) FROM examens_planifies 
                        WHERE salle_id = (
                            SELECT salle_id FROM examens_planifies WHERE id = %s
                        )
                        AND date_heure = %s
                        AND statut = 'VALIDE'
                    """, (examen_id, nouvelle_date_str))
                    
                    if success and self.cursor.fetchone()[0] == 0:
                        # Déplacer l'examen
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
            
            message = f"✅ Optimisation terminée en {temps_execution}s\n"
            message += f"📊 Conflits résolus: {conflits_resolus}\n"
            message += f"📈 Conflits restants: {conflits_apres}"
            
            return True, message, temps_execution
            
        except Exception as e:
            return False, f"❌ Erreur: {str(e)[:200]}", 0
    
    # ==================== FONCTION POUR VOIR LA STRUCTURE ====================
    
    def get_table_info(self):
        """Afficher les informations de la table pour debug"""
        try:
            # Structure
            self.cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'examens_planifies'
                ORDER BY ordinal_position
            """)
            structure = self.cursor.fetchall()
            
            # Contraintes CHECK
            self.cursor.execute("""
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'examens_planifies'::regclass
                AND contype = 'c'
            """)
            constraints = self.cursor.fetchall()
            
            return structure, constraints
            
        except Exception as e:
            return [], []
    
    # ==================== FONCTIONS DE DONNÉES ====================
    
    def get_generated_timetable(self, limit=100):
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
            WHERE ep.statut = 'VALIDE'
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
        
        # Total examens
        success, error = self.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'")
        if success:
            stats['total_examens'] = self.cursor.fetchone()[0]
        
        # Examens par jour
        success, error = self.safe_execute("""
            SELECT DATE(date_heure) as jour, COUNT(*) 
            FROM examens_planifies 
            WHERE statut = 'VALIDE'
            GROUP BY DATE(date_heure)
            ORDER BY DATE(date_heure)
        """)
        if success:
            data = self.cursor.fetchall()
            if data:
                stats['examens_par_jour'] = pd.DataFrame(data, columns=['Date', 'Examens'])
        
        # Répartition par département
        success, error = self.safe_execute("""
            SELECT d.nom, COUNT(ep.id) 
            FROM examens_planifies ep
            LEFT JOIN modules m ON ep.module_id = m.id
            LEFT JOIN formations f ON m.formation_id = f.id
            LEFT JOIN departements d ON f.dept_id = d.id
            WHERE ep.statut = 'VALIDE'
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
            WHERE ep.statut = 'VALIDE'
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
            WHERE ep.statut = 'VALIDE'
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
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN professeurs p ON ep.prof_id = p.id
            JOIN lieu_examen l ON ep.salle_id = l.id
            WHERE ep.statut = 'VALIDE'
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

# ==================== INTERFACE STREAMLIT ====================

def show_login_page():
    """Page de connexion"""
    st.title("🎓 Plateforme d'Optimisation des Examens")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Bienvenue")
        st.markdown("""
        **Fonctionnalités :**
        - 🤖 Génération AUTOMATIQUE d'emploi du temps
        - ✏️ Ajout MANUEL d'examens
        - ⚡ Détection et résolution des conflits
        - 📊 Interface multi-rôles
        
        **Objectifs :**
        - Génération en < 45 secondes
        - Résolution automatique des conflits
        - Optimisation de l'occupation
        """)
    
    with col2:
        st.header("🔐 Connexion")
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
    st.title("👨‍🎓 Tableau de bord Étudiant")
    st.markdown("---")
    
    # Filtres
    st.subheader("🔍 Filtres de recherche")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Sélection du département
        departments = platform.get_departments()
        dept_names = [d[1] for d in departments]
        selected_dept = st.selectbox("Département", ["Tous"] + dept_names)
    
    with col2:
        # Sélection de la formation si département choisi
        formation_options = ["Toutes"]
        if selected_dept != "Tous":
            dept_id = [d[0] for d in departments if d[1] == selected_dept][0]
            formations = platform.get_formations_by_department(dept_id)
            formation_options += [f[1] for f in formations]
        
        selected_formation = st.selectbox("Formation", formation_options)
    
    # Filtres de date
    col3, col4 = st.columns(2)
    with col3:
        date_debut = st.date_input("Date de début", datetime.now().date())
    with col4:
        date_fin = st.date_input("Date de fin", datetime.now().date() + timedelta(days=30))
    
    # Appliquer les filtres
    filters = {
        'departement': selected_dept if selected_dept != 'Tous' else None,
        'formation': selected_formation if selected_formation != 'Toutes' else None,
        'date_debut': f"{date_debut} 00:00:00",
        'date_fin': f"{date_fin} 23:59:59"
    }
    
    # Récupérer les examens filtrés
    exams_df = platform.get_student_exams(filters={k: v for k, v in filters.items() if v})
    
    if not exams_df.empty:
        st.subheader(f"📚 {len(exams_df)} examens trouvés")
        
        # Statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Examens", len(exams_df))
        with col2:
            st.metric("Départements", exams_df['Département'].nunique())
        with col3:
            st.metric("Formations", exams_df['Formation'].nunique())
        
        # Affichage des examens
        st.dataframe(exams_df, use_container_width=True, height=400)
        
        # Téléchargement
        csv = exams_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger le planning",
            data=csv,
            file_name=f"planning_examens_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # Visualisations
        st.subheader("📊 Visualisations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Examens par jour
            exams_df['Date'] = pd.to_datetime(exams_df['Date/Heure']).dt.date
            daily_counts = exams_df.groupby('Date').size().reset_index(name='Examens')
            
            fig = px.bar(daily_counts, x='Date', y='Examens',
                        title="Nombre d'examens par jour")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Répartition par département
            if selected_dept == "Tous":
                dept_counts = exams_df['Département'].value_counts().reset_index()
                dept_counts.columns = ['Département', 'Examens']
                
                fig = px.pie(dept_counts, values='Examens', names='Département',
                            title="Répartition par département")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 Aucun examen trouvé avec ces critères.")

def show_professeur_dashboard(platform):
    """Dashboard pour professeur"""
    st.title("👨‍🏫 Tableau de bord Professeur")
    st.markdown("---")
    
    # Sélection du professeur
    st.subheader("👤 Sélection du professeur")
    
    success, error = platform.safe_execute("""
        SELECT DISTINCT CONCAT(p.prenom, ' ', p.nom) as nom_complet
        FROM professeurs p
        JOIN examens_planifies ep ON p.id = ep.prof_id
        WHERE ep.statut = 'VALIDE'
        ORDER BY nom_complet
    """)
    
    if success:
        profs = platform.cursor.fetchall()
        prof_names = [p[0] for p in profs] if profs else ["Professeur Test"]
        
        if prof_names:
            selected_prof = st.selectbox("Sélectionnez votre nom", prof_names)
            
            # Récupérer les examens du professeur
            exams_df = platform.get_teacher_exams(teacher_name=selected_prof)
            
            if not exams_df.empty:
                st.subheader(f"📋 {len(exams_df)} surveillances programmées")
                
                # Statistiques
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Surveillances", len(exams_df))
                with col2:
                    unique_departements = exams_df['Département'].nunique()
                    st.metric("Départements", unique_departements)
                with col3:
                    total_duree = exams_df['Durée (min)'].sum()
                    st.metric("Heures totales", f"{total_duree/60:.1f}h")
                
                # Affichage des examens
                st.dataframe(exams_df, use_container_width=True, height=400)
                
                # Calendrier des examens
                st.subheader("🗓️ Calendrier des surveillances")
                
                # Convertir pour affichage calendrier
                exams_df['Date'] = pd.to_datetime(exams_df['Date/Heure']).dt.date
                exams_df['Heure'] = pd.to_datetime(exams_df['Date/Heure']).dt.strftime('%H:%M')
                
                # Afficher par jour
                unique_dates = sorted(exams_df['Date'].unique())
                
                for date in unique_dates:
                    with st.expander(f"📅 {date.strftime('%A %d %B %Y')}"):
                        day_exams = exams_df[exams_df['Date'] == date]
                        for _, exam in day_exams.iterrows():
                            st.write(f"**{exam['Heure']}** - {exam['Module']}")
                            st.write(f"📍 {exam['Salle']} | 📍 {exam['Département']} | ⏱️ {exam['Durée (min)']} min")
                            st.markdown("---")
                
                # Téléchargement
                csv = exams_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Télécharger mes surveillances",
                    data=csv,
                    file_name=f"surveillances_{selected_prof.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("📭 Aucune surveillance programmée pour ce professeur.")
        else:
            st.warning("⚠️ Aucun professeur n'a d'examens programmés.")
    else:
        st.error("❌ Erreur lors de la récupération des professeurs.")

def show_chef_departement_dashboard(platform):
    """Dashboard pour chef de département"""
    st.title("📊 Tableau de bord Chef de Département")
    st.markdown("---")
    
    # Sélection du département
    departments = platform.get_departments()
    dept_names = [d[1] for d in departments]
    
    if not dept_names:
        st.error("❌ Aucun département trouvé")
        return
    
    selected_dept = st.selectbox("Votre département", dept_names)
    
    st.markdown(f"### Département : **{selected_dept}**")
    
    # Onglets
    tab1, tab2 = st.tabs(["📈 Vue d'ensemble", "📋 Examens"])
    
    with tab1:
        # Statistiques du département
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT ep.id) 
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut = 'VALIDE'
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
                WHERE d.nom = %s AND ep.statut = 'VALIDE'
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
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            # Examens par formation
            success, error = platform.safe_execute("""
                SELECT f.nom, COUNT(ep.id) as examens
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                WHERE d.nom = %s AND ep.statut = 'VALIDE'
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
    
    with tab2:
        # Liste des examens du département
        exams_df = platform.get_department_exams(selected_dept)
        
        if not exams_df.empty:
            st.subheader(f"📋 {len(exams_df)} examens dans le département")
            
            st.dataframe(exams_df, use_container_width=True, height=400)
            
            # Téléchargement
            csv = exams_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger la liste",
                data=csv,
                file_name=f"examens_{selected_dept.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("📭 Aucun examen trouvé pour ce département.")

def show_administrateur_dashboard(platform):
    """Dashboard administrateur"""
    st.title("⚙️ Tableau de bord Administrateur")
    st.markdown("---")
    
    # Initialiser la variable de session
    if 'reset_before_generate' not in st.session_state:
        st.session_state.reset_before_generate = True
    
    # ==================== SECTION DE DÉBOGAGE ====================
    with st.sidebar:
        st.subheader("🔧 Outils de débogage")
        
        if st.button("📋 Voir structure table"):
            structure, constraints = platform.get_table_info()
            
            st.write("**Structure de examens_planifies:**")
            for col in structure:
                st.write(f"- {col[0]}: {col[1]} (NULL: {col[2]}, Default: {col[3]})")
            
            if constraints:
                st.write("**Contraintes CHECK:**")
                for conname, condef in constraints:
                    st.write(f"- {conname}: {condef}")
            else:
                st.write("Aucune contrainte CHECK trouvée")
        
        if st.button("🧹 Test réinitialisation simple"):
            with st.spinner("Test en cours..."):
                success, message = platform.reset_all_exams()
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    # Vérification initiale
    if platform.check_initial_state():
        st.success("✅ Base prête pour la planification (0 examens existants)")
    else:
        st.warning("⚠️ Il y a déjà des examens planifiés")
        
        # Bouton de réinitialisation
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Réinitialiser", type="secondary", use_container_width=True):
                with st.spinner("Réinitialisation en cours..."):
                    success, message = platform.reset_all_exams()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    st.markdown("---")
    
    # Onglets principaux
    tab1, tab2, tab3, tab4 = st.tabs(["🤖 Génération AUTO", "✏️ Ajout MANUEL", "📋 EDT Généré", "⚡ Optimisation"])
    
    # TAB 1: GÉNÉRATION AUTO
    with tab1:
        st.subheader("🤖 Génération d'Emploi du Temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nb_examens = st.slider("Nombre d'examens", 10, 50, 20)
            duree_moyenne = st.select_slider("Durée (minutes)", [60, 90, 120, 150, 180], value=120)
            
            # Option de réinitialisation avant génération
            st.session_state.reset_before_generate = st.checkbox(
                "Réinitialiser avant de générer", value=True
            )
            
            st.markdown("---")
            st.info("""
            **Mode de génération :**
            - Tente plusieurs méthodes d'insertion
            - Gère les contraintes CHECK automatiquement
            - Utilise autocommit=True pour éviter les erreurs de transaction
            """)
        
        with col2:
            # Statistiques
            success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'")
            if success:
                total_examens = platform.cursor.fetchone()[0]
                st.metric("Examens existants", total_examens)
            
            # Conflits actuels
            conflits = platform.count_conflicts()
            if conflits > 0:
                st.error(f"⚠️ {conflits} conflit(s)")
            else:
                st.success("✅ Aucun conflit")
            
            # Temps estimé
            st.info(f"⏱️ Temps estimé: {nb_examens * 0.2:.1f}s")
            
            # Bouton de test
            st.markdown("---")
            if st.button("🧪 Test génération (5 examens)"):
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
        
        # Bouton de génération principal
        st.markdown("---")
        if st.button("🚀 GÉNÉRER L'EMPLOI DU TEMPS", type="primary", use_container_width=True):
            with st.spinner("Génération en cours..."):
                # Réinitialiser si demandé
                if st.session_state.reset_before_generate:
                    platform.reset_all_exams()
                
                # Générer
                succes, message, temps_exec, details = platform.generate_simple_timetable(
                    nb_examens=nb_examens,
                    duree_minutes=duree_moyenne
                )
                
                if succes:
                    st.success(f"✅ {message}")
                    st.metric("Temps d'exécution", f"{temps_exec}s")
                    
                    if temps_exec <= 45:
                        st.balloons()
                        st.success("🎉 OBJECTIF ATTEINT: < 45 secondes!")
                    
                    # Afficher les détails
                    with st.expander("📊 Détails de la génération"):
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
                    st.error(f"❌ {message}")
                    
                    if 'echecs_details' in details and details['echecs_details']:
                        with st.expander("🔍 Voir les erreurs détaillées"):
                            for err in details['echecs_details']:
                                st.write(f"- {err}")
    
    # TAB 2: AJOUT MANUEL
    with tab2:
        st.subheader("✏️ Ajout Manuel d'Examen")
        
        # Récupérer les données pour les listes déroulantes
        modules = platform.get_modules_sans_examen()
        professeurs = platform.get_all_professeurs()
        salles = platform.get_all_salles()
        
        if not modules:
            st.error("❌ Tous les modules ont déjà un examen planifié!")
        else:
            # Formulaire de saisie
            with st.form("form_ajout_manuel"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Sélection du module
                    module_options = {f"{m[1]} ({m[3]} - {m[2]})": m[0] for m in modules}
                    module_choice = st.selectbox("Module à planifier", list(module_options.keys()))
                    module_id = module_options[module_choice]
                    
                    # Sélection du professeur
                    prof_options = {p[1]: p[0] for p in professeurs}
                    prof_choice = st.selectbox("Professeur responsable", list(prof_options.keys()))
                    prof_id = prof_options[prof_choice]
                
                with col2:
                    # Sélection de la salle
                    salle_options = {f"{s[1]} ({s[2]}, {s[3]} places)": s[0] for s in salles}
                    salle_choice = st.selectbox("Salle d'examen", list(salle_options.keys()))
                    salle_id = salle_options[salle_choice]
                    
                    # Date et heure
                    date_examen = st.date_input("Date de l'examen", datetime.now().date() + timedelta(days=7))
                    heure_examen = st.selectbox("Heure de début", ["08:30", "10:45", "14:00", "16:15"])
                    date_heure = f"{date_examen} {heure_examen}:00"
                    
                    # Durée
                    duree_minutes = st.selectbox("Durée (minutes)", [60, 90, 120, 150, 180])
                
                # Aperçu de la saisie
                st.markdown("---")
                st.subheader("📋 Aperçu de l'examen")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Module :** {module_choice}")
                    st.write(f"**Professeur :** {prof_choice}")
                with col_b:
                    st.write(f"**Salle :** {salle_choice}")
                    st.write(f"**Date/Heure :** {date_heure}")
                    st.write(f"**Durée :** {duree_minutes} minutes")
                
                # Bouton de soumission
                submitted = st.form_submit_button("➕ AJOUTER L'EXAMEN", type="primary", use_container_width=True)
                
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
    
    # TAB 3: AFFICHAGE EDT
    with tab3:
        st.subheader("📋 Emploi du Temps Généré")
        
        show_limit = st.selectbox("Nombre d'examens à afficher", [20, 50, 100, 200], index=0)
        timetable = platform.get_generated_timetable(limit=show_limit)
        
        if not timetable.empty:
            st.write(f"**📊 {len(timetable)} examens planifiés**")
            
            # Statistiques rapides
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
            
            # Affichage
            display_cols = ['date_heure', 'module', 'departement', 'salle', 'professeur', 'duree_minutes', 'mode_generation']
            available_cols = [col for col in display_cols if col in timetable.columns]
            
            if available_cols:
                st.dataframe(
                    timetable[available_cols],
                    use_container_width=True,
                    height=400
                )
            
            # Téléchargement
            csv = timetable[available_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger l'EDT",
                data=csv,
                file_name=f"emploi_du_temps_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Bouton de réinitialisation
            st.markdown("---")
            if st.button("🧹 Réinitialiser cet emploi du temps", type="secondary"):
                with st.spinner("Réinitialisation en cours..."):
                    success, message = platform.reset_all_exams()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        else:
            st.info("📭 Aucun emploi du temps généré")
            
            # Suggestions
            if st.button("🎲 Générer un EDT (10 examens)"):
                with st.spinner("Génération en cours..."):
                    platform.reset_all_exams()
                    succes, message, temps_exec, details = platform.generate_simple_timetable(
                        nb_examens=10,
                        duree_minutes=120
                    )
                    
                    if succes:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    # TAB 4: OPTIMISATION
    with tab4:
        st.subheader("⚡ Optimisation des Conflits")
        
        # État actuel des conflits
        conflits_actuels = platform.count_conflicts()
        
        if conflits_actuels == 0:
            st.success("✅ Aucun conflit détecté!")
        else:
            st.error(f"⚠️ {conflits_actuels} conflit(s) détecté(s)")
            
            # Détails des conflits
            if st.button("🔍 Voir les détails des conflits"):
                conflicts_df = platform.get_conflicts_details()
                if not conflicts_df.empty:
                    st.dataframe(conflicts_df, use_container_width=True)
                else:
                    st.info("ℹ️ Aucun détail disponible")
        
        st.markdown("---")
        
        # Bouton d'optimisation
        if st.button("🚀 Lancer l'optimisation", use_container_width=True):
            with st.spinner("Optimisation en cours..."):
                succes, message, temps_exec = platform.optimize_timetable(mode='RAPIDE')
                
                if succes:
                    st.success(message)
                    st.metric("Temps", f"{temps_exec}s")
                    st.rerun()
                else:
                    st.error(message)

def show_doyen_dashboard(platform):
    """Dashboard vice-doyen/doyen"""
    st.title("🎓 Tableau de bord Direction")
    st.markdown("---")
    
    # KPIs principaux
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'")
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
    
    st.markdown("---")
    
    # Onglets
    tab1, tab2 = st.tabs(["📈 Vue globale", "⚠️ Conflits"])
    
    with tab1:
        st.subheader("Vue d'ensemble")
        
        # Statistiques
        stats = platform.get_timetable_statistics()
        
        if 'examens_par_jour' in stats and not stats['examens_par_jour'].empty:
            df_daily = stats['examens_par_jour']
            df_daily['Date'] = pd.to_datetime(df_daily['Date'])
            fig = px.bar(df_daily, x='Date', y='Examens', title="Examens par jour")
            st.plotly_chart(fig, use_container_width=True)
        
        if 'repartition_par_departement' in stats and not stats['repartition_par_departement'].empty:
            df_dept = stats['repartition_par_departement']
            fig = px.pie(df_dept, values='Examens', names='Département', title="Répartition par département")
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Analyse des Conflits")
        
        conflits = platform.count_conflicts()
        
        if conflits == 0:
            st.success("✅ Aucun conflit détecté")
        else:
            st.error(f"⚠️ {conflits} conflit(s) détecté(s)")
            
            # Détails des conflits
            conflicts_df = platform.get_conflicts_details()
            if not conflicts_df.empty:
                st.dataframe(conflicts_df, use_container_width=True)

def main():
    """Fonction principale"""
    
    # Initialiser
    platform = ExamPlatform()
    
    if not platform.conn:
        st.error("❌ Connexion base de données échouée")
        st.stop()
    
    # Gestion de session
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    
    # Afficher la page
    if st.session_state.get('role') is None:
        show_login_page()
    else:
        # Sidebar
        with st.sidebar:
            st.image("https://img.icons8.com/color/96/000000/university.png", width=80)
            st.success(f"👤 Connecté: **{st.session_state['role']}**")
            
            # Statistiques rapides
            if st.session_state['role'] in ["Administrateur", "Vice-doyen/Doyen", "Chef de département"]:
                success, error = platform.safe_execute("SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'")
                if success:
                    total_examens = platform.cursor.fetchone()[0]
                    st.metric("Examens planifiés", total_examens)
                
                conflits = platform.count_conflicts()
                if conflits > 0:
                    st.error(f"⚠️ {conflits} conflit(s)")
                else:
                    st.success("✅ Aucun conflit")
            
            st.markdown("---")
            if st.button("🚪 Déconnexion", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        # Router
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
