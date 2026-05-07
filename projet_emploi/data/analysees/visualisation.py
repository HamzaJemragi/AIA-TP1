"""
============================================================
MODULE : ANALYSE ET VISUALISATION
============================================================
Responsabilités :
  - Extraction des compétences techniques depuis les descriptions
  - Génération d'un rapport analytique avec 4 graphiques :
      A. Top 10 compétences (barplot)
      B. Répartition géographique (camembert)
      C. Nuage de mots des descriptions
      D. Distribution des salaires (histogramme)
============================================================
"""

import re
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from wordcloud import WordCloud


# Base de compétences techniques à rechercher dans les descriptions
SKILLS_DB = [
    'python', 'java', 'kotlin', 'flutter', 'dart', 'react', 'sql', 'nosql',
    'docker', 'aws', 'azure', 'machine learning', 'deep learning', 'cnn',
    'scikit-learn', 'tensorflow', 'pytorch', 'git', 'agile', 'api', 'rest'
]


# ============================================================
# MODULE 5 : ANALYSE ET VISUALISATION
# ============================================================

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
    top_10_skills = Counter(all_skills).most_common(10)

    # --- Statistiques de base ---
    total_offres = len(df)
    villes = df['lieu'].value_counts()

    # --- Analyse des salaires ---
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
    if top_10_skills:
        skills_labels, skills_counts = zip(*top_10_skills)
        sns.barplot(x=list(skills_counts), y=list(skills_labels),
                    ax=axs[0, 0], palette='viridis')
    axs[0, 0].set_title('Top 10 des Compétences Demandées')

    # B. Répartition géographique (Camembert Top 5)
    villes.head(5).plot.pie(autopct='%1.1f%%', ax=axs[0, 1])
    axs[0, 1].set_title('Répartition Géographique (Top 5)')
    axs[0, 1].set_ylabel('')

    # C. Nuage de mots des descriptions tokenisées
    text_cloud = " ".join(df['description_tokenisee'].dropna())
    if text_cloud.strip():
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
    if avg_salary:
        print(f"Salaire moyen détecté : {avg_salary:.2f} (unités locales)")
    if top_10_skills:
        print(f"Top compétence : {top_10_skills[0][0]} ({top_10_skills[0][1]} mentions)")