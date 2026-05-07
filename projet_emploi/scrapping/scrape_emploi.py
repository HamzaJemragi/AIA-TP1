"""
============================================================
MODULE : EXTRACTION & PERSISTANCE DES URLs
============================================================
Responsabilités :
  1. Extraction des URLs d'offres sur une page de résultats
  2. Pagination automatique (multi-pages)
  3. Sauvegarde et rechargement depuis CSV
============================================================
"""

import csv
import os
import time
import random

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ============================================================
# MODULE 1 : EXTRACTION DES URLs
# ============================================================

def extraire_urls_offres(url_recherche, base_url):
    """
    Extrait les URLs des offres d'emploi depuis une page de résultats unique.

    Args:
        url_recherche (str): URL de la page de résultats Rekrute.
        base_url (str): URL de base du site (pour reconstruire les liens relatifs).

    Returns:
        list[str]: Liste des URLs complètes des offres trouvées sur la page.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url_recherche, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        urls_offres = []
        balises_liens = soup.findAll('a', class_='titreJob')

        for balise in balises_liens:
            url_offre = balise.get('href')
            if url_offre:
                url_complete = urljoin(base_url, url_offre)
                if url_complete not in urls_offres:
                    urls_offres.append(url_complete)

        return urls_offres

    except requests.RequestException as e:
        print(f"Erreur lors de la requête : {e}")
        return []


def extraire_urls_multipage(url_recherche_base, url_site_base, pages_max=5):
    """
    Parcourt plusieurs pages de résultats et collecte toutes les URLs d'offres.

    Stratégie de pagination : paramètre ?p=N dans l'URL.
    Arrêt automatique si aucune offre n'est trouvée sur une page.

    Args:
        url_recherche_base (str): URL de base de la recherche (sans paramètre de page).
        url_site_base (str): URL racine du site.
        pages_max (int): Nombre maximum de pages à parcourir.

    Returns:
        list[str]: Liste dédupliquée de toutes les URLs d'offres récupérées.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }

    toutes_les_urls = []

    for numero_page in range(1, pages_max + 1):
        url_courante = f"{url_recherche_base}?p={numero_page}"
        print(f"Scraping en cours -> Page {numero_page} : {url_courante}")

        try:
            response = requests.get(url_courante, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            balises_liens = soup.find_all('a', class_='titreJob')

            if not balises_liens:
                print("Aucune offre trouvée sur cette page. Fin de la pagination.")
                break

            urls_page_courante = 0
            for balise in balises_liens:
                lien_offre = balise.get('href')
                if lien_offre:
                    lien_complete = urljoin(url_site_base, lien_offre)
                    if lien_complete not in toutes_les_urls:
                        toutes_les_urls.append(lien_complete)
                        urls_page_courante += 1

            print(f"  > {urls_page_courante} nouveaux liens extraits.")

            delai = random.uniform(1.5, 3.5)
            time.sleep(delai)

        except requests.exceptions.RequestException as e:
            print(f"Erreur rencontrée sur la page {numero_page} : {e}")
            break

    return toutes_les_urls


# ============================================================
# MODULE 2 : PERSISTANCE DES URLs
# ============================================================

def sauvegarder_urls_csv(liste_urls, nom_fichier="urls_offres.csv"):
    """
    Sauvegarde la liste des URLs dans un fichier CSV (colonne unique 'url').

    Args:
        liste_urls (list[str]): URLs à sauvegarder.
        nom_fichier (str): Chemin du fichier CSV de sortie.
    """
    if not liste_urls:
        print("Aucune URL à sauvegarder.")
        return

    try:
        with open(nom_fichier, mode='w', encoding='utf-8', newline='') as fichier_csv:
            writer = csv.writer(fichier_csv)
            writer.writerow(['url'])
            for url in liste_urls:
                writer.writerow([url])

        print(f"Succès : {len(liste_urls)} URLs sauvegardées dans '{nom_fichier}'.")

    except IOError as e:
        print(f"Erreur lors de l'écriture du fichier : {e}")


def charger_urls_depuis_csv(nom_fichier="urls_offres.csv"):
    """
    Recharge la liste des URLs depuis un fichier CSV précédemment sauvegardé.

    Args:
        nom_fichier (str): Chemin du fichier CSV.

    Returns:
        list[str]: Liste des URLs.
    """
    urls = []
    if os.path.exists(nom_fichier):
        with open(nom_fichier, mode='r', encoding='utf-8') as fichier:
            reader = csv.DictReader(fichier)
            for ligne in reader:
                urls.append(ligne['url'])
    return urls


# ============================================================
# MODULE 3 : SCRAPING DES DÉTAILS D'OFFRE
# ============================================================

def configurer_session():
    """
    Configure une session requests robuste avec retry automatique.

    Stratégie : 3 tentatives max, backoff exponentiel x1,
    déclenchée sur les erreurs serveur (5xx).

    Returns:
        requests.Session: Session configurée et prête à l'emploi.
    """
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def extraire_details_offre(url, session):
    """
    Extrait les informations détaillées d'une offre d'emploi individuelle.

    Champs extraits :
        - titre, entreprise, lieu, description
        - date de publication, compétences (balises skill-tag)
        - salaire, date d'extraction

    Args:
        url (str): URL de la page d'offre.
        session (requests.Session): Session HTTP configurée.

    Returns:
        dict: Dictionnaire des informations extraites.
              Contient une clé 'erreur' en cas d'échec.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        details = {
            'url': url,
            'titre': getattr(soup.find('h1'), 'text', 'N/A').strip(),
            'entreprise': getattr(soup.find('div', class_='company'), 'text', 'N/A').strip(),
            'lieu': getattr(soup.find('span', class_='location'), 'text', 'Non spécifié').strip(),
            'description': getattr(soup.find('div', class_='description'), 'text', 'N/A').strip(),
            'date_publication': getattr(soup.find('time'), 'text', 'Inconnue').strip(),
            'competences': [li.text.strip() for li in soup.find_all('li', class_='skill-tag')] or [],
            'salaire': getattr(soup.find('span', class_='salary'), 'text', 'Non indiqué').strip(),
            'extraction_date': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return details

    except Exception as e:
        return {"url": url, "erreur": str(e)}


def scraper_offres(urls, session=None):
    """
    Lance le scraping complet d'une liste d'URLs d'offres.

    Args:
        urls (list[str]): Liste des URLs à scraper.
        session (requests.Session, optional): Session HTTP. Créée automatiquement si None.

    Returns:
        list[dict]: Liste des dictionnaires d'offres extraites.
    """
    from tqdm import tqdm

    if session is None:
        session = configurer_session()

    details_offres = []
    for url in tqdm(urls, desc="Traitement des offres", unit="offre"):
        info = extraire_details_offre(url, session)
        details_offres.append(info)
        time.sleep(random.uniform(1.0, 2.5))  # Politesse inter-requêtes

    return details_offres


def sauvegarder_donnees_json(donnees, dossier="data/brutes", nom_fichier="offres_details.json"):
    """
    Sauvegarde la liste des offres au format JSON indenté.

    Args:
        donnees (list[dict]): Liste des dictionnaires d'offres.
        dossier (str): Dossier de destination (créé si inexistant).
        nom_fichier (str): Nom du fichier JSON de sortie.
    """
    if not os.path.exists(dossier):
        os.makedirs(dossier)

    chemin_complet = os.path.join(dossier, nom_fichier)

    with open(chemin_complet, 'w', encoding='utf-8') as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)

    print(f"\nDonnées sauvegardées dans : {chemin_complet}")