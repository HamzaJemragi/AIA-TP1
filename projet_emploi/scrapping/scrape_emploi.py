"""
============================================================
SCRAPER & ANALYSEUR D'OFFRES D'EMPLOI — Rekrute.com
============================================================
Pipeline complet :
  1. Extraction des URLs sur plusieurs pages
  2. Scraping des détails de chaque offre
  3. Nettoyage et traitement NLP
  4. Génération d'un rapport analytique avec graphiques
============================================================
"""

import csv
import json
import os
import re
from collections import Counter
from xml.sax.saxutils import unescape

import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import random
from requests.adapters import HTTPAdapter
import spacy
from tqdm import tqdm
from urllib3.util.retry import Retry
import pandas as pd
from wordcloud import WordCloud
import seaborn as sns


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
    # En-tête HTTP simulant un navigateur pour éviter les blocages anti-bot
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url_recherche, headers=headers)
        response.raise_for_status()  # Lève une exception si code HTTP >= 400
        soup = BeautifulSoup(response.text, 'html.parser')

        urls_offres = []
        # Sélection des balises <a class="titreJob"> qui contiennent les liens des offres
        balises_liens = soup.findAll('a', class_='titreJob')

        for balise in balises_liens:
            url_offre = balise.get('href')
            if url_offre:
                # Reconstruction de l'URL absolue à partir du lien relatif
                url_complete = urljoin(base_url, url_offre)
                # Évite les doublons
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
    Arrêt automatique si aucune offre n'est trouvée sur une page (fin de la liste).

    Args:
        url_recherche_base (str): URL de base de la recherche (sans paramètre de page).
        url_site_base (str): URL racine du site.
        pages_max (int): Nombre maximum de pages à parcourir (limite de politesse).

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

            # Condition d'arrêt : plus aucune offre détectée -> fin de la pagination
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

            # Délai aléatoire pour éviter la détection et respecter le serveur
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
            writer.writerow(['url'])  # En-tête
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
    # Retry sur les codes d'erreur serveur courants
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
            # getattr + valeur par défaut pour gérer les champs absents proprement
            'titre': getattr(soup.find('h1'), 'text', 'N/A').strip(),
            'entreprise': getattr(soup.find('div', class_='company'), 'text', 'N/A').strip(),
            'lieu': getattr(soup.find('span', class_='location'), 'text', 'Non spécifié').strip(),
            'description': getattr(soup.find('div', class_='description'), 'text', 'N/A').strip(),
            'date_publication': getattr(soup.find('time'), 'text', 'Inconnue').strip(),
            # Liste des compétences balisées ou liste vide si absentes
            'competences': [li.text.strip() for li in soup.find_all('li', class_='skill-tag')] or [],
            'salaire': getattr(soup.find('span', class_='salary'), 'text', 'Non indiqué').strip(),
            'extraction_date': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return details

    except Exception as e:
        # En cas d'erreur, on retourne un dict minimal pour ne pas perdre l'URL
        return {"url": url, "erreur": str(e)}


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
        # ensure_ascii=False pour conserver les accents
        json.dump(donnees, f, indent=4, ensure_ascii=False)

    print(f"\nDonnées sauvegardées dans : {chemin_complet}")


# ============================================================
# MODULE 4 : NETTOYAGE ET TRAITEMENT NLP
# ============================================================

# Chargement du modèle spaCy français (sans parser syntaxique ni NER pour la vitesse)
nlp = spacy.load("fr_core_news_sm", disable=["parser", "ner"])


def nettoyage_texte(texte):
    """
    Nettoie un texte brut extrait du web.

    Étapes :
        1. Décodage des entités HTML (&nbsp;, &eacute;…)
        2. Suppression des balises HTML résiduelles
        3. Normalisation des espaces et retours à la ligne
        4. Suppression des caractères spéciaux (hors lettres, chiffres, ponctuation de base)

    Args:
        texte (str): Texte brut à nettoyer.

    Returns:
        str: Texte nettoyé.
    """
    if not texte or texte == "N/A":
        return ""

    texte = unescape(texte)                                  # Étape 1
    texte = re.sub(r'<[^>]+>', '', texte)                    # Étape 2
    texte = re.sub(r'\s+', ' ', texte)                       # Étape 3
    # Étape 4 : on conserve lettres (avec accents), chiffres et ponctuation standard
    texte = re.sub(
        r'[^a-zA-Z0-9àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ.,!?;: ]', '', texte
    )

    return texte.strip()


def pipeline_nlp(texte):
    """
    Tokenisation, suppression des stopwords et lemmatisation via spaCy.

    Args:
        texte (str): Texte nettoyé à traiter.

    Returns:
        str: Chaîne de lemmes filtrés, séparés par des espaces.
    """
    if not texte:
        return ""

    doc = nlp(texte.lower())  # Passage en minuscule avant traitement

    tokens_nettoyes = [
        token.lemma_           # Forme canonique (lemme) du token
        for token in doc
        if not token.is_stop   # Filtre les mots vides (de, le, et…)
        and not token.is_punct # Filtre la ponctuation
        and len(token.text) > 2  # Filtre les tokens trop courts (bruit)
    ]

    return " ".join(tokens_nettoyes)


def traiter_dataset(chemin_entree, dossier_sortie="data/nettoyees"):
    """
    Charge le JSON brut, applique le pipeline NLP et sauvegarde le CSV nettoyé.

    Args:
        chemin_entree (str): Chemin vers le fichier JSON brut.
        dossier_sortie (str): Dossier de destination du CSV.
    """
    with open(chemin_entree, 'r', encoding='utf-8') as f:
        data = json.load(f)

    df = pd.DataFrame(data)

    print("Nettoyage et traitement NLP en cours...")
    df['description_propre'] = df['description'].apply(nettoyage_texte)
    df['description_tokenisee'] = df['description_propre'].apply(pipeline_nlp)

    if not os.path.exists(dossier_sortie):
        os.makedirs(dossier_sortie)

    chemin_csv = os.path.join(dossier_sortie, "offres_nettoyees.csv")
    df.to_csv(chemin_csv, index=False, encoding='utf-8-sig')

    print(f"Traitement terminé. Fichier sauvegardé : {chemin_csv}")


# ============================================================
# MODULE 5 : ANALYSE ET VISUALISATION
# ============================================================

# Base de compétences techniques à rechercher dans les descriptions
SKILLS_DB = [
    'python', 'java', 'kotlin', 'flutter', 'dart', 'react', 'sql', 'nosql',
    'docker', 'aws', 'azure', 'machine learning', 'deep learning', 'cnn',
    'scikit-learn', 'tensorflow', 'pytorch', 'git', 'agile', 'api', 'rest'
]


def extraire_competences(texte):
    """
    Détecte les compétences techniques présentes dans un texte.

    Utilise des expressions régulières avec délimiteurs de mots (\b)
    pour éviter les faux positifs (ex: "rest" dans "interest").

    Args:
        texte (str): Description nettoyée de l'offre.

    Returns:
        list[str]: Liste des compétences identifiées.
    """
    if not isinstance(texte, str):
        return []
    texte = texte.lower()
    trouvees = [skill for skill in SKILLS_DB if re.search(rf'\b{skill}\b', texte)]
    return trouvees


def generer_rapport(chemin_csv):
    """
    Génère un rapport analytique visuel à partir du CSV nettoyé.

    Visualisations produites :
        A. Barplot horizontal — Top 10 compétences
        B. Camembert — Répartition géographique (Top 5 villes)
        C. Nuage de mots — Termes fréquents dans les descriptions
        D. Histogramme — Distribution des salaires

    Args:
        chemin_csv (str): Chemin vers le fichier CSV nettoyé.
    """
    df = pd.read_csv(chemin_csv)

    # --- Extraction des compétences ---
    df['skills_found'] = df['description_propre'].apply(extraire_competences)
    all_skills = [s for sublist in df['skills_found'] for s in sublist]
    print(all_skills)
    top_10_skills = Counter(all_skills)

    # --- Statistiques de base ---
    total_offres = len(df)
    villes = df['lieu'].value_counts()

    # --- Analyse des salaires (extraction numérique depuis les chaînes) ---
    def clean_salary(val):
        if pd.isna(val) or 'indiqué' in str(val).lower():
            return None
        nums = re.findall(r'\d+', str(val).replace(' ', ''))
        return int(nums[0]) if nums else None

    df['salaire_num'] = df['salaire'].apply(clean_salary)
    avg_salary = df['salaire_num'].mean()

    # --- Création de la figure avec 4 sous-graphiques ---
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    plt.subplots_adjust(hspace=0.4)

    # A. Top 10 Compétences (Barplot horizontal)
    print(top_10_skills)
    print(zip(*top_10_skills))
    skills_labels, skills_counts = list(zip(*top_10_skills))
    sns.barplot(x=list(skills_counts), y=list(skills_labels),
                ax=axs[0, 0], palette='viridis')
    axs[0, 0].set_title('Top 10 des Compétences Demandées')

    # B. Répartition géographique (Camembert Top 5)
    villes.head(5).plot.pie(autopct='%1.1f%%', ax=axs[0, 1])
    axs[0, 1].set_title('Répartition Géographique (Top 5)')
    axs[0, 1].set_ylabel('')

    # C. Nuage de mots des descriptions tokenisées
    text_cloud = " ".join(df['description_tokenisee'].dropna())
    wordcloud = WordCloud(width=800, height=400,
                          background_color='white').generate(text_cloud)
    axs[1, 0].imshow(wordcloud, interpolation='bilinear')
    axs[1, 0].axis('off')
    axs[1, 0].set_title('Nuage de mots des descriptions')

    # D. Distribution des salaires (histogramme + KDE)
    sns.histplot(df['salaire_num'].dropna(), kde=True, ax=axs[1, 1], color='g')
    axs[1, 1].set_title('Distribution des Salaires')

    plt.show()

    # --- Rapport textuel ---
    print(f"--- RAPPORT DE SCRAPING ---")
    print(f"Nombre total d'offres : {total_offres}")
    print(f"Salaire moyen détecté : {avg_salary:.2f} (unités locales)")
    print(f"Top compétence : {top_10_skills[0][0]} ({top_10_skills[0][1]} mentions)")


# ============================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================

if __name__ == "__main__":
    URL_BASE = "https://www.rekrute.com/"
    URL_RECHERCHE = f"{URL_BASE}/offres.html"

    # --- Étape 1 : Collecte des URLs ---
    print("Démarrage de l'extraction des URLs...")
    liens_recuperes = extraire_urls_multipage(URL_RECHERCHE, URL_BASE)

    print(f"\n{len(liens_recuperes)} offres trouvées :")
    for i, lien in enumerate(liens_recuperes, 1):
        print(f"{i}. {lien}")

    sauvegarder_urls_csv(liens_recuperes)

    # --- Étape 2 : Extraction des détails de chaque offre ---
    urls = charger_urls_depuis_csv()[:5]
    session = configurer_session()
    details_offres = []

    for url in tqdm(urls, desc="Traitement des offres", unit="offre"):
        info = extraire_details_offre(url, session)
        details_offres.append(info)
        time.sleep(random.uniform(1.0, 2.5))  # Politesse inter-requêtes

    sauvegarder_donnees_json(details_offres)

    # --- Étape 3 : Nettoyage NLP ---
    traiter_dataset("data/brutes/offres_details.json")

    # --- Étape 4 : Génération du rapport ---
    generer_rapport("data/nettoyees/offres_nettoyees.csv")