-- ============================================
-- FICHIER: 00_connection_test.sql
-- DESCRIPTION: Test de connexion et vérification
-- ============================================

-- Vérifier la version de PostgreSQL
SELECT version();

-- Lister toutes les bases de données
SELECT datname FROM pg_database;

-- Vérifier si la base exam_platform existe
SELECT '✅ Base de données exam_platform créée avec succès' as message
WHERE EXISTS (SELECT 1 FROM pg_database WHERE datname = 'exam_platform');

-- Vérifier les privilèges
SELECT current_user, current_database();