"""
============================================================
POINT D'ENTRÉE PRINCIPAL — Pipeline Emploi Maroc
============================================================
Orchestre les 4 étapes du pipeline :
  1. Collecte des URLs (scrapping/url_extractor.py)
  2. Scraping des détails (scrapping/scraper.py)
  3. Nettoyage NLP (data/nettoyees/nlp_pipeline.py)
  4. Analyse & visualisation (analyse/visualisation.py)
============================================================
"""

import os
import sys

# Ajout du dossier racine au path pour les imports relatifs
sys.path.insert(0, os.path.dirname(__file__))

from scrapping.config import (
    URL_BASE, URL_RECHERCHE, PAGES_MAX,
    FICHIER_URLS_CSV, DOSSIER_BRUTES, FICHIER_JSON_BRUT,
    DOSSIER_NETTOYEES, FICHIER_CSV_PROPRE
)
from scrapping.scrape_emploi import (
    extraire_urls_multipage,
    sauvegarder_urls_csv,
    charger_urls_depuis_csv,
    configurer_session,
    scraper_offres,
    sauvegarder_donnees_json
)
from data.netoyees.nlp_pipeline import traiter_dataset
from data.analysees.visualisation import generer_rapport


def main():
    # ── Étape 1 : Collecte des URLs ──────────────────────────
    print("=" * 60)
    print("ÉTAPE 1 : Extraction des URLs")
    print("=" * 60)
    liens_recuperes = extraire_urls_multipage(URL_RECHERCHE, URL_BASE, PAGES_MAX)
    print(f"\n{len(liens_recuperes)} offres trouvées.")
    sauvegarder_urls_csv(liens_recuperes, FICHIER_URLS_CSV)

    # ── Étape 2 : Scraping des détails ───────────────────────
    print("\n" + "=" * 60)
    print("ÉTAPE 2 : Scraping des détails d'offres")
    print("=" * 60)
    urls = charger_urls_depuis_csv(FICHIER_URLS_CSV)[:5]
    session = configurer_session()
    details_offres = scraper_offres(urls, session)
    sauvegarder_donnees_json(details_offres, DOSSIER_BRUTES, FICHIER_JSON_BRUT)

    # ── Étape 3 : Nettoyage NLP ──────────────────────────────
    print("\n" + "=" * 60)
    print("ÉTAPE 3 : Nettoyage & traitement NLP")
    print("=" * 60)
    chemin_json = os.path.join(DOSSIER_BRUTES, FICHIER_JSON_BRUT)
    traiter_dataset(chemin_json, DOSSIER_NETTOYEES)

    # ── Étape 4 : Rapport analytique ─────────────────────────
    print("\n" + "=" * 60)
    print("ÉTAPE 4 : Génération du rapport")
    print("=" * 60)
    chemin_csv = os.path.join(DOSSIER_NETTOYEES, FICHIER_CSV_PROPRE)
    generer_rapport(chemin_csv)


if __name__ == "__main__":
    main()