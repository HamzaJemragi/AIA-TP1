"""
============================================================
MODULE : NETTOYAGE ET TRAITEMENT NLP
============================================================
Responsabilités :
  - Nettoyage du texte brut (HTML, caractères spéciaux)
  - Pipeline NLP : tokenisation, stopwords, lemmatisation
  - Traitement du dataset JSON → CSV nettoyé
============================================================
"""

import json
import os
import re
from xml.sax.saxutils import unescape

import pandas as pd
import spacy


# Chargement du modèle spaCy français (sans parser ni NER pour la vitesse)
nlp = spacy.load("fr_core_news_sm", disable=["parser", "ner"])


# ============================================================
# MODULE 4 : NETTOYAGE ET TRAITEMENT NLP
# ============================================================

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

    texte = unescape(texte)
    texte = re.sub(r'<[^>]+>', '', texte)
    texte = re.sub(r'\s+', ' ', texte)
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

    doc = nlp(texte.lower())

    tokens_nettoyes = [
        token.lemma_
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and len(token.text) > 2
    ]

    return " ".join(tokens_nettoyes)


def traiter_dataset(chemin_entree, dossier_sortie="data/nettoyees"):
    """
    Charge le JSON brut, applique le pipeline NLP et sauvegarde le CSV nettoyé.

    Args:
        chemin_entree (str): Chemin vers le fichier JSON brut.
        dossier_sortie (str): Dossier de destination du CSV.

    Returns:
        str: Chemin vers le fichier CSV produit.
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
    return chemin_csv