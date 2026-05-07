"""
============================================================
CONFIGURATION GLOBALE DU PROJET
============================================================
Centralise toutes les constantes et paramètres du pipeline.
============================================================
"""

# --- URLs ---
URL_BASE = "https://www.rekrute.com/"
URL_RECHERCHE = f"{URL_BASE}offres.html"

# --- Paramètres de scraping ---
PAGES_MAX = 5
DELAI_MIN = 1.5   # secondes (entre pages)
DELAI_MAX = 3.5
DELAI_OFFRE_MIN = 1.0  # secondes (entre offres)
DELAI_OFFRE_MAX = 2.5
TIMEOUT_REQUETE = 10   # secondes

# --- Chemins de fichiers ---
FICHIER_URLS_CSV = "urls_offres.csv"
DOSSIER_BRUTES = "data/brutes"
FICHIER_JSON_BRUT = "offres_details.json"
DOSSIER_NETTOYEES = "data/nettoyees"
FICHIER_CSV_PROPRE = "offres_nettoyees.csv"

# --- NLP ---
MODELE_SPACY = "fr_core_news_sm"

# --- Base de compétences techniques ---
SKILLS_DB = [
    'python', 'java', 'kotlin', 'flutter', 'dart', 'react', 'sql', 'nosql',
    'docker', 'aws', 'azure', 'machine learning', 'deep learning', 'cnn',
    'scikit-learn', 'tensorflow', 'pytorch', 'git', 'agile', 'api', 'rest'
]