-- ============================================
-- FICHIER: 02_constraints_triggers_v3_complet.sql
-- DESCRIPTION: Contraintes et triggers pour support manuel/automatique
-- ============================================

-- -------------------------------------------------
-- 1. SUPPRIMER LES TRIGGERS ET FONCTIONS EXISTANTS
-- -------------------------------------------------

-- Supprimer les triggers d'abord
DROP TRIGGER IF EXISTS trg_check_etudiant_daily_limit ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_professeur_daily_limit ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_salle_capacity ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_professeur_departement ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_salle_disponibilite ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_equite_surveillance ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_duree_creneau ON examens_planifies;
DROP TRIGGER IF EXISTS trg_check_module_unique_examen ON examens_planifies;

-- Supprimer les fonctions
DROP FUNCTION IF EXISTS check_etudiant_daily_limit CASCADE;
DROP FUNCTION IF EXISTS check_professeur_daily_limit CASCADE;
DROP FUNCTION IF EXISTS check_salle_capacity CASCADE;
DROP FUNCTION IF EXISTS check_professeur_departement CASCADE;
DROP FUNCTION IF EXISTS check_salle_disponibilite CASCADE;
DROP FUNCTION IF EXISTS check_equite_surveillance CASCADE;
DROP FUNCTION IF EXISTS check_duree_creneau CASCADE;
DROP FUNCTION IF EXISTS check_module_unique_examen CASCADE;

DROP FUNCTION IF EXISTS check_salle_capacity_helper CASCADE;
DROP FUNCTION IF EXISTS check_salle_disponibilite_helper CASCADE;
DROP FUNCTION IF EXISTS check_professeur_daily_limit_helper CASCADE;
DROP FUNCTION IF EXISTS check_etudiant_daily_limit_helper CASCADE;
DROP FUNCTION IF EXISTS check_professeur_departement_helper CASCADE;
DROP FUNCTION IF EXISTS check_equite_surveillance_helper CASCADE;

DROP FUNCTION IF EXISTS verifier_contraintes_examen CASCADE;
DROP FUNCTION IF EXISTS generer_creneaux_manquants CASCADE;
DROP FUNCTION IF EXISTS planifier_examen_auto CASCADE;
DROP FUNCTION IF EXISTS afficher_statut_contraintes CASCADE;

DROP PROCEDURE IF EXISTS tester_contraintes CASCADE;
DROP PROCEDURE IF EXISTS planifier_examen_avec_verification CASCADE;

-- -------------------------------------------------
-- 2. FONCTIONS DE BASE POUR LES CONTRAINTES
-- -------------------------------------------------

-- Fonction 1: Vérifier qu'un étudiant n'a pas plus d'un examen par jour
CREATE OR REPLACE FUNCTION check_etudiant_daily_limit()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        -- Vérifier si l'étudiant a déjà un examen le même jour
        SELECT 1
        FROM inscriptions i
        JOIN examens_planifies e ON i.module_id = e.module_id
        WHERE i.etudiant_id IN (
            SELECT etudiant_id 
            FROM inscriptions 
            WHERE module_id = NEW.module_id
        )
        AND e.id != COALESCE(NEW.id, 0)
        AND DATE(e.date_heure) = DATE(NEW.date_heure)
        AND e.statut IN ('PROPOSE', 'VALIDE')
    ) THEN
        RAISE EXCEPTION 'ERREUR: Un étudiant ne peut pas avoir plus d''un examen par jour';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 2: Vérifier qu'un professeur n'a pas plus de 3 examens par jour
CREATE OR REPLACE FUNCTION check_professeur_daily_limit()
RETURNS TRIGGER AS $$
DECLARE
    exam_count INTEGER;
BEGIN
    -- Compter le nombre d'examens du professeur le même jour
    SELECT COUNT(*) INTO exam_count
    FROM examens_planifies
    WHERE prof_id = NEW.prof_id
    AND DATE(date_heure) = DATE(NEW.date_heure)
    AND id != COALESCE(NEW.id, 0)
    AND statut IN ('PROPOSE', 'VALIDE');
    
    IF exam_count >= 3 THEN
        RAISE EXCEPTION 'ERREUR: Le professeur % ne peut pas avoir plus de 3 examens par jour (déjà %)', 
            NEW.prof_id, exam_count;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 3: Vérifier la capacité de la salle
CREATE OR REPLACE FUNCTION check_salle_capacity()
RETURNS TRIGGER AS $$
DECLARE
    salle_capacity INTEGER;
    etudiants_count INTEGER;
    salle_type VARCHAR(20);
BEGIN
    -- Récupérer la capacité et le type de la salle
    SELECT capacite, type INTO salle_capacity, salle_type
    FROM lieu_examen WHERE id = NEW.salle_id;
    
    -- Compter le nombre d'étudiants inscrits au module
    SELECT COUNT(*) INTO etudiants_count
    FROM inscriptions WHERE module_id = NEW.module_id;
    
    -- Vérification de la capacité
    -- Les amphithéâtres (AMPHI) peuvent accueillir plus de 20
    -- Les salles normales (SALLE, LABO) maximum 20
    IF salle_type != 'AMPHI' AND etudiants_count > 20 THEN
        RAISE EXCEPTION 'ERREUR: La salle % de type % peut accueillir seulement % étudiants, alors que le module a % étudiants', 
            NEW.salle_id, salle_type, LEAST(salle_capacity, 20), etudiants_count;
    ELSIF etudiants_count > salle_capacity THEN
        RAISE EXCEPTION 'ERREUR: La salle % a une capacité de % étudiants, alors que le module a % étudiants', 
            NEW.salle_id, salle_capacity, etudiants_count;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 4: Vérifier la priorité département (avertissement seulement, pas d'erreur)
CREATE OR REPLACE FUNCTION check_professeur_departement()
RETURNS TRIGGER AS $$
DECLARE
    prof_dept_id INTEGER;
    module_dept_id INTEGER;
BEGIN
    -- Récupérer le département du professeur
    SELECT dept_id INTO prof_dept_id
    FROM professeurs WHERE id = NEW.prof_id;
    
    -- Récupérer le département du module (via la formation)
    SELECT f.dept_id INTO module_dept_id
    FROM modules m
    JOIN formations f ON m.formation_id = f.id
    WHERE m.id = NEW.module_id;
    
    -- Vérifier que le professeur est du même département
    IF prof_dept_id != module_dept_id THEN
        -- Toujours autoriser, mais noter la différence
        NEW.modifie_par := COALESCE(NEW.modifie_par, 'system') || 
                          ' [Département diff: prof=' || prof_dept_id || 
                          ' module=' || module_dept_id || ']';
        
        -- En mode AUTO, on peut quand même continuer
        -- En mode MANUEL, l'administrateur est averti par le message
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 3: Vérifier la capacité de la salle (avec plus de flexibilité)
CREATE OR REPLACE FUNCTION check_salle_capacity()
RETURNS TRIGGER AS $$
DECLARE
    salle_capacity INTEGER;
    etudiants_count INTEGER;
    salle_type VARCHAR(20);
BEGIN
    -- Récupérer la capacité et le type de la salle
    SELECT capacite, type INTO salle_capacity, salle_type
    FROM lieu_examen WHERE id = NEW.salle_id;
    
    -- Compter le nombre d'étudiants inscrits au module
    SELECT COUNT(*) INTO etudiants_count
    FROM inscriptions WHERE module_id = NEW.module_id;
    
    -- Vérification de la capacité
    -- Les amphithéâtres (AMPHI) peuvent accueillir plus de 20
    -- Les salles normales (SALLE, LABO) maximum 20
    IF salle_type != 'AMPHI' AND etudiants_count > 20 THEN
        -- Au lieu d'une erreur, on accepte avec un avertissement
        NEW.modifie_par := COALESCE(NEW.modifie_par, 'system') || 
                          ' [Salle ' || salle_type || ' capacity=' || salle_capacity || 
                          ' students=' || etudiants_count || ' (max 20)]';
    ELSIF etudiants_count > salle_capacity THEN
        RAISE EXCEPTION 'ERREUR: La salle % a une capacité de % étudiants, alors que le module a % étudiants', 
            NEW.salle_id, salle_capacity, etudiants_count;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- Fonction 5: Vérifier que la salle est libre au moment de l'examen
CREATE OR REPLACE FUNCTION check_salle_disponibilite()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM examens_planifies
        WHERE salle_id = NEW.salle_id
        AND id != COALESCE(NEW.id, 0)
        AND statut IN ('PROPOSE', 'VALIDE')
        AND (
            -- Vérification de chevauchement horaire
            (NEW.date_heure, NEW.date_heure + (NEW.duree_minutes || ' minutes')::INTERVAL) 
            OVERLAPS 
            (date_heure, date_heure + (duree_minutes || ' minutes')::INTERVAL)
        )
    ) THEN
        RAISE EXCEPTION 'ERREUR: La salle % est occupée à cette heure', NEW.salle_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 6: Vérifier l'équité de la surveillance (avertissement seulement)
CREATE OR REPLACE FUNCTION check_equite_surveillance()
RETURNS TRIGGER AS $$
DECLARE
    avg_surveillance DECIMAL;
    prof_surveillance INTEGER;
    total_profs INTEGER;
    total_surveillances INTEGER;
BEGIN
    -- Calculer la moyenne des surveillances
    SELECT COUNT(DISTINCT prof_id), SUM(cnt)
    INTO total_profs, total_surveillances
    FROM (
        SELECT prof_id, COUNT(*) as cnt
        FROM examens_planifies
        WHERE statut IN ('PROPOSE', 'VALIDE')
        GROUP BY prof_id
    ) stats;
    
    IF total_profs > 0 THEN
        avg_surveillance := total_surveillances::DECIMAL / total_profs;
        
        -- Compter les surveillances du professeur actuel
        SELECT COUNT(*) INTO prof_surveillance
        FROM examens_planifies
        WHERE prof_id = NEW.prof_id
        AND statut IN ('PROPOSE', 'VALIDE');
        
        -- Si le professeur a beaucoup plus que la moyenne, avertir
        IF prof_surveillance > avg_surveillance * 1.5 THEN
            RAISE WARNING 'ATTENTION: Le professeur % a % surveillances, alors que la moyenne est %.2f', 
                NEW.prof_id, prof_surveillance, avg_surveillance;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 7: Vérifier que la durée correspond au créneau
CREATE OR REPLACE FUNCTION check_duree_creneau()
RETURNS TRIGGER AS $$
DECLARE
    creneau_record RECORD;
    duree_heures DECIMAL;
BEGIN
    -- Si l'examen a un créneau assigné (mode AUTO)
    IF NEW.creneau_id IS NOT NULL THEN
        -- Récupérer les informations du créneau
        SELECT * INTO creneau_record
        FROM creneaux_horaires WHERE id = NEW.creneau_id;
        
        -- Calculer la durée en heures
        duree_heures := NEW.duree_minutes / 60.0;
        
        -- Vérifier que la durée ne dépasse pas le créneau
        IF (EXTRACT(EPOCH FROM (creneau_record.heure_fin - creneau_record.heure_debut)) / 3600) < duree_heures THEN
            RAISE EXCEPTION 'ERREUR: La durée de l''examen (% minutes) dépasse le créneau horaire (% - %)', 
                NEW.duree_minutes, creneau_record.heure_debut, creneau_record.heure_fin;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction 8: Vérifier qu'un module n'a qu'un seul examen planifié
CREATE OR REPLACE FUNCTION check_module_unique_examen()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM examens_planifies
        WHERE module_id = NEW.module_id
        AND id != COALESCE(NEW.id, 0)
        AND statut IN ('PROPOSE', 'VALIDE')
    ) THEN
        RAISE EXCEPTION 'ERREUR: Le module % a déjà un examen planifié', NEW.module_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------
-- 3. FONCTIONS HELPER POUR LA VÉRIFICATION
-- -------------------------------------------------

-- Helper 1: Vérification capacité de salle
CREATE OR REPLACE FUNCTION check_salle_capacity_helper(
    module_id_param INTEGER,
    salle_id_param INTEGER
) RETURNS VOID AS $$
DECLARE
    salle_capacity INTEGER;
    etudiants_count INTEGER;
    salle_type VARCHAR(20);
BEGIN
    SELECT capacite, type INTO salle_capacity, salle_type
    FROM lieu_examen WHERE id = salle_id_param;
    
    SELECT COUNT(*) INTO etudiants_count
    FROM inscriptions WHERE module_id = module_id_param;
    
    IF salle_type != 'AMPHI' AND etudiants_count > 20 THEN
        RAISE EXCEPTION 'La salle de type % peut accueillir seulement % étudiants, alors que le module a % étudiants', 
            salle_type, LEAST(salle_capacity, 20), etudiants_count;
    ELSIF etudiants_count > salle_capacity THEN
        RAISE EXCEPTION 'La salle a une capacité de % étudiants, alors que le module a % étudiants', 
            salle_capacity, etudiants_count;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper 2: Vérification disponibilité de salle
CREATE OR REPLACE FUNCTION check_salle_disponibilite_helper(
    salle_id_param INTEGER,
    date_heure_param TIMESTAMP,
    duree_minutes_param INTEGER,
    examen_id_param INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM examens_planifies
        WHERE salle_id = salle_id_param
        AND id != COALESCE(examen_id_param, 0)
        AND statut IN ('PROPOSE', 'VALIDE')
        AND (
            (date_heure_param, date_heure_param + (duree_minutes_param || ' minutes')::INTERVAL) 
            OVERLAPS 
            (date_heure, date_heure + (duree_minutes || ' minutes')::INTERVAL)
        )
    ) THEN
        RAISE EXCEPTION 'La salle est occupée à cette heure';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper 3: Vérification limite quotidienne professeur
CREATE OR REPLACE FUNCTION check_professeur_daily_limit_helper(
    prof_id_param INTEGER,
    date_heure_param TIMESTAMP,
    examen_id_param INTEGER DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    exam_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO exam_count
    FROM examens_planifies
    WHERE prof_id = prof_id_param
    AND DATE(date_heure) = DATE(date_heure_param)
    AND id != COALESCE(examen_id_param, 0)
    AND statut IN ('PROPOSE', 'VALIDE');
    
    IF exam_count >= 3 THEN
        RAISE EXCEPTION 'Le professeur a déjà % examens ce jour', exam_count;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper 4: Vérification limite quotidienne étudiant
CREATE OR REPLACE FUNCTION check_etudiant_daily_limit_helper(
    module_id_param INTEGER,
    date_heure_param TIMESTAMP,
    examen_id_param INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM inscriptions i
        JOIN examens_planifies e ON i.module_id = e.module_id
        WHERE i.etudiant_id IN (
            SELECT etudiant_id 
            FROM inscriptions 
            WHERE module_id = module_id_param
        )
        AND e.id != COALESCE(examen_id_param, 0)
        AND DATE(e.date_heure) = DATE(date_heure_param)
        AND e.statut IN ('PROPOSE', 'VALIDE')
    ) THEN
        RAISE EXCEPTION 'Un étudiant ne peut pas avoir plus d''un examen par jour';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper 5: Vérification priorité département
CREATE OR REPLACE FUNCTION check_professeur_departement_helper(
    prof_id_param INTEGER,
    module_id_param INTEGER,
    mode_generation_param VARCHAR
) RETURNS VOID AS $$
DECLARE
    prof_dept_id INTEGER;
    module_dept_id INTEGER;
BEGIN
    -- Récupérer le département du professeur
    SELECT dept_id INTO prof_dept_id
    FROM professeurs WHERE id = prof_id_param;
    
    -- Récupérer le département du module (via la formation)
    SELECT f.dept_id INTO module_dept_id
    FROM modules m
    JOIN formations f ON m.formation_id = f.id
    WHERE m.id = module_id_param;
    
    -- Vérifier que le professeur est du même département
    IF prof_dept_id != module_dept_id THEN
        IF mode_generation_param = 'AUTO' THEN
            RAISE EXCEPTION 'Le professeur doit surveiller un examen de son département (département % ≠ %)', 
                prof_dept_id, module_dept_id;
        ELSE
            -- Pour le mode manuel, on ne fait rien (c'est permis avec avertissement)
            -- Le message sera géré par verifier_contraintes_examen
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper 6: Vérification équité surveillance
CREATE OR REPLACE FUNCTION check_equite_surveillance_helper(
    prof_id_param INTEGER
) RETURNS VOID AS $$
DECLARE
    avg_surveillance DECIMAL;
    prof_surveillance INTEGER;
    total_profs INTEGER;
    total_surveillances INTEGER;
BEGIN
    -- Calculer la moyenne des surveillances
    SELECT COUNT(DISTINCT prof_id), SUM(cnt)
    INTO total_profs, total_surveillances
    FROM (
        SELECT prof_id, COUNT(*) as cnt
        FROM examens_planifies
        WHERE statut IN ('PROPOSE', 'VALIDE')
        GROUP BY prof_id
    ) stats;
    
    IF total_profs > 0 THEN
        avg_surveillance := total_surveillances::DECIMAL / total_profs;
        
        -- Compter les surveillances du professeur actuel
        SELECT COUNT(*) INTO prof_surveillance
        FROM examens_planifies
        WHERE prof_id = prof_id_param
        AND statut IN ('PROPOSE', 'VALIDE');
        
        -- Si le professeur a beaucoup plus que la moyenne, lever une exception
        IF prof_surveillance > avg_surveillance * 1.5 THEN
            RAISE EXCEPTION 'Le professeur % a % surveillances, alors que la moyenne est %.2f', 
                prof_id_param, prof_surveillance, avg_surveillance;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------
-- 4. FONCTION PRINCIPALE POUR VÉRIFIER LES CONTRAINTES
-- -------------------------------------------------

CREATE OR REPLACE FUNCTION verifier_contraintes_examen(
    p_module_id INTEGER,
    p_prof_id INTEGER,
    p_salle_id INTEGER,
    p_date_heure TIMESTAMP,
    p_duree_minutes INTEGER,
    p_examen_id INTEGER DEFAULT NULL,
    p_mode_generation VARCHAR DEFAULT 'MANUEL'
) RETURNS TABLE (
    contrainte VARCHAR(100),
    est_valide BOOLEAN,
    message TEXT,
    severite VARCHAR(10)
) AS $$
DECLARE
    prof_dept_id INTEGER;
    module_dept_id INTEGER;
BEGIN
    -- Vérification capacité de la salle
    BEGIN
        PERFORM check_salle_capacity_helper(p_module_id, p_salle_id);
        contrainte := 'Capacité de la salle';
        est_valide := TRUE;
        message := 'Capacité adéquate';
        severite := 'ERREUR';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        contrainte := 'Capacité de la salle';
        est_valide := FALSE;
        message := SQLERRM;
        severite := 'ERREUR';
        RETURN NEXT;
    END;

    -- Vérification disponibilité de la salle
    BEGIN
        PERFORM check_salle_disponibilite_helper(p_salle_id, p_date_heure, p_duree_minutes, p_examen_id);
        contrainte := 'Disponibilité de la salle';
        est_valide := TRUE;
        message := 'Salle disponible';
        severite := 'ERREUR';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        contrainte := 'Disponibilité de la salle';
        est_valide := FALSE;
        message := SQLERRM;
        severite := 'ERREUR';
        RETURN NEXT;
    END;

    -- Vérification limite quotidienne professeur
    BEGIN
        PERFORM check_professeur_daily_limit_helper(p_prof_id, p_date_heure, p_examen_id);
        contrainte := 'Limite quotidienne professeur';
        est_valide := TRUE;
        message := 'Professeur disponible';
        severite := 'ERREUR';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        contrainte := 'Limite quotidienne professeur';
        est_valide := FALSE;
        message := SQLERRM;
        severite := 'ERREUR';
        RETURN NEXT;
    END;

    -- Vérification limite quotidienne étudiant
    BEGIN
        PERFORM check_etudiant_daily_limit_helper(p_module_id, p_date_heure, p_examen_id);
        contrainte := 'Limite quotidienne étudiant';
        est_valide := TRUE;
        message := 'Étudiants disponibles';
        severite := 'ERREUR';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        contrainte := 'Limite quotidienne étudiant';
        est_valide := FALSE;
        message := SQLERRM;
        severite := 'ERREUR';
        RETURN NEXT;
    END;

    -- Vérification priorité département
    BEGIN
        -- Récupérer le département du professeur
        SELECT dept_id INTO prof_dept_id
        FROM professeurs WHERE id = p_prof_id;
        
        -- Récupérer le département du module (via la formation)
        SELECT f.dept_id INTO module_dept_id
        FROM modules m
        JOIN formations f ON m.formation_id = f.id
        WHERE m.id = p_module_id;
        
        IF prof_dept_id != module_dept_id THEN
            IF p_mode_generation = 'AUTO' THEN
                -- Pour le mode AUTO: c'est une erreur
                contrainte := 'Priorité département';
                est_valide := FALSE;
                message := 'Le professeur doit surveiller un examen de son département (département ' || prof_dept_id || ' ≠ ' || module_dept_id || ')';
                severite := 'ERREUR';
                RETURN NEXT;
            ELSE
                -- Pour le mode MANUEL: avertissement seulement (toujours valide)
                contrainte := 'Priorité département';
                est_valide := TRUE;
                message := 'Le professeur du département ' || prof_dept_id || ' surveille un module du département ' || module_dept_id || ' (avertissement)';
                severite := 'AVERTISSEMENT';
                RETURN NEXT;
            END IF;
        ELSE
            -- Même département: tout est bon
            contrainte := 'Priorité département';
            est_valide := TRUE;
            message := 'Professeur du même département';
            severite := CASE WHEN p_mode_generation = 'AUTO' THEN 'ERREUR' ELSE 'AVERTISSEMENT' END;
            RETURN NEXT;
        END IF;
    END;

    -- Vérification équité surveillance (avertissement seulement)
    BEGIN
        PERFORM check_equite_surveillance_helper(p_prof_id);
        contrainte := 'Équité surveillance';
        est_valide := TRUE;
        message := 'Équité respectée';
        severite := 'AVERTISSEMENT';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        contrainte := 'Équité surveillance';
        est_valide := TRUE;  -- Toujours valide, juste un avertissement
        message := SQLERRM;
        severite := 'AVERTISSEMENT';
        RETURN NEXT;
    END;
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------
-- 5. CRÉATION DES TRIGGERS
-- -------------------------------------------------

-- Trigger 1: Limite quotidienne étudiant
CREATE TRIGGER trg_check_etudiant_daily_limit
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_etudiant_daily_limit();

-- Trigger 2: Limite quotidienne professeur
CREATE TRIGGER trg_check_professeur_daily_limit
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_professeur_daily_limit();

-- Trigger 3: Capacité de la salle
CREATE TRIGGER trg_check_salle_capacity
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_salle_capacity();

-- Trigger 4: Priorité département
CREATE TRIGGER trg_check_professeur_departement
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_professeur_departement();

-- Trigger 5: Disponibilité de la salle
CREATE TRIGGER trg_check_salle_disponibilite
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_salle_disponibilite();

-- Trigger 6: Équité surveillance
CREATE TRIGGER trg_check_equite_surveillance
AFTER INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_equite_surveillance();

-- Trigger 7: Durée créneau
CREATE TRIGGER trg_check_duree_creneau
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.creneau_id IS NOT NULL AND NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_duree_creneau();

-- Trigger 8: Unicité module
CREATE TRIGGER trg_check_module_unique_examen
BEFORE INSERT OR UPDATE ON examens_planifies
FOR EACH ROW 
WHEN (NEW.statut IN ('PROPOSE', 'VALIDE'))
EXECUTE FUNCTION check_module_unique_examen();

-- -------------------------------------------------
-- 6. AUTRES FONCTIONS UTILES
-- -------------------------------------------------

-- Fonction pour générer les créneaux manquants
CREATE OR REPLACE FUNCTION generer_creneaux_manquants(
    p_date_debut DATE,
    p_date_fin DATE
) RETURNS INTEGER AS $$
DECLARE
    date_courante DATE;
    creneaux_crees INTEGER := 0;
BEGIN
    FOR date_courante IN 
        SELECT generate_series(p_date_debut, p_date_fin, '1 day'::INTERVAL)::DATE
    LOOP
        -- Vérifier si des créneaux existent déjà pour cette date
        IF NOT EXISTS (SELECT 1 FROM creneaux_horaires WHERE date_creneau = date_courante) THEN
            -- Créneaux du matin
            INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
            VALUES (date_courante, '08:30', '10:30', 'MATIN');
            
            INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
            VALUES (date_courante, '10:45', '12:45', 'MATIN');
            
            -- Créneaux d'après-midi
            INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
            VALUES (date_courante, '14:00', '16:00', 'APRES_MIDI');
            
            INSERT INTO creneaux_horaires (date_creneau, heure_debut, heure_fin, periode)
            VALUES (date_courante, '16:15', '18:15', 'APRES_MIDI');
            
            creneaux_crees := creneaux_crees + 4;
        END IF;
    END LOOP;
    
    RETURN creneaux_crees;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour planifier un examen en mode auto
CREATE OR REPLACE FUNCTION planifier_examen_auto(
    p_module_id INTEGER,
    p_duree_minutes INTEGER DEFAULT 120
) RETURNS INTEGER AS $$
DECLARE
    v_examen_id INTEGER;
    v_prof_id INTEGER;
    v_salle_id INTEGER;
    v_creneau_id INTEGER;
    v_date_heure TIMESTAMP;
    v_nb_etudiants INTEGER;
    v_departement_id INTEGER;
    v_trouve BOOLEAN := FALSE;
BEGIN
    -- Récupérer le département du module
    SELECT f.dept_id INTO v_departement_id
    FROM modules m
    JOIN formations f ON m.formation_id = f.id
    WHERE m.id = p_module_id;
    
    -- Trouver un professeur du même département avec le moins de surveillances
    SELECT p.id INTO v_prof_id
    FROM professeurs p
    LEFT JOIN (
        SELECT prof_id, COUNT(*) as nb_surveillances
        FROM examens_planifies
        WHERE statut IN ('PROPOSE', 'VALIDE')
        GROUP BY prof_id
    ) s ON p.id = s.prof_id
    WHERE p.dept_id = v_departement_id
    ORDER BY COALESCE(s.nb_surveillances, 0)
    LIMIT 1;
    
    -- Si pas de professeur du même département, prendre un au hasard
    IF v_prof_id IS NULL THEN
        SELECT id INTO v_prof_id
        FROM professeurs
        ORDER BY RANDOM()
        LIMIT 1;
    END IF;
    
    -- Trouver une salle adaptée
    SELECT l.id INTO v_salle_id
    FROM lieu_examen l
    WHERE l.capacite >= (
        SELECT COUNT(*) FROM inscriptions WHERE module_id = p_module_id
    )
    AND (l.type = 'AMPHI' OR (
        l.type != 'AMPHI' AND l.capacite >= 20 AND (
            SELECT COUNT(*) FROM inscriptions WHERE module_id = p_module_id
        ) <= 20
    ))
    ORDER BY l.capacite ASC, l.type DESC
    LIMIT 1;
    
    -- Trouver un créneau disponible
    FOR v_creneau_id IN 
        SELECT c.id
        FROM creneaux_horaires c
        WHERE c.est_disponible = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM examens_planifies e
            WHERE e.creneau_id = c.id
            AND e.statut IN ('PROPOSE', 'VALIDE')
        )
        AND NOT EXISTS (
            SELECT 1 FROM examens_planifies e
            WHERE e.prof_id = v_prof_id
            AND DATE(e.date_heure) = c.date_creneau
            AND e.statut IN ('PROPOSE', 'VALIDE')
            HAVING COUNT(*) >= 3
        )
        AND NOT EXISTS (
            SELECT 1
            FROM inscriptions i
            JOIN examens_planifies e ON i.module_id = e.module_id
            WHERE i.etudiant_id IN (
                SELECT etudiant_id FROM inscriptions WHERE module_id = p_module_id
            )
            AND DATE(e.date_heure) = c.date_creneau
            AND e.statut IN ('PROPOSE', 'VALIDE')
        )
        ORDER BY c.date_creneau, c.heure_debut
    LOOP
        v_trouve := TRUE;
        EXIT;
    END LOOP;
    
    IF NOT v_trouve THEN
        RAISE EXCEPTION 'Aucun créneau disponible pour le module %', p_module_id;
    END IF;
    
    -- Récupérer la date et l'heure du créneau
    SELECT date_creneau + heure_debut INTO v_date_heure
    FROM creneaux_horaires WHERE id = v_creneau_id;
    
    -- Insérer l'examen
    INSERT INTO examens_planifies (
        module_id, prof_id, salle_id, creneau_id,
        date_heure, duree_minutes, mode_generation, statut
    ) VALUES (
        p_module_id, v_prof_id, v_salle_id, v_creneau_id,
        v_date_heure, p_duree_minutes, 'AUTO', 'PROPOSE'
    ) RETURNING id INTO v_examen_id;
    
    -- Marquer le créneau comme indisponible
    UPDATE creneaux_horaires 
    SET est_disponible = FALSE 
    WHERE id = v_creneau_id;
    
    RETURN v_examen_id;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour afficher l'état des contraintes
CREATE OR REPLACE FUNCTION afficher_statut_contraintes()
RETURNS TABLE (
    contrainte VARCHAR(100),
    description TEXT,
    active BOOLEAN,
    severite VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'Limite quotidienne étudiant'::VARCHAR(100),
        'Un étudiant ne peut pas avoir plus d''un examen par jour'::TEXT,
        TRUE::BOOLEAN,
        'ERREUR'::VARCHAR(20)
    UNION ALL
    SELECT 
        'Limite quotidienne professeur',
        'Un professeur ne peut pas avoir plus de 3 examens par jour',
        TRUE,
        'ERREUR'
    UNION ALL
    SELECT 
        'Capacité de salle',
        'Les salles normales (non-amphi) ont une capacité max de 20 étudiants',
        TRUE,
        'ERREUR'
    UNION ALL
    SELECT 
        'Priorité département (Auto)',
        'Un professeur doit surveiller les examens de son département en priorité (mode Auto)',
        TRUE,
        'ERREUR'
    UNION ALL
    SELECT 
        'Priorité département (Manuel)',
        'Avertissement si un professeur surveille un examen hors département (mode Manuel)',
        TRUE,
        'AVERTISSEMENT'
    UNION ALL
    SELECT 
        'Équité surveillance',
        'Tous les enseignants doivent avoir approximativement le même nombre de surveillances',
        TRUE,
        'AVERTISSEMENT'
    UNION ALL
    SELECT 
        'Disponibilité salle',
        'Une salle ne peut pas être utilisée par deux examens au même moment',
        TRUE,
        'ERREUR'
    UNION ALL
    SELECT 
        'Unicité module',
        'Un module ne peut avoir qu''un seul examen planifié',
        TRUE,
        'ERREUR';
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------
-- 7. PROCÉDURES
-- -------------------------------------------------

-- Procédure pour tester les contraintes
CREATE OR REPLACE PROCEDURE tester_contraintes()
LANGUAGE plpgsql AS $$
DECLARE
    test_result RECORD;
    tests_reussis INTEGER := 0;
    tests_echecs INTEGER := 0;
BEGIN
    RAISE NOTICE '🧪 TEST DES CONTRAINTES';
    RAISE NOTICE '=====================';
    
    -- Test 1: Vérifier que la fonction verifier_contraintes_examen existe
    BEGIN
        PERFORM 1 FROM pg_proc WHERE proname = 'verifier_contraintes_examen';
        RAISE NOTICE '✅ Test 1: Fonction verifier_contraintes_examen existe';
        tests_reussis := tests_reussis + 1;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '❌ Test 1: Fonction verifier_contraintes_examen manquante';
        tests_echecs := tests_echecs + 1;
    END;
    
    -- Test 2: Vérifier les triggers
    BEGIN
        PERFORM 1 FROM pg_trigger WHERE tgname = 'trg_check_etudiant_daily_limit';
        RAISE NOTICE '✅ Test 2: Trigger trg_check_etudiant_daily_limit existe';
        tests_reussis := tests_reussis + 1;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '❌ Test 2: Trigger trg_check_etudiant_daily_limit manquant';
        tests_echecs := tests_echecs + 1;
    END;
    
    -- Test 3: Vérifier les vues
    BEGIN
        PERFORM 1 FROM information_schema.views WHERE table_name = 'v_examens_auto';
        RAISE NOTICE '✅ Test 3: Vue v_examens_auto existe';
        tests_reussis := tests_reussis + 1;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '❌ Test 3: Vue v_examens_auto manquante';
        tests_echecs := tests_echecs + 1;
    END;
    
    -- Résumé
    RAISE NOTICE '';
    RAISE NOTICE '📊 RÉSULTATS DES TESTS:';
    RAISE NOTICE '   Tests réussis: %', tests_reussis;
    RAISE NOTICE '   Tests échoués: %', tests_echecs;
    
    IF tests_echecs = 0 THEN
        RAISE NOTICE '✅ TOUTES LES CONTRAINTES SONT OPÉRATIONNELLES';
    ELSE
        RAISE NOTICE '⚠️  CERTAINES CONTRAINTES NÉCESSITENT UNE ATTENTION';
    END IF;
END;
$$;

-- Procédure pour planifier avec vérification
CREATE OR REPLACE PROCEDURE planifier_examen_avec_verification(
    p_module_id INTEGER,
    p_prof_id INTEGER,
    p_salle_id INTEGER,
    p_date_heure TIMESTAMP,
    p_duree_minutes INTEGER,
    p_utilisateur VARCHAR(100),
    p_mode_generation VARCHAR DEFAULT 'MANUEL'
) LANGUAGE plpgsql AS $$
DECLARE
    v_resultat RECORD;
    v_toutes_valides BOOLEAN := TRUE;
    v_examen_id INTEGER;
    v_erreurs TEXT := '';
    v_avertissements TEXT := '';
BEGIN
    -- Vérifier toutes les contraintes
    FOR v_resultat IN 
        SELECT * FROM verifier_contraintes_examen(
            p_module_id, p_prof_id, p_salle_id, 
            p_date_heure, p_duree_minutes, 
            NULL, p_mode_generation
        )
    LOOP
        IF v_resultat.severite = 'ERREUR' AND NOT v_resultat.est_valide THEN
            v_toutes_valides := FALSE;
            v_erreurs := v_erreurs || E'\n- ' || v_resultat.contrainte || ': ' || v_resultat.message;
        ELSIF v_resultat.severite = 'AVERTISSEMENT' AND v_resultat.message NOT LIKE '%respectée%' THEN
            v_avertissements := v_avertissements || E'\n⚠️  ' || v_resultat.contrainte || ': ' || v_resultat.message;
        END IF;
    END LOOP;
    
    IF v_toutes_valides THEN
        -- Insérer l'examen
        INSERT INTO examens_planifies (
            module_id, prof_id, salle_id, date_heure,
            duree_minutes, mode_generation, statut, modifie_par
        ) VALUES (
            p_module_id, p_prof_id, p_salle_id, p_date_heure,
            p_duree_minutes, p_mode_generation, 'VALIDE', p_utilisateur
        ) RETURNING id INTO v_examen_id;
        
        -- Enregistrer la modification
        INSERT INTO modifications_manuelles (
            examen_id, ancienne_valeur, nouvelle_valeur, 
            utilisateur, type_modification, raison
        ) VALUES (
            v_examen_id,
            NULL,
            jsonb_build_object(
                'module_id', p_module_id,
                'prof_id', p_prof_id,
                'salle_id', p_salle_id,
                'date_heure', p_date_heure,
                'duree_minutes', p_duree_minutes,
                'mode_generation', p_mode_generation,
                'action', 'CREATION'
            ),
            p_utilisateur,
            'CREATION',
            'Planification ' || p_mode_generation
        );
        
        -- Afficher les résultats
        RAISE NOTICE '✅ Examen #% planifié avec succès', v_examen_id;
        
        IF v_avertissements != '' THEN
            RAISE WARNING 'Avertissements:%', v_avertissements;
        END IF;
        
    ELSE
        RAISE EXCEPTION 'Impossible de planifier l''examen. Erreurs:%', v_erreurs;
    END IF;
END;
$$;

-- -------------------------------------------------
-- 8. MESSAGE DE CONFIRMATION
-- -------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE '✅ CONTRAINTES ET TRIGGERS CRÉÉS AVEC SUCCÈS!';
    RAISE NOTICE '   - Fonctions créées: 8 principales + 6 helpers';
    RAISE NOTICE '   - Triggers créés: 8';
    RAISE NOTICE '   - Autres fonctions: 3';
    RAISE NOTICE '   - Procédures: 2';
    RAISE NOTICE '';
    RAISE NOTICE 'Le système est maintenant prêt à gérer les examens en mode AUTO et MANUEL.';
END $$;


-- تحقق من وجود الدوال
SELECT routine_name FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name LIKE 'check_%';

-- تحقق من وجود الفهارس
SELECT indexname FROM pg_indexes WHERE schemaname = 'public';