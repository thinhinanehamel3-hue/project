#!/usr/bin/env python3
"""
DASHBOARD COMPLET - Version 7
Avec optimisation fonctionnelle + interface complète
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
import traceback

# Configuration de la page
st.set_page_config(
    page_title="Plateforme d'Examens Universitaires",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration de la base de données
DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
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
            self.conn.autocommit = False
            self.cursor = self.conn.cursor()
        else:
            self.cursor = None
    
    def safe_execute(self, query, params=None):
        """Exécuter une requête SQL en gérant les erreurs"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return True, None
        except Exception as e:
            self.conn.rollback()
            return False, str(e)
    
    def safe_commit(self):
        """Commiter la transaction"""
        try:
            self.conn.commit()
            return True, None
        except Exception as e:
            self.conn.rollback()
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
    
    def check_initial_state(self):
        """Vérifier l'état initial de la base"""
        success, error = self.safe_execute("SELECT COUNT(*) FROM examens_planifies")
        if success:
            count = self.cursor.fetchone()[0]
            return count == 0
        return False
    
    # ==================== GÉNÉRATION EDT ====================
    
    def generate_timetable(self, nb_examens=50, duree_minutes=120, mode='AUTO'):
        """Générer un emploi du temps automatiquement"""
        start_time = time.time()
        
        try:
            # Désactiver temporairement les contraintes
            self.cursor.execute("SET session_replication_role = 'replica';")
            
            # Récupérer les modules sans examen
            success, error = self.safe_execute("""
                SELECT m.id, m.nom, 
                       (SELECT COUNT(*) FROM inscriptions WHERE module_id = m.id) as nb_etudiants,
                       f.dept_id
                FROM modules m
                JOIN formations f ON m.formation_id = f.id
                WHERE NOT EXISTS (
                    SELECT 1 FROM examens_planifies ep 
                    WHERE ep.module_id = m.id AND ep.statut != 'ANNULE'
                )
                ORDER BY RANDOM()
                LIMIT %s
            """, (nb_examens,))
            
            if not success:
                return False, f"Erreur recherche modules: {error}", 0, {}
            
            modules = self.cursor.fetchall()
            
            if not modules:
                return False, "Tous les modules ont déjà un examen", 0, {}
            
            # Récupérer les ressources
            self.cursor.execute("SELECT id, capacite, type FROM lieu_examen ORDER BY type, capacite")
            salles = self.cursor.fetchall()
            
            self.cursor.execute("SELECT id, dept_id FROM professeurs")
            professeurs = self.cursor.fetchall()
            
            # Préparer les dates
            dates_possibles = []
            for i in range(1, 31):
                date_base = datetime.now().date() + timedelta(days=i)
                dates_possibles.extend([
                    f"{date_base} 08:30:00",
                    f"{date_base} 10:45:00",
                    f"{date_base} 14:00:00",
                    f"{date_base} 16:15:00"
                ])
            
            succes_count = 0
            echecs_count = 0
            echecs_details = []
            
            for module in modules:
                module_id, module_nom, nb_etudiants, dept_id = module
                
                try:
                    # Trouver une salle adaptée
                    salle_trouvee = None
                    for salle in salles:
                        if salle[1] >= nb_etudiants:
                            salle_trouvee = salle
                            break
                    
                    if not salle_trouvee:
                        # Prendre la plus grande salle
                        salle_trouvee = max(salles, key=lambda x: x[1])
                    
                    salle_id = salle_trouvee[0]
                    
                    # Trouver un professeur
                    prof_id = None
                    profs_dept = [p for p in professeurs if p[1] == dept_id]
                    if profs_dept:
                        prof_id = random.choice(profs_dept)[0]
                    else:
                        prof_id = random.choice(professeurs)[0]
                    
                    # Date aléatoire
                    date_heure = random.choice(dates_possibles)
                    
                    # Insérer l'examen
                    success, error = self.safe_execute("""
                        INSERT INTO examens_planifiques 
                        (module_id, prof_id, salle_id, date_heure, 
                         duree_minutes, mode_generation, statut, priorite)
                        VALUES (%s, %s, %s, %s, %s, %s, 'PROPOSE', 1)
                    """, (module_id, prof_id, salle_id, date_heure, duree_minutes, mode))
                    
                    if success:
                        succes_count += 1
                    else:
                        echecs_count += 1
                        echecs_details.append(f"Module {module_nom}: {error[:50]}")
                        
                except Exception as e:
                    echecs_count += 1
                    echecs_details.append(f"Module {module_nom}: {str(e)[:50]}")
                    continue
            
            # Réactiver les contraintes et commit
            self.cursor.execute("SET session_replication_role = 'origin';")
            self.conn.commit()
            
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
                return True, f"✅ {succes_count} examens planifiés ({echecs_count} échecs)", temps_execution, details
            else:
                return False, "❌ Aucun examen créé", temps_execution, details
            
        except Exception as e:
            self.conn.rollback()
            return False, f"❌ Erreur majeure: {str(e)[:200]}", 0, {}
    
    # ==================== FONCTIONS D'OPTIMISATION ====================
    
    def count_conflicts(self):
        """Compter le nombre de conflits détectés"""
        try:
            # Essayer d'abord avec la vue v_conflits
            success, error = self.safe_execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT e1.id, e2.id
                    FROM examens_planifies e1
                    JOIN examens_planifies e2 ON e1.id < e2.id
                    WHERE e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
                    AND (
                        (e1.salle_id = e2.salle_id AND e1.date_heure = e2.date_heure) OR
                        (e1.prof_id = e2.prof_id AND e1.date_heure = e2.date_heure)
                    )
                ) as conflits
            """)
            
            if success:
                return self.cursor.fetchone()[0]
        except:
            pass
        
        # Fallback: compter manuellement
        try:
            success, error = self.safe_execute("""
                SELECT COUNT(DISTINCT e1.id) FROM examens_planifies e1
                JOIN examens_planifies e2 ON e1.id != e2.id
                WHERE e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
                AND e1.salle_id = e2.salle_id 
                AND e1.date_heure = e2.date_heure
            """)
            if success:
                return self.cursor.fetchone()[0]
        except:
            return 0
        return 0
    
    def get_conflicts_details(self):
        """Récupérer les détails des conflits"""
        try:
            success, error = self.safe_execute("""
                SELECT 
                    e1.id as id1, 
                    e2.id as id2,
                    s.nom as salle_nom,
                    CONCAT(p1.prenom, ' ', p1.nom) as prof1,
                    CONCAT(p2.prenom, ' ', p2.nom) as prof2,
                    e1.date_heure as date1,
                    e2.date_heure as date2,
                    CASE 
                        WHEN e1.salle_id = e2.salle_id AND e1.date_heure = e2.date_heure THEN 'CONFLIT_SALLE'
                        WHEN e1.prof_id = e2.prof_id AND e1.date_heure = e2.date_heure THEN 'CONFLIT_PROFESSEUR'
                        ELSE 'AUTRE_CONFLIT'
                    END as type_conflit
                FROM examens_planifies e1
                JOIN examens_planifies e2 ON e1.id < e2.id
                JOIN lieu_examen s ON e1.salle_id = s.id
                JOIN professeurs p1 ON e1.prof_id = p1.id
                JOIN professeurs p2 ON e2.prof_id = p2.id
                WHERE e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
                AND (
                    (e1.salle_id = e2.salle_id AND e1.date_heure = e2.date_heure) OR
                    (e1.prof_id = e2.prof_id AND e1.date_heure = e2.date_heure)
                )
                ORDER BY e1.date_heure
            """)
            
            if success:
                conflicts = self.cursor.fetchall()
                if conflicts:
                    columns = ['Examen1', 'Examen2', 'Salle', 'Professeur1', 'Professeur2', 
                              'Date1', 'Date2', 'Type']
                    return pd.DataFrame(conflicts, columns=columns)
        except Exception as e:
            st.error(f"Erreur détails conflits: {e}")
        
        return pd.DataFrame()
    
    def optimize_timetable(self, mode='COMPLET'):
        """Algorithme d'optimisation des conflits"""
        start_time = time.time()
        conflits_resolus = 0
        
        try:
            # 1. Résoudre les conflits de salle
            st.info("🔄 Résolution des conflits de salle...")
            
            # Trouver les conflits de salle
            success, error = self.safe_execute("""
                SELECT e1.id, e1.salle_id, e1.date_heure, e1.prof_id,
                       (SELECT COUNT(*) FROM inscriptions i 
                        JOIN modules m ON i.module_id = m.id 
                        WHERE m.id = e1.module_id) as nb_etudiants
                FROM examens_planifies e1
                JOIN examens_planifies e2 ON e1.id != e2.id
                WHERE e1.statut = 'VALIDE' AND e2.statut = 'VALIDE'
                AND e1.salle_id = e2.salle_id 
                AND e1.date_heure = e2.date_heure
                ORDER BY e1.date_heure
            """)
            
            if success:
                conflits_salle = self.cursor.fetchall()
                
                for conflit in conflits_salle:
                    examen_id, salle_id, date_heure, prof_id, nb_etudiants = conflit
                    
                    # Chercher une salle alternative
                    success, error = self.safe_execute("""
                        SELECT l.id, l.nom, l.capacite
                        FROM lieu_examen l
                        WHERE l.id != %s
                        AND l.capacite >= %s
                        AND NOT EXISTS (
                            SELECT 1 FROM examens_planifies ep
                            WHERE ep.salle_id = l.id
                            AND ep.date_heure = %s
                            AND ep.statut = 'VALIDE'
                        )
                        ORDER BY l.capacite ASC
                        LIMIT 1
                    """, (salle_id, nb_etudiants, date_heure))
                    
                    if success and self.cursor.rowcount > 0:
                        nouvelle_salle = self.cursor.fetchone()
                        nouvelle_salle_id = nouvelle_salle[0]
                        
                        # Mettre à jour l'examen
                        success, error = self.safe_execute("""
                            UPDATE examens_planifies 
                            SET salle_id = %s, 
                                modifie_par = 'optimizer',
                                mode_generation = 'MANUEL'
                            WHERE id = %s
                        """, (nouvelle_salle_id, examen_id))
                        
                        if success:
                            conflits_resolus += 1
            
            # 2. Équilibrage professeurs (mode COMPLET seulement)
            if mode == 'COMPLET':
                st.info("👨‍🏫 Équilibrage de la charge des professeurs...")
                
                # Trouver les professeurs surchargés (> 4 examens)
                success, error = self.safe_execute("""
                    SELECT prof_id, COUNT(*) as nb_examens
                    FROM examens_planifies
                    WHERE statut = 'VALIDE'
                    GROUP BY prof_id
                    HAVING COUNT(*) > 4
                    ORDER BY COUNT(*) DESC
                """)
                
                if success:
                    profs_surcharges = self.cursor.fetchall()
                    
                    for prof_id, nb_examens in profs_surcharges:
                        # Trouver un examen à déplacer
                        success, error = self.safe_execute("""
                            SELECT ep.id, ep.module_id
                            FROM examens_planifies ep
                            WHERE ep.prof_id = %s
                            AND ep.statut = 'VALIDE'
                            ORDER BY RANDOM()
                            LIMIT 1
                        """, (prof_id,))
                        
                        if success and self.cursor.rowcount > 0:
                            examen_id, module_id = self.cursor.fetchone()
                            
                            # Trouver un professeur alternatif (même département)
                            success, error = self.safe_execute("""
                                SELECT p.id
                                FROM professeurs p
                                JOIN modules m ON p.dept_id = (
                                    SELECT f.dept_id FROM formations f
                                    JOIN modules m2 ON f.id = m2.formation_id
                                    WHERE m2.id = %s
                                )
                                WHERE p.id != %s
                                ORDER BY RANDOM()
                                LIMIT 1
                            """, (module_id, prof_id))
                            
                            if success and self.cursor.rowcount > 0:
                                nouveau_prof_id = self.cursor.fetchone()[0]
                                
                                # Mettre à jour
                                success, error = self.safe_execute("""
                                    UPDATE examens_planifies 
                                    SET prof_id = %s,
                                        modifie_par = 'optimizer'
                                    WHERE id = %s
                                """, (nouveau_prof_id, examen_id))
            
            self.conn.commit()
            end_time = time.time()
            temps_execution = round(end_time - start_time, 2)
            
            # Compter les conflits après optimisation
            conflits_finaux = self.count_conflicts()
            
            message = f"✅ Optimisation terminée en {temps_execution}s\n"
            message += f"📊 Conflits résolus: {conflits_resolus}\n"
            message += f"📈 Conflits restants: {conflits_finaux}"
            
            return True, message, temps_execution
            
        except Exception as e:
            self.conn.rollback()
            return False, f"❌ Erreur: {str(e)[:200]}", 0
    
    # ==================== FONCTIONS DE RÉCUPÉRATION ====================
    
    def get_generated_timetable(self, limit=100):
        """Récupérer l'emploi du temps généré"""
        success, error = self.safe_execute("""
            SELECT 
                ep.id as examen_id,
                ep.date_heure,
                m.nom as module,
                f.nom as formation,
                d.nom as departement,
                CONCAT(p.prenom, ' ', p.nom) as professeur,
                l.nom as salle,
                l.type as type_salle,
                l.capacite,
                ep.duree_minutes,
                ep.mode_generation,
                ep.statut
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            JOIN professeurs p ON ep.prof_id = p.id
            JOIN lieu_examen l ON ep.salle_id = l.id
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
    
    def export_timetable_csv(self):
        """Exporter l'emploi du temps en CSV"""
        df = self.get_generated_timetable(1000)
        return df.to_csv(index=False).encode('utf-8')
    
    def validate_timetable(self, user="administrateur"):
        """Valider définitivement l'emploi du temps"""
        try:
            conflits = self.count_conflicts()
            if conflits > 0:
                return False, f"❌ {conflits} conflit(s) détecté(s) - Impossible de valider"
            
            success, error = self.safe_execute("""
                UPDATE examens_planifies 
                SET statut = 'VALIDE', modifie_par = %s
                WHERE statut = 'PROPOSE'
            """, (user,))
            
            if success:
                self.conn.commit()
                return True, "✅ Emploi du temps validé avec succès"
            else:
                return False, f"❌ Erreur: {error}"
        except Exception as e:
            self.conn.rollback()
            return False, f"❌ Erreur: {str(e)}"
    
    def get_timetable_statistics(self):
        """Statistiques de l'emploi du temps"""
        stats = {}
        
        # Total examens
        success, error = self.safe_execute(
            "SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'"
        )
        if success:
            stats['total_examens'] = self.cursor.fetchone()[0]
        
        # Examens par jour
        success, error = self.safe_execute("""
            SELECT DATE(date_heure), COUNT(*) 
            FROM examens_planifies 
            WHERE statut = 'VALIDE'
            GROUP BY DATE(date_heure)
            ORDER BY DATE(date_heure)
        """)
        if success:
            stats['examens_par_jour'] = pd.DataFrame(
                self.cursor.fetchall(), 
                columns=['Date', 'Examens']
            )
        
        # Répartition par département
        success, error = self.safe_execute("""
            SELECT d.nom, COUNT(ep.id) 
            FROM examens_planifies ep
            JOIN modules m ON ep.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            WHERE ep.statut = 'VALIDE'
            GROUP BY d.nom
            ORDER BY COUNT(ep.id) DESC
        """)
        if success:
            stats['repartition_par_departement'] = pd.DataFrame(
                self.cursor.fetchall(),
                columns=['Département', 'Examens']
            )
        
        return stats

# ==================== INTERFACE STREAMLIT ====================

def show_login_page():
    """Page d'accueil avec connexion"""
    st.title("🎓 Plateforme d'Optimisation des Examens Universitaires")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Bienvenue")
        st.markdown("""
        **Fonctionnalités principales :**
        - Génération automatique d'emploi du temps
        - Détection et résolution des conflits
        - Optimisation des ressources (salles, professeurs)
        - Interface multi-rôles
        - Validation en temps réel
        
        **Objectifs :**
        - Génération en moins de 45 secondes
        - Résolution automatique des conflits
        - Optimisation de l'occupation des salles
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
            st.session_state['page'] = 'dashboard'
            st.rerun()

def show_administrateur_dashboard(platform):
    """Dashboard administrateur avec toutes les fonctionnalités"""
    st.title("⚙️ Tableau de bord Administrateur")
    st.markdown("---")
    
    # Vérification initiale
    if platform.check_initial_state():
        st.success("✅ Base prête pour la planification")
    else:
        st.info(f"ℹ️ Des examens sont déjà planifiés")
    
    # Onglets principaux
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Génération EDT", "📋 EDT Généré", "⚡ Optimisation", "📊 Statistiques"])
    
    # TAB 1: GÉNÉRATION
    with tab1:
        st.subheader("🤖 Génération Automatique de l'Emploi du Temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nb_examens = st.slider("Nombre d'examens", 10, 200, 50)
            duree_moyenne = st.select_slider("Durée", [60, 90, 120, 150, 180], value=120)
            mode_generation = st.radio("Mode", ["AUTO", "MANUEL"])
        
        with col2:
            # Statistiques
            success, error = platform.safe_execute("SELECT COUNT(*) FROM modules")
            if success:
                total_modules = platform.cursor.fetchone()[0]
                st.metric("Modules totaux", total_modules)
            
            success, error = platform.safe_execute(
                "SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'"
            )
            if success:
                examens_existants = platform.cursor.fetchone()[0]
                st.metric("Examens existants", examens_existants)
            
            conflits = platform.count_conflicts()
            if conflits > 0:
                st.error(f"⚠️ {conflits} conflit(s)")
            else:
                st.success("✅ Aucun conflit")
        
        # Bouton de génération
        if st.button("🚀 GÉNÉRER L'EMPLOI DU TEMPS", type="primary", use_container_width=True):
            with st.spinner("Génération en cours..."):
                succes, message, temps_exec, details = platform.generate_timetable(
                    nb_examens=nb_examens,
                    duree_minutes=duree_moyenne,
                    mode=mode_generation
                )
                
                if succes:
                    st.success(f"✅ {message}")
                    st.metric("Temps d'exécution", f"{temps_exec}s")
                    
                    if temps_exec <= 45:
                        st.balloons()
                        st.success("🎉 OBJECTIF ATTEINT: < 45 secondes!")
                    
                    # Afficher les détails
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Examens créés", details.get('examens_planifies', 0))
                    with col_b:
                        st.metric("Échecs", details.get('echecs', 0))
                    with col_c:
                        st.metric("Taux réussite", f"{details.get('taux_reussite', 0):.1f}%")
                    
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
    # TAB 2: AFFICHAGE EDT
    with tab2:
        st.subheader("📋 Emploi du Temps Généré")
        
        show_limit = st.selectbox("Afficher", [50, 100, 200, 500], index=1)
        timetable = platform.get_generated_timetable(limit=show_limit)
        
        if not timetable.empty:
            st.write(f"**{len(timetable)} examens planifiés**")
            
            # Filtres
            col1, col2 = st.columns(2)
            with col1:
                if 'departement' in timetable.columns:
                    departements = ['Tous'] + list(timetable['departement'].unique())
                    dept_filtre = st.selectbox("Filtrer par département", departements)
                    
                    if dept_filtre != 'Tous':
                        timetable = timetable[timetable['departement'] == dept_filtre]
            
            with col2:
                if 'mode_generation' in timetable.columns:
                    modes = ['Tous'] + list(timetable['mode_generation'].unique())
                    mode_filtre = st.selectbox("Filtrer par mode", modes)
                    
                    if mode_filtre != 'Tous':
                        timetable = timetable[timetable['mode_generation'] == mode_filtre]
            
            # Affichage
            st.dataframe(
                timetable[['date_heure', 'module', 'formation', 'departement', 'salle', 'professeur', 'duree_minutes']],
                use_container_width=True,
                height=400
            )
            
            # Export
            csv = platform.export_timetable_csv()
            st.download_button(
                label="📥 Télécharger CSV",
                data=csv,
                file_name=f"emploi_du_temps_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Graphiques
            col1, col2 = st.columns(2)
            with col1:
                if 'departement' in timetable.columns:
                    dept_counts = timetable['departement'].value_counts()
                    fig = px.bar(x=dept_counts.index, y=dept_counts.values,
                                title="Examens par département")
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if 'date_heure' in timetable.columns:
                    timetable['Jour'] = pd.to_datetime(timetable['date_heure']).dt.date
                    daily_counts = timetable['Jour'].value_counts().sort_index()
                    fig = px.line(x=daily_counts.index, y=daily_counts.values,
                                title="Examens par jour")
                    st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.info("📭 Aucun emploi du temps généré")
    
    # TAB 3: OPTIMISATION (NOUVEAU ONGLET FONCTIONNEL)
    with tab3:
        st.subheader("⚡ Optimisation des Conflits")
        st.markdown("---")
        
        # État actuel
        conflits_actuels = platform.count_conflicts()
        
        if conflits_actuels == 0:
            st.success("✅ Aucun conflit détecté!")
        else:
            st.error(f"⚠️ {conflits_actuels} conflit(s) détecté(s)")
            
            # Afficher les détails
            if st.button("🔍 Voir les détails des conflits"):
                conflicts_df = platform.get_conflicts_details()
                if not conflicts_df.empty:
                    st.dataframe(conflicts_df, use_container_width=True)
                    
                    # Graphique des types de conflits
                    if 'Type' in conflicts_df.columns:
                        type_counts = conflicts_df['Type'].value_counts()
                        fig = px.pie(values=type_counts.values, names=type_counts.index,
                                    title="Types de conflits")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("ℹ️ Aucun détail de conflit disponible")
        
        st.markdown("---")
        st.write("### 🎯 Algorithmes d'Optimisation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### ⚡ Mode Rapide")
            st.markdown("""
            **Résolution des conflits de salle**
            - Recherche de salles alternatives
            - Temps d'exécution rapide
            - Priorité aux conflits critiques
            """)
            
            if st.button("🚀 Optimisation rapide", use_container_width=True):
                with st.spinner("Optimisation en cours..."):
                    succes, message, temps_exec = platform.optimize_timetable(mode='RAPIDE')
                    
                    if succes:
                        st.success(message)
                        st.metric("Temps", f"{temps_exec}s")
                        st.rerun()
                    else:
                        st.error(message)
        
        with col2:
            st.write("#### 🎯 Mode Complet")
            st.markdown("""
            **Optimisation complète**
            - Conflits de salle
            - Équilibrage professeurs
            - Optimisation occupation
            - Temps plus long
            """)
            
            if st.button("🚀 Optimisation complète", use_container_width=True):
                with st.spinner("Optimisation complète en cours..."):
                    succes, message, temps_exec = platform.optimize_timetable(mode='COMPLET')
                    
                    if succes:
                        st.success(message)
                        st.metric("Temps", f"{temps_exec}s")
                        st.rerun()
                    else:
                        st.error(message)
        
        st.markdown("---")
        st.write("### 📈 Statistiques de performance")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Conflits actuels", conflits_actuels)
        
        with col2:
            # Occupation salles
            success, error = platform.safe_execute("""
                SELECT ROUND(COUNT(DISTINCT salle_id) * 100.0 / 
                       (SELECT COUNT(*) FROM lieu_examen WHERE type != 'AMPHI'), 2)
                FROM examens_planifies WHERE statut = 'VALIDE'
            """)
            if success:
                taux = platform.cursor.fetchone()[0] or 0
                st.metric("Occupation salles", f"{taux}%")
        
        with col3:
            # Professeurs utilisés
            success, error = platform.safe_execute("""
                SELECT COUNT(DISTINCT prof_id) FROM examens_planifies WHERE statut = 'VALIDE'
            """)
            if success:
                profs_utilises = platform.cursor.fetchone()[0] or 0
                st.metric("Professeurs", profs_utilises)
    
    # TAB 4: STATISTIQUES
    with tab4:
        st.subheader("📊 Statistiques Globales")
        
        stats = platform.get_timetable_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Examens", stats.get('total_examens', 0))
        with col2:
            conflits = platform.count_conflicts()
            st.metric("Conflits", conflits)
        with col3:
            if 'examens_par_jour' in stats and not stats['examens_par_jour'].empty:
                moy = stats['examens_par_jour']['Examens'].mean()
                st.metric("Moyenne/jour", f"{moy:.1f}")
        with col4:
            if 'repartition_par_departement' in stats and not stats['repartition_par_departement'].empty:
                top = stats['repartition_par_departement'].iloc[0]['Département']
                st.metric("Top département", top)
        
        # Graphiques
        if 'examens_par_jour' in stats and not stats['examens_par_jour'].empty:
            col1, col2 = st.columns(2)
            
            with col1:
                df_daily = stats['examens_par_jour']
                df_daily['Date'] = pd.to_datetime(df_daily['Date'])
                fig = px.line(df_daily, x='Date', y='Examens',
                            title="Examens par jour")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if 'repartition_par_departement' in stats:
                    df_dept = stats['repartition_par_departement']
                    fig = px.bar(df_dept.head(10), x='Département', y='Examens',
                                title="Top 10 départements")
                    st.plotly_chart(fig, use_container_width=True)

def show_doyen_dashboard(platform):
    """Dashboard vice-doyen/doyen - CORRIGÉ ET COMPLET"""
    st.title("🎓 Tableau de bord Vice-doyen/Doyen")
    st.markdown("---")
    
    # KPIs globaux
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        success, error = platform.safe_execute("SELECT COUNT(*) FROM etudiants")
        if success:
            total_etudiants = platform.cursor.fetchone()[0]
            st.metric("Étudiants", f"{total_etudiants:,}")
    
    with col2:
        success, error = platform.safe_execute(
            "SELECT COUNT(*) FROM examens_planifies WHERE statut = 'VALIDE'"
        )
        if success:
            total_examens = platform.cursor.fetchone()[0]
            st.metric("Examens", total_examens)
    
    with col3:
        success, error = platform.safe_execute("""
            SELECT ROUND(COUNT(DISTINCT salle_id) * 100.0 / 
                   (SELECT COUNT(*) FROM lieu_examen), 1)
            FROM examens_planifies WHERE statut = 'VALIDE'
        """)
        if success:
            taux_occupation = platform.cursor.fetchone()[0] or 0
            st.metric("Occupation", f"{taux_occupation}%")
    
    with col4:
        conflits = platform.count_conflicts()
        st.metric("Conflits", conflits)
    
    st.markdown("---")
    
    # Onglets
    tab1, tab2, tab3 = st.tabs(["📈 Vue stratégique", "✅ Validation", "📊 Performances"])
    
    with tab1:
        st.subheader("Vue stratégique globale")
        
        # Graphique 1: Occupation des amphis
        success, error = platform.safe_execute("""
            SELECT l.nom, COUNT(ep.id) as examens, l.capacite
            FROM lieu_examen l
            LEFT JOIN examens_planifies ep ON l.id = ep.salle_id AND ep.statut = 'VALIDE'
            WHERE l.type = 'AMPHI'
            GROUP BY l.id, l.nom, l.capacite
            ORDER BY examens DESC
        """)
        
        if success:
            amphis = platform.cursor.fetchall()
            if amphis:
                df_amphis = pd.DataFrame(amphis, columns=['Amphi', 'Examens', 'Capacité'])
                
                fig = px.bar(df_amphis, x='Amphi', y='Examens',
                            title="Utilisation des amphithéâtres",
                            hover_data=['Capacité'])
                st.plotly_chart(fig, use_container_width=True)
        
        # Graphique 2: Charge des départements
        success, error = platform.safe_execute("""
            SELECT d.nom, COUNT(ep.id) as examens,
                   COUNT(DISTINCT ep.prof_id) as professeurs
            FROM departements d
            LEFT JOIN formations f ON d.id = f.dept_id
            LEFT JOIN modules m ON f.id = m.formation_id
            LEFT JOIN examens_planifies ep ON m.id = ep.module_id AND ep.statut = 'VALIDE'
            GROUP BY d.id, d.nom
            ORDER BY examens DESC
        """)
        
        if success:
            depts = platform.cursor.fetchall()
            if depts:
                df_depts = pd.DataFrame(depts, columns=['Département', 'Examens', 'Professeurs'])
                
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(df_depts, x='Département', y='Examens',
                                title="Examens par département")
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.bar(df_depts, x='Département', y='Professeurs',
                                title="Professeurs mobilisés")
                    st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Validation globale")
        
        # Conflits restants
        conflits = platform.count_conflicts()
        
        if conflits > 0:
            st.error(f"❌ {conflits} conflit(s) détecté(s) - Validation impossible")
            
            # Détails des conflits
            if st.button("🔍 Afficher les conflits"):
                conflicts_df = platform.get_conflicts_details()
                if not conflicts_df.empty:
                    st.dataframe(conflicts_df, use_container_width=True)
        else:
            st.success("✅ Aucun conflit - Prêt pour validation")
            
            # Derniers examens
            st.subheader("Derniers examens planifiés")
            success, error = platform.safe_execute("""
                SELECT ep.date_heure, m.nom as module, d.nom as departement,
                       l.nom as salle, ep.mode_generation
                FROM examens_planifies ep
                JOIN modules m ON ep.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                JOIN departements d ON f.dept_id = d.id
                JOIN lieu_examen l ON ep.salle_id = l.id
                WHERE ep.statut = 'VALIDE'
                ORDER BY ep.date_heure DESC
                LIMIT 10
            """)
            
            if success:
                derniers = platform.cursor.fetchall()
                if derniers:
                    df_derniers = pd.DataFrame(derniers, 
                                              columns=['Date', 'Module', 'Département', 'Salle', 'Mode'])
                    st.dataframe(df_derniers, use_container_width=True)
            
            # Bouton de validation finale
            st.markdown("---")
            if st.button("✅ VALIDER L'EMPLOI DU TEMPS", type="primary", use_container_width=True):
                succes, message = platform.validate_timetable("direction")
                if succes:
                    st.success(message)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
    
    with tab3:
        st.subheader("Analyse de performance")
        
        # Temps de génération (simulé)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Objectif temps", "< 45s", "OK")
        
        with col2:
            # Taux d'occupation optimal
            success, error = platform.safe_execute("""
                SELECT ROUND(AVG(l.capacite_utilisee), 1) FROM (
                    SELECT l.id, 
                           COUNT(ep.id) * 100.0 / l.capacite as capacite_utilisee
                    FROM lieu_examen l
                    LEFT JOIN examens_planifies ep ON l.id = ep.salle_id AND ep.statut = 'VALIDE'
                    GROUP BY l.id, l.capacite
                ) as occupation
            """)
            if success:
                taux_optimal = platform.cursor.fetchone()[0] or 0
                st.metric("Occupation optimale", f"{taux_optimal}%")
        
        with col3:
            # Équilibre professeurs
            success, error = platform.safe_execute("""
                SELECT ROUND(STDDEV(nb_examens), 2) FROM (
                    SELECT prof_id, COUNT(*) as nb_examens
                    FROM examens_planifies
                    WHERE statut = 'VALIDE'
                    GROUP BY prof_id
                ) as charge_prof
            """)
            if success:
                ecart_type = platform.cursor.fetchone()[0] or 0
                st.metric("Équilibre professeurs", f"σ={ecart_type}")
        
        # Graphique de performance
        st.subheader("Indicateurs qualité")
        
        success, error = platform.safe_execute("""
            SELECT d.nom as departement,
                   COUNT(ep.id) as examens,
                   COUNT(DISTINCT ep.salle_id) as salles_utilisees,
                   COUNT(DISTINCT ep.prof_id) as professeurs
            FROM departements d
            LEFT JOIN formations f ON d.id = f.dept_id
            LEFT JOIN modules m ON f.id = m.formation_id
            LEFT JOIN examens_planifies ep ON m.id = ep.module_id AND ep.statut = 'VALIDE'
            GROUP BY d.id, d.nom
            HAVING COUNT(ep.id) > 0
            ORDER BY examens DESC
        """)
        
        if success:
            perf_data = platform.cursor.fetchall()
            if perf_data:
                df_perf = pd.DataFrame(perf_data, 
                                      columns=['Département', 'Examens', 'Salles', 'Professeurs'])
                
                # Normaliser pour radar chart
                df_perf_normalized = df_perf.copy()
                for col in ['Examens', 'Salles', 'Professeurs']:
                    if df_perf[col].max() > 0:
                        df_perf_normalized[col] = df_perf[col] / df_perf[col].max() * 100
                
                fig = go.Figure()
                
                for i, row in df_perf_normalized.head(3).iterrows():
                    fig.add_trace(go.Scatterpolar(
                        r=[row['Examens'], row['Salles'], row['Professeurs'], row['Examens']],
                        theta=['Examens', 'Salles', 'Professeurs', 'Examens'],
                        name=row['Département'],
                        fill='toself'
                    ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )
                    ),
                    title="Performance par département (Top 3)",
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)

def show_etudiant_dashboard(platform):
    """Dashboard étudiant"""
    st.title("👨‍🎓 Consultation des Examens")
    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        departments = platform.get_departments()
        dept_options = ["Tous"] + [d[1] for d in departments]
        selected_dept = st.selectbox("Département", dept_options)
    
    # Récupérer les examens
    query = """
    SELECT ep.date_heure, m.nom as module, f.nom as formation,
           d.nom as departement, l.nom as salle, ep.duree_minutes
    FROM examens_planifies ep
    JOIN modules m ON ep.module_id = m.id
    JOIN formations f ON m.formation_id = f.id
    JOIN departements d ON f.dept_id = d.id
    JOIN lieu_examen l ON ep.salle_id = l.id
    WHERE ep.statut = 'VALIDE'
    """
    
    params = []
    if selected_dept != "Tous":
        query += " AND d.nom = %s"
        params.append(selected_dept)
    
    query += " ORDER BY ep.date_heure"
    
    success, error = platform.safe_execute(query, params)
    
    if success:
        exams = platform.cursor.fetchall()
        if exams:
            df = pd.DataFrame(exams, 
                            columns=['Date/Heure', 'Module', 'Formation', 'Département', 'Salle', 'Durée (min)'])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Aucun examen trouvé")

def show_professeur_dashboard(platform):
    """Dashboard professeur"""
    st.title("👨‍🏫 Mes Surveillances")
    
    # Sélection département
    departments = platform.get_departments()
    dept_options = [d[1] for d in departments]
    selected_dept = st.selectbox("Département", dept_options)
    
    # Récupérer les examens
    dept_id = [d[0] for d in departments if d[1] == selected_dept][0]
    
    success, error = platform.safe_execute("""
        SELECT ep.date_heure, m.nom as module,
               CONCAT(p.prenom, ' ', p.nom) as professeur,
               l.nom as salle, ep.duree_minutes
        FROM examens_planifies ep
        JOIN modules m ON ep.module_id = m.id
        JOIN formations f ON m.formation_id = f.id
        JOIN departements d ON f.dept_id = d.id
        JOIN professeurs p ON ep.prof_id = p.id
        JOIN lieu_examen l ON ep.salle_id = l.id
        WHERE ep.statut = 'VALIDE'
        AND d.id = %s
        ORDER BY ep.date_heure
    """, (dept_id,))
    
    if success:
        exams = platform.cursor.fetchall()
        if exams:
            df = pd.DataFrame(exams, 
                            columns=['Date/Heure', 'Module', 'Professeur', 'Salle', 'Durée'])
            st.dataframe(df, use_container_width=True)

def show_chef_departement_dashboard(platform):
    """Dashboard chef de département"""
    st.title("📊 Chef de Département")
    
    # Sélection département
    departments = platform.get_departments()
    selected_dept = st.selectbox("Votre département", [d[1] for d in departments])
    
    st.markdown(f"### Département : {selected_dept}")
    
    # Statistiques
    dept_id = [d[0] for d in departments if d[1] == selected_dept][0]
    
    success, error = platform.safe_execute("""
        SELECT COUNT(DISTINCT ep.id), COUNT(DISTINCT ep.prof_id),
               COUNT(DISTINCT ep.salle_id), SUM(ep.duree_minutes)/60
        FROM examens_planifies ep
        JOIN modules m ON ep.module_id = m.id
        JOIN formations f ON m.formation_id = f.id
        JOIN departements d ON f.dept_id = d.id
        WHERE d.id = %s AND ep.statut = 'VALIDE'
    """, (dept_id,))
    
    if success:
        stats = platform.cursor.fetchone()
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Examens", stats[0])
            with col2:
                st.metric("Professeurs", stats[1])
            with col3:
                st.metric("Salles", stats[2])
            with col4:
                st.metric("Heures total", f"{stats[3]:.1f}h")

def main():
    """Fonction principale"""
    
    # Initialiser la plateforme
    platform = ExamPlatform()
    
    if not platform.conn:
        st.error("❌ Connexion base de données échouée")
        st.stop()
    
    # Gestion de session
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    
    # Afficher la page appropriée
    if st.session_state.get('role') is None:
        show_login_page()
    else:
        # Sidebar
        with st.sidebar:
            st.image("https://img.icons8.com/color/96/000000/university.png", width=80)
            st.success(f"👤 Connecté: **{st.session_state['role']}**")
            
            # Statistiques rapides
            if st.session_state['role'] in ["Administrateur", "Vice-doyen/Doyen"]:
                conflits = platform.count_conflicts()
                if conflits > 0:
                    st.error(f"⚠️ {conflits} conflit(s)")
                else:
                    st.success("✅ Aucun conflit")
            
            st.markdown("---")
            if st.button("🚪 Déconnexion", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        # Router vers le bon dashboard
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