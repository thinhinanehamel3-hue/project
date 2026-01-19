-- ============================================
-- FICHIER: 01_schema_base_v2_corrected.sql
-- ============================================

-- 1. Table des départements
CREATE TABLE departements (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) UNIQUE NOT NULL
);

-- 2. Table des formations
CREATE TABLE formations (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    dept_id INTEGER NOT NULL REFERENCES departements(id),
    nb_modules INTEGER CHECK (nb_modules BETWEEN 6 AND 9),
    CONSTRAINT fk_formation_departement FOREIGN KEY (dept_id) 
        REFERENCES departements(id) ON DELETE CASCADE
);

-- 3. Table des modules
CREATE TABLE modules (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    credits INTEGER CHECK (credits > 0),
    formation_id INTEGER NOT NULL REFERENCES formations(id),
    pre_req_id INTEGER REFERENCES modules(id),
    CONSTRAINT fk_module_formation FOREIGN KEY (formation_id) 
        REFERENCES formations(id) ON DELETE CASCADE,
    CONSTRAINT fk_module_prerequis FOREIGN KEY (pre_req_id) 
        REFERENCES modules(id) ON DELETE SET NULL
);

-- 4. Table des étudiants
CREATE TABLE etudiants (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    formation_id INTEGER NOT NULL REFERENCES formations(id),
    promo VARCHAR(10) NOT NULL,
    CONSTRAINT fk_etudiant_formation FOREIGN KEY (formation_id) 
        REFERENCES formations(id) ON DELETE CASCADE
);

-- 5. Table des professeurs
CREATE TABLE professeurs (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    dept_id INTEGER NOT NULL REFERENCES departements(id),
    specialite VARCHAR(100),
    CONSTRAINT fk_professeur_departement FOREIGN KEY (dept_id) 
        REFERENCES departements(id) ON DELETE CASCADE
);

-- 6. Table des lieux d'examen
CREATE TABLE lieu_examen (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    capacite INTEGER NOT NULL CHECK (capacite > 0),
    type VARCHAR(20) CHECK (type IN ('AMPHI', 'SALLE', 'LABO')),
    batiment VARCHAR(50)
);

-- 7. Table des créneaux horaires
CREATE TABLE creneaux_horaires (
    id SERIAL PRIMARY KEY,
    date_creneau DATE NOT NULL,
    heure_debut TIME NOT NULL,
    heure_fin TIME NOT NULL,
    periode VARCHAR(20) CHECK (periode IN ('MATIN', 'APRES_MIDI', 'SOIREE')),
    est_disponible BOOLEAN DEFAULT TRUE,
    UNIQUE (date_creneau, heure_debut)
);

-- 8. Table des inscriptions
CREATE TABLE inscriptions (
    etudiant_id INTEGER NOT NULL REFERENCES etudiants(id),
    module_id INTEGER NOT NULL REFERENCES modules(id),
    note DECIMAL(4,2) CHECK (note >= 0 AND note <= 20),
    PRIMARY KEY (etudiant_id, module_id),
    CONSTRAINT fk_inscription_etudiant FOREIGN KEY (etudiant_id) 
        REFERENCES etudiants(id) ON DELETE CASCADE,
    CONSTRAINT fk_inscription_module FOREIGN KEY (module_id) 
        REFERENCES modules(id) ON DELETE CASCADE
);

-- 9. Table des examens planifiés
CREATE TABLE examens_planifies (
    id SERIAL PRIMARY KEY,
    module_id INTEGER NOT NULL REFERENCES modules(id),
    prof_id INTEGER NOT NULL REFERENCES professeurs(id),
    salle_id INTEGER NOT NULL REFERENCES lieu_examen(id),
    creneau_id INTEGER REFERENCES creneaux_horaires(id),
    date_heure TIMESTAMP NOT NULL,
    duree_minutes INTEGER NOT NULL CHECK (duree_minutes BETWEEN 60 AND 240),
    
    mode_generation VARCHAR(20) DEFAULT 'AUTO' CHECK (mode_generation IN ('AUTO', 'MANUEL')),
    statut VARCHAR(20) DEFAULT 'PROPOSE' CHECK (statut IN ('PROPOSE', 'VALIDE', 'ANNULE', 'MODIFIE')),
    priorite INTEGER DEFAULT 1 CHECK (priorite BETWEEN 1 AND 5),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modifie_par VARCHAR(100),
    
    CONSTRAINT fk_examen_module FOREIGN KEY (module_id) 
        REFERENCES modules(id) ON DELETE CASCADE,
    CONSTRAINT fk_examen_professeur FOREIGN KEY (prof_id) 
        REFERENCES professeurs(id) ON DELETE CASCADE,
    CONSTRAINT fk_examen_salle FOREIGN KEY (salle_id) 
        REFERENCES lieu_examen(id) ON DELETE CASCADE,
    CONSTRAINT fk_examen_creneau FOREIGN KEY (creneau_id) 
        REFERENCES creneaux_horaires(id) ON DELETE SET NULL,
    
    CONSTRAINT chk_mode_creneau CHECK (
        (mode_generation = 'AUTO' AND creneau_id IS NOT NULL) OR
        (mode_generation = 'MANUEL')
    )
);

-- 10. Table des modifications manuelles
CREATE TABLE modifications_manuelles (
    id SERIAL PRIMARY KEY,
    examen_id INTEGER NOT NULL REFERENCES examens_planifies(id),
    
    ancienne_valeur JSONB,
    nouvelle_valeur JSONB,
    
    utilisateur VARCHAR(100) NOT NULL,
    type_modification VARCHAR(50) CHECK (type_modification IN ('CREATION', 'MODIFICATION', 'SUPPRESSION', 'DEPLACEMENT')),
    raison TEXT,
    
    date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Table des paramètres système
CREATE TABLE parametres_systeme (
    id SERIAL PRIMARY KEY,
    cle VARCHAR(50) UNIQUE NOT NULL,
    valeur TEXT,
    description TEXT,
    modifiable BOOLEAN DEFAULT TRUE,
    date_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEXES (CRÉÉS APRÈS LES TABLES)
-- ============================================

-- Index pour modifications_manuelles
CREATE INDEX idx_examen_modifie ON modifications_manuelles(examen_id, date_modification);

-- Index pour examens_planifies
CREATE INDEX idx_examens_date ON examens_planifies(date_heure);
CREATE INDEX idx_examens_mode ON examens_planifies(mode_generation, statut);
CREATE INDEX idx_examens_module_prof ON examens_planifies(module_id, prof_id);
CREATE INDEX idx_examens_salle_date ON examens_planifies(salle_id, date_heure);

-- Index pour creneaux_horaires
CREATE INDEX idx_creneaux_date ON creneaux_horaires(date_creneau, est_disponible);
CREATE INDEX idx_creneaux_periode ON creneaux_horaires(periode, est_disponible);

-- Index pour recherches fréquentes
CREATE INDEX idx_etudiants_formation ON etudiants(formation_id);
CREATE INDEX idx_professeurs_departement ON professeurs(dept_id);
CREATE INDEX idx_modules_formation ON modules(formation_id);

-- ============================================
-- VUES
-- ============================================

-- Vue pour les examens automatiques
CREATE OR REPLACE VIEW v_examens_auto AS
SELECT e.*, m.nom as module_nom, p.nom as prof_nom, p.prenom as prof_prenom,
       l.nom as salle_nom, l.type as salle_type, l.capacite
FROM examens_planifies e
JOIN modules m ON e.module_id = m.id
JOIN professeurs p ON e.prof_id = p.id
JOIN lieu_examen l ON e.salle_id = l.id
WHERE e.mode_generation = 'AUTO';

-- Vue pour les examens manuels
CREATE OR REPLACE VIEW v_examens_manuel AS
SELECT e.*, m.nom as module_nom, p.nom as prof_nom, p.prenom as prof_prenom,
       l.nom as salle_nom, l.type as salle_type, l.capacite,
       mm.utilisateur as derniere_modification_par,
       mm.date_modification as derniere_modification_le
FROM examens_planifies e
JOIN modules m ON e.module_id = m.id
JOIN professeurs p ON e.prof_id = p.id
JOIN lieu_examen l ON e.salle_id = l.id
LEFT JOIN modifications_manuelles mm ON e.id = mm.examen_id
WHERE e.mode_generation = 'MANUEL';

-- Vue pour les conflits
CREATE OR REPLACE VIEW v_conflits AS
SELECT 
    e1.id as examen1_id,
    e2.id as examen2_id,
    e1.salle_id,
    e1.date_heure as debut1,
    e1.date_heure + (e1.duree_minutes || ' minutes')::INTERVAL as fin1,
    e2.date_heure as debut2,
    e2.date_heure + (e2.duree_minutes || ' minutes')::INTERVAL as fin2,
    CASE 
        WHEN e1.salle_id = e2.salle_id AND 
             (e1.date_heure, e1.date_heure + (e1.duree_minutes || ' minutes')::INTERVAL) 
             OVERLAPS 
             (e2.date_heure, e2.date_heure + (e2.duree_minutes || ' minutes')::INTERVAL)
        THEN 'CONFLIT_SALLE'
        WHEN e1.prof_id = e2.prof_id AND 
             DATE(e1.date_heure) = DATE(e2.date_heure) AND
             (SELECT COUNT(*) FROM examens_planifies 
              WHERE prof_id = e1.prof_id 
              AND DATE(date_heure) = DATE(e1.date_heure)) > 3
        THEN 'CONFLIT_PROFESSEUR'
        ELSE 'PAS_DE_CONFLIT'
    END as type_conflit
FROM examens_planifies e1
JOIN examens_planifies e2 ON e1.id < e2.id
WHERE e1.statut = 'VALIDE' AND e2.statut = 'VALIDE';

-- ============================================
-- FONCTIONS ET TRIGGERS
-- ============================================

-- Fonction pour mettre à jour modified_at
CREATE OR REPLACE FUNCTION update_modified_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modified_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour examens_planifies
CREATE TRIGGER trg_update_modified_at
BEFORE UPDATE ON examens_planifies
FOR EACH ROW EXECUTE FUNCTION update_modified_at();

-- Fonction pour enregistrer les modifications
CREATE OR REPLACE FUNCTION enregistrer_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO modifications_manuelles 
        (examen_id, ancienne_valeur, nouvelle_valeur, utilisateur, type_modification)
        VALUES (
            OLD.id,
            jsonb_build_object(
                'prof_id', OLD.prof_id,
                'salle_id', OLD.salle_id,
                'date_heure', OLD.date_heure,
                'duree_minutes', OLD.duree_minutes,
                'statut', OLD.statut,
                'mode_generation', OLD.mode_generation
            ),
            jsonb_build_object(
                'prof_id', NEW.prof_id,
                'salle_id', NEW.salle_id,
                'date_heure', NEW.date_heure,
                'duree_minutes', NEW.duree_minutes,
                'statut', NEW.statut,
                'mode_generation', NEW.mode_generation
            ),
            COALESCE(NEW.modifie_par, 'system'),
            'MODIFICATION'
        );
    ELSIF (TG_OP = 'INSERT' AND NEW.mode_generation = 'MANUEL') THEN
        INSERT INTO modifications_manuelles 
        (examen_id, ancienne_valeur, nouvelle_valeur, utilisateur, type_modification)
        VALUES (
            NEW.id,
            NULL,
            jsonb_build_object(
                'prof_id', NEW.prof_id,
                'salle_id', NEW.salle_id,
                'date_heure', NEW.date_heure,
                'duree_minutes', NEW.duree_minutes,
                'statut', NEW.statut,
                'mode_generation', NEW.mode_generation
            ),
            COALESCE(NEW.modifie_par, 'system'),
            'CREATION'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour enregistrer les modifications manuelles
CREATE TRIGGER trg_enregistrer_modification
AFTER INSERT OR UPDATE ON examens_planifies
FOR EACH ROW EXECUTE FUNCTION enregistrer_modification();

-- ============================================
-- DONNÉES DE BASE (PARAMÈTRES SYSTÈME)
-- ============================================

INSERT INTO parametres_systeme (cle, valeur, description, modifiable) VALUES
('MAX_EXAMENS_PAR_JOUR_PROF', '3', 'Nombre maximum d''examens qu''un professeur peut avoir par jour', true),
('MAX_EXAMENS_PAR_JOUR_ETUDIANT', '1', 'Nombre maximum d''examens qu''un étudiant peut avoir par jour', true),
('CAPACITE_MAX_SALLE_NORMALE', '20', 'Capacité maximale pour les salles normales (non-amphi)', true),
('DUREE_MIN_EXAMEN', '60', 'Durée minimale d''un examen (minutes)', true),
('DUREE_MAX_EXAMEN', '240', 'Durée maximale d''un examen (minutes)', true),
('PERIODE_EXAMENS_DEBUT', CURRENT_DATE + INTERVAL '7 days', 'Date de début de la période d''examens', true),
('PERIODE_EXAMENS_FIN', CURRENT_DATE + INTERVAL '21 days', 'Date de fin de la période d''examens', true),
('HEURE_DEBUT_MATIN', '08:30', 'Heure de début des créneaux du matin', true),
('HEURE_FIN_MATIN', '12:30', 'Heure de fin des créneaux du matin', true),
('HEURE_DEBUT_APRES_MIDI', '14:00', 'Heure de début des créneaux d''après-midi', true),
('HEURE_FIN_APRES_MIDI', '18:00', 'Heure de fin des créneaux d''après-midi', true);

-- ============================================
-- CRÉATION DES CRÉNEAUX HORAIRES (POUR LES 14 PROCHAINS JOURS)
-- ============================================

DO $$
DECLARE
    date_courante DATE;
    i INTEGER;
BEGIN
    FOR i IN 0..13 LOOP
        date_courante := CURRENT_DATE + i;
        
        -- Créneaux du matin (8:30 - 12:30)
        INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
        VALUES (date_courante, '08:30', '10:30', 'MATIN');
        
        INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
        VALUES (date_courante, '10:45', '12:45', 'MATIN');
        
        -- Créneaux d'après-midi (14:00 - 18:00)
        INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
        VALUES (date_courante, '14:00', '16:00', 'APRES_MIDI');
        
        INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
        VALUES (date_courante, '16:15', '18:15', 'APRES_MIDI');
    END LOOP;
END $$;

-- ============================================
-- MESSAGE DE CONFIRMATION
-- ============================================

DO $$
DECLARE
    nb_tables INTEGER;
    nb_vues INTEGER;
    nb_index INTEGER;
BEGIN
    -- Compter les tables
    SELECT COUNT(*) INTO nb_tables
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    
    -- Compter les vues
    SELECT COUNT(*) INTO nb_vues
    FROM information_schema.views 
    WHERE table_schema = 'public';
    
    -- Compter les indexes
    SELECT COUNT(*) INTO nb_index
    FROM pg_indexes 
    WHERE schemaname = 'public';
    
    RAISE NOTICE '✅ SCHÉMA DE BASE CRÉÉ AVEC SUCCÈS!';
    RAISE NOTICE '   - Tables créées: %', nb_tables;
    RAISE NOTICE '   - Vues créées: %', nb_vues;
    RAISE NOTICE '   - Indexes créés: %', nb_index;
    RAISE NOTICE '   - Données de base insérées';
    RAISE NOTICE '   - Support manuel/automatique activé';
END $$;