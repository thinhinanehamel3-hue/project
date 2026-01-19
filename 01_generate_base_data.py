#!/usr/bin/env python3
"""
Script pour générer les données de base de la plateforme d'examens
Génère: départements, formations, modules, étudiants, professeurs, salles, inscriptions, créneaux
"""

import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta
import time
import sys

# ============================================
# CONFIGURATION
# ============================================

DB_CONFIG = {
    'host': 'localhost',
    'database': 'exam_platform',
    'user': 'postgres',
    'password': 'tinasql',
    'port': '5432'
}

CONFIG = {
    'departements': [
        'Informatique', 'Mathématiques', 'Physique',
        'Chimie', 'Biologie', 'Génie Civil', 'Économie'
    ],
    'nb_etudiants': 13000,
    'nb_professeurs': 100,
    'nb_formations': 200,
    'modules_par_formation': {'min': 6, 'max': 9},
    'nb_salles': 100,
    'promotions': ['2022', '2023', '2024', '2025'],
    'specialites_prof': [
        'Informatique', 'Mathématiques', 'Physique', 'Chimie',
        'Biologie', 'Génie Civil', 'Économie', 'Recherche'
    ],
    'sujets_modules': [
        'Algorithmes et Structures de Données', 'Base de Données', 
        'Réseaux Informatiques', 'Sécurité Informatique', 'IA et Machine Learning',
        'Développement Web', 'Systèmes d\'Exploitation', 'Programmation Orientée Objet',
        'Analyse Mathématique', 'Algèbre Linéaire', 'Statistiques',
        'Probabilités', 'Calcul Différentiel', 'Théorie des Graphes',
        'Mécanique Classique', 'Thermodynamique', 'Électromagnétisme',
        'Physique Quantique', 'Astrophysique', 'Optique',
        'Chimie Organique', 'Chimie Inorganique', 'Biochimie',
        'Chimie Analytique', 'Chimie Physique', 'Chimie des Matériaux',
        'Biologie Moléculaire', 'Génétique', 'Écologie',
        'Biologie Cellulaire', 'Microbiologie', 'Bioinformatique',
        'Mécanique des Structures', 'Matériaux de Construction',
        'Géotechnique', 'Hydraulique', 'Transport', 'Environnement',
        'Microéconomie', 'Macroéconomie', 'Économétrie',
        'Finance', 'Comptabilité', 'Gestion de Projet'
    ]
}

# ============================================
# CLASS PRINCIPALE
# ============================================

class BaseDataGenerator:
    def __init__(self):
        self.fake = Faker('fr_FR')
        random.seed(42)
        Faker.seed(42)
        
        self.conn = None
        self.cursor = None
        
        self.departement_ids = {}
        self.formation_ids = []
        self.module_ids = []
        self.etudiant_ids = []
        self.professeur_ids = []
        self.salle_ids = []
    
    def connect(self):
        """Connexion à la base de données"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Connexion à la base de données établie")
            return True
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False
    
    def disconnect(self):
        """Déconnexion de la base de données"""
        if self.conn:
            self.conn.close()
            print("✅ Connexion fermée")
    
    def check_and_clean(self):
        """Vérifier et nettoyer la base si nécessaire"""
        self.cursor.execute("SELECT COUNT(*) FROM etudiants")
        count = self.cursor.fetchone()[0]
        
        if count > 0:
            confirm = input(f"⚠️  {count} étudiants existent déjà. Voulez-vous tout nettoyer? (o/n): ")
            if confirm.lower() != 'o':
                print("Nettoyage annulé - utilisation des données existantes")
                self.load_existing_ids()
                return False
        
        print("🧹 Nettoyage de la base de données...")
        
        # Désactiver temporairement les triggers
        try:
            self.cursor.execute("ALTER TABLE examens_planifies DISABLE TRIGGER ALL;")
        except:
            pass
        
        tables = [
            'modifications_manuelles',
            'examens_planifies',
            'inscriptions',
            'etudiants',
            'professeurs',
            'modules',
            'formations',
            'lieu_examen',
            'creneaux_horaires',
            'departements'
        ]
        
        for table in tables:
            try:
                self.cursor.execute(f"TRUNCATE TABLE {table} CASCADE;")
                print(f"  - Table {table} nettoyée")
            except Exception as e:
                print(f"  - Note pour {table}: {e}")
        
        # Réactiver les triggers
        try:
            self.cursor.execute("ALTER TABLE examens_planifies ENABLE TRIGGER ALL;")
        except:
            pass
        
        self.conn.commit()
        print("✅ Base de données nettoyée")
        return True
    
    def load_existing_ids(self):
        """Charger les IDs existants"""
        print("\n📥 Chargement des données existantes...")
        
        # Départements
        self.cursor.execute("SELECT id, nom FROM departements")
        for dept_id, nom in self.cursor.fetchall():
            self.departement_ids[nom] = dept_id
        
        # Formations
        self.cursor.execute("SELECT id FROM formations")
        self.formation_ids = [row[0] for row in self.cursor.fetchall()]
        
        # Modules
        self.cursor.execute("SELECT id FROM modules")
        self.module_ids = [row[0] for row in self.cursor.fetchall()]
        
        # Étudiants
        self.cursor.execute("SELECT id FROM etudiants")
        self.etudiant_ids = [row[0] for row in self.cursor.fetchall()]
        
        # Professeurs
        self.cursor.execute("SELECT id FROM professeurs")
        self.professeur_ids = [row[0] for row in self.cursor.fetchall()]
        
        # Salles
        self.cursor.execute("SELECT id FROM lieu_examen")
        self.salle_ids = [row[0] for row in self.cursor.fetchall()]
        
        print(f"✅ Données chargées: {len(self.departement_ids)} départements, "
              f"{len(self.formation_ids)} formations, {len(self.module_ids)} modules, "
              f"{len(self.etudiant_ids)} étudiants, {len(self.professeur_ids)} professeurs, "
              f"{len(self.salle_ids)} salles")
    
    def generate_departements(self):
        """Générer les départements"""
        print("\n🏛️  Génération des départements...")
        
        for nom in CONFIG['departements']:
            self.cursor.execute(
                "INSERT INTO departements (nom) VALUES (%s) RETURNING id",
                (nom,)
            )
            dept_id = self.cursor.fetchone()[0]
            self.departement_ids[nom] = dept_id
            print(f"  - {nom} (ID: {dept_id})")
        
        self.conn.commit()
        print(f"✅ {len(self.departement_ids)} départements créés")
    
    def generate_formations(self):
        """Générer les formations (200 formations)"""
        print("\n📚 Génération des formations...")
        
        types_formation = ['Licence', 'Master', 'Doctorat', 'Ingénierie']
        
        formations_par_dept = CONFIG['nb_formations'] // len(self.departement_ids)
        
        for dept_nom, dept_id in self.departement_ids.items():
            for i in range(formations_par_dept + 1):
                if len(self.formation_ids) >= CONFIG['nb_formations']:
                    break
                    
                type_formation = random.choice(types_formation)
                annee = random.choice(['I', 'II', 'III', 'Spécialisé'])
                
                if dept_nom == 'Informatique':
                    specialite = random.choice(['Informatique', 'IA', 'Cybersécurité', 'Développement', 'Réseaux'])
                elif dept_nom == 'Mathématiques':
                    specialite = random.choice(['Maths Appliquées', 'Statistiques', 'Analyse', 'Algèbre'])
                elif dept_nom == 'Physique':
                    specialite = random.choice(['Physique Quantique', 'Astrophysique', 'Mécanique'])
                elif dept_nom == 'Chimie':
                    specialite = random.choice(['Chimie Organique', 'Biochimie', 'Chimie Analytique'])
                elif dept_nom == 'Biologie':
                    specialite = random.choice(['Biologie Moléculaire', 'Génétique', 'Écologie'])
                elif dept_nom == 'Génie Civil':
                    specialite = random.choice(['Structures', 'Matériaux', 'Environnement'])
                else:
                    specialite = random.choice(['Économie', 'Finance', 'Commerce'])
                
                nom_formation = f"{type_formation} en {specialite} {annee}"
                nb_modules = random.randint(CONFIG['modules_par_formation']['min'], 
                                           CONFIG['modules_par_formation']['max'])
                
                self.cursor.execute(
                    "INSERT INTO formations (nom, dept_id, nb_modules) VALUES (%s, %s, %s) RETURNING id",
                    (nom_formation, dept_id, nb_modules)
                )
                formation_id = self.cursor.fetchone()[0]
                self.formation_ids.append(formation_id)
        
        self.conn.commit()
        print(f"✅ {len(self.formation_ids)} formations créées")
    
    def generate_modules(self):
        """Générer les modules (6-9 par formation)"""
        print("\n📖 Génération des modules...")
        
        modules_count = 0
        batch_size = 100
        batch_values = []
        
        for formation_id in self.formation_ids:
            self.cursor.execute(
                "SELECT nb_modules FROM formations WHERE id = %s",
                (formation_id,)
            )
            nb_modules = self.cursor.fetchone()[0]
            
            for i in range(nb_modules):
                sujet = random.choice(CONFIG['sujets_modules'])
                niveau = random.choice(['Introduction à', 'Avancé', 'Spécialité', 'Projet de', 'Théorie des'])
                nom_module = f"{niveau} {sujet}"
                credits = random.randint(3, 6)
                
                batch_values.append((nom_module, credits, formation_id))
                modules_count += 1
                
                if len(batch_values) >= batch_size:
                    args = ','.join(self.cursor.mogrify("(%s,%s,%s)", row).decode('utf-8') for row in batch_values)
                    self.cursor.execute(f"INSERT INTO modules (nom, credits, formation_id) VALUES {args} RETURNING id")
                    
                    new_ids = [row[0] for row in self.cursor.fetchall()]
                    self.module_ids.extend(new_ids)
                    batch_values = []
                    
                    if len(self.module_ids) % 500 == 0:
                        print(f"  - {len(self.module_ids)} modules créés")
        
        if batch_values:
            args = ','.join(self.cursor.mogrify("(%s,%s,%s)", row).decode('utf-8') for row in batch_values)
            self.cursor.execute(f"INSERT INTO modules (nom, credits, formation_id) VALUES {args} RETURNING id")
            new_ids = [row[0] for row in self.cursor.fetchall()]
            self.module_ids.extend(new_ids)
        
        self.conn.commit()
        print(f"✅ {len(self.module_ids)} modules créés")
    
    def generate_etudiants(self):
        """Générer 13000 étudiants"""
        print(f"\n👨‍🎓 Génération des étudiants ({CONFIG['nb_etudiants']})...")
        
        etudiants_par_formation = CONFIG['nb_etudiants'] // len(self.formation_ids)
        etudiants_restants = CONFIG['nb_etudiants'] % len(self.formation_ids)
        
        etudiants_count = 0
        batch_size = 500
        batch_values = []
        
        for i, formation_id in enumerate(self.formation_ids):
            nb_etudiants = etudiants_par_formation
            if i < etudiants_restants:
                nb_etudiants += 1
            
            for _ in range(nb_etudiants):
                nom = self.fake.last_name()
                prenom = self.fake.first_name()
                promo = random.choice(CONFIG['promotions'])
                
                batch_values.append((nom, prenom, formation_id, promo))
                etudiants_count += 1
                
                if len(batch_values) >= batch_size:
                    args = ','.join(self.cursor.mogrify("(%s,%s,%s,%s)", row).decode('utf-8') for row in batch_values)
                    self.cursor.execute(f"INSERT INTO etudiants (nom, prenom, formation_id, promo) VALUES {args} RETURNING id")
                    
                    new_ids = [row[0] for row in self.cursor.fetchall()]
                    self.etudiant_ids.extend(new_ids)
                    batch_values = []
                    
                    if len(self.etudiant_ids) % 1000 == 0:
                        print(f"  - {len(self.etudiant_ids)} étudiants créés")
        
        if batch_values:
            args = ','.join(self.cursor.mogrify("(%s,%s,%s,%s)", row).decode('utf-8') for row in batch_values)
            self.cursor.execute(f"INSERT INTO etudiants (nom, prenom, formation_id, promo) VALUES {args} RETURNING id")
            new_ids = [row[0] for row in self.cursor.fetchall()]
            self.etudiant_ids.extend(new_ids)
        
        self.conn.commit()
        print(f"✅ {len(self.etudiant_ids)} étudiants créés")
    
    def generate_professeurs(self):
        """Générer 100 professeurs"""
        print(f"\n👨‍🏫 Génération des professeurs ({CONFIG['nb_professeurs']})...")
        
        profs_par_dept = CONFIG['nb_professeurs'] // len(self.departement_ids)
        profs_restants = CONFIG['nb_professeurs'] % len(self.departement_ids)
        
        dept_items = list(self.departement_ids.items())
        
        for i, (dept_nom, dept_id) in enumerate(dept_items):
            nb_profs = profs_par_dept
            if i < profs_restants:
                nb_profs += 1
            
            for _ in range(nb_profs):
                nom = self.fake.last_name()
                prenom = self.fake.first_name()
                specialite = random.choice(CONFIG['specialites_prof'])
                
                self.cursor.execute(
                    "INSERT INTO professeurs (nom, prenom, dept_id, specialite) VALUES (%s, %s, %s, %s) RETURNING id",
                    (nom, prenom, dept_id, specialite)
                )
                prof_id = self.cursor.fetchone()[0]
                self.professeur_ids.append(prof_id)
                
                if len(self.professeur_ids) % 20 == 0:
                    print(f"  - {len(self.professeur_ids)} professeurs créés")
        
        self.conn.commit()
        print(f"✅ {len(self.professeur_ids)} professeurs créés")
    
    def generate_salles(self):
        """Générer 100 salles"""
        print(f"\n🏫 Génération des salles ({CONFIG['nb_salles']})...")
        
        for i in range(CONFIG['nb_salles']):
            if i < 20:
                nom = f"Amphi {i+1:02d}"
                capacite = random.randint(100, 300)
                type_salle = 'AMPHI'
            elif i < 80:
                nom = f"Salle {i-19:02d}"
                capacite = random.randint(15, 20)
                type_salle = 'SALLE'
            else:
                nom = f"Labo {i-79:02d}"
                capacite = random.randint(20, 30)
                type_salle = 'LABO'
            
            batiment = random.choice(['A', 'B', 'C', 'D', 'E'])
            
            self.cursor.execute(
                "INSERT INTO lieu_examen (nom, capacite, type, batiment) VALUES (%s, %s, %s, %s) RETURNING id",
                (nom, capacite, type_salle, batiment)
            )
            salle_id = self.cursor.fetchone()[0]
            self.salle_ids.append(salle_id)
        
        self.conn.commit()
        print(f"✅ {len(self.salle_ids)} salles créées")
    
    def generate_inscriptions(self):
        """Générer les inscriptions (~130000)"""
        print("\n📝 Génération des inscriptions...")
        
        total_inscriptions = 0
        batch_size = 1000
        batch_values = []
        
        for etudiant_id in self.etudiant_ids:
            self.cursor.execute(
                "SELECT formation_id FROM etudiants WHERE id = %s",
                (etudiant_id,)
            )
            formation_id = self.cursor.fetchone()[0]
            
            self.cursor.execute(
                "SELECT id FROM modules WHERE formation_id = %s",
                (formation_id,)
            )
            modules_formation = [row[0] for row in self.cursor.fetchall()]
            
            if not modules_formation:
                continue
            
            nb_inscriptions = max(1, int(len(modules_formation) * 0.8))
            modules_choisis = random.sample(modules_formation, min(nb_inscriptions, len(modules_formation)))
            
            for module_id in modules_choisis:
                if random.random() < 0.3:
                    note = round(random.uniform(8.0, 20.0), 2)
                else:
                    note = None
                
                batch_values.append((etudiant_id, module_id, note))
                total_inscriptions += 1
                
                if len(batch_values) >= batch_size:
                    args = ','.join(self.cursor.mogrify("(%s,%s,%s)", row).decode('utf-8') for row in batch_values)
                    try:
                        self.cursor.execute(f"INSERT INTO inscriptions (etudiant_id, module_id, note) VALUES {args}")
                        self.conn.commit()
                        batch_values = []
                    except Exception as e:
                        print(f"  - Erreur batch: {e}")
                        self.conn.rollback()
                        batch_values = []
            
            if len(self.etudiant_ids) > 100 and etudiant_id % 500 == 0:
                print(f"  - {etudiant_id}/{len(self.etudiant_ids)} étudiants traités ({total_inscriptions} inscriptions)")
        
        if batch_values:
            args = ','.join(self.cursor.mogrify("(%s,%s,%s)", row).decode('utf-8') for row in batch_values)
            self.cursor.execute(f"INSERT INTO inscriptions (etudiant_id, module_id, note) VALUES {args}")
        
        self.conn.commit()
        print(f"✅ {total_inscriptions} inscriptions créées")
    
    def generate_creneaux(self):
        """Générer les créneaux horaires pour 30 jours"""
        print("\n⏰ Génération des créneaux horaires...")
        
        self.cursor.execute("SELECT COUNT(*) FROM creneaux_horaires")
        existing = self.cursor.fetchone()[0]
        
        if existing > 0:
            print(f"  - {existing} créneaux existent déjà")
            return
        
        creneaux_crees = 0
        batch_size = 50
        batch_values = []
        
        for day_offset in range(30):
            date_creneau = datetime.now().date() + timedelta(days=day_offset)
            
            for heure in ['08:30', '10:45']:
                batch_values.append((date_creneau, f"{heure}:00", f"{int(heure[:2]) + 2}:15:00", 'MATIN', True))
                creneaux_crees += 1
            
            for heure in ['14:00', '16:15']:
                batch_values.append((date_creneau, f"{heure}:00", f"{int(heure[:2]) + 2}:15:00", 'APRES_MIDI', True))
                creneaux_crees += 1
            
            if len(batch_values) >= batch_size:
                args = ','.join(self.cursor.mogrify("(%s,%s,%s,%s,%s)", row).decode('utf-8') for row in batch_values)
                self.cursor.execute(f"""
                    INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode, est_disponible) 
                    VALUES {args}
                """)
                self.conn.commit()
                batch_values = []
        
        if batch_values:
            args = ','.join(self.cursor.mogrify("(%s,%s,%s,%s,%s)", row).decode('utf-8') for row in batch_values)
            self.cursor.execute(f"""
                INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode, est_disponible) 
                VALUES {args}
            """)
        
        self.conn.commit()
        print(f"✅ {creneaux_crees} créneaux horaires créés")
    
    def show_statistics(self):
        """Afficher les statistiques"""
        print("\n" + "="*60)
        print("📊 STATISTIQUES DES DONNÉES DE BASE")
        print("="*60)
        
        queries = [
            ("Départements", "SELECT COUNT(*) FROM departements"),
            ("Formations", "SELECT COUNT(*) FROM formations"),
            ("Modules", "SELECT COUNT(*) FROM modules"),
            ("Étudiants", "SELECT COUNT(*) FROM etudiants"),
            ("Professeurs", "SELECT COUNT(*) FROM professeurs"),
            ("Salles", "SELECT COUNT(*) FROM lieu_examen"),
            ("Inscriptions", "SELECT COUNT(*) FROM inscriptions"),
            ("Créneaux horaires", "SELECT COUNT(*) FROM creneaux_horaires"),
        ]
        
        for label, query in queries:
            try:
                self.cursor.execute(query)
                result = self.cursor.fetchone()[0]
                print(f"  {label:25}: {result:,}")
            except Exception as e:
                print(f"  {label:25}: Erreur ({e})")
        
        print("="*60)
    
    def generate_all(self):
        """Génère toutes les données de base"""
        print("\n🚀 Démarrage de la génération des données de base...")
        
        cleaned = self.check_and_clean()
        
        if not cleaned:
            print("\n📊 Utilisation des données existantes")
            self.show_statistics()
            return
        
        print("\n▶️  Génération des données...")
        
        self.generate_departements()
        self.generate_formations()
        self.generate_modules()
        self.generate_etudiants()
        self.generate_professeurs()
        self.generate_salles()
        self.generate_inscriptions()
        self.generate_creneaux()
        
        print("\n✅ Données de base générées avec succès!")
        self.show_statistics()

# ============================================
# EXÉCUTION PRINCIPALE
# ============================================

def main():
    print("🎓 GÉNÉRATEUR DE DONNÉES DE BASE")
    print("="*60)
    print("Génère: départements, formations, modules, étudiants, professeurs, salles, inscriptions")
    print("="*60)
    
    start_time = time.time()
    generator = BaseDataGenerator()
    
    if not generator.connect():
        sys.exit(1)
    
    try:
        generator.generate_all()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n⏱️  TEMPS D'EXÉCUTION: {total_time:.2f} secondes")
        
        if total_time <= 30:
            print("✅ PERFORMANCE EXCELLENTE (< 30s)")
        elif total_time <= 45:
            print("✅ PERFORMANCE BONNE (< 45s)")
        else:
            print(f"⚠️  Temps un peu long ({total_time:.2f}s)")
        
        print("="*60)
        print("✅ GÉNÉRATION TERMINÉE AVEC SUCCÈS!")
        print("\n💡 Conseil: Exécutez maintenant '02_generate_exams.py' pour générer des examens")
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        generator.disconnect()

if __name__ == "__main__":
    main()