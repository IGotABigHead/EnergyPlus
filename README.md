# EnergyPlus Digital Twin Project

Ce projet propose une plateforme web pour manipuler des fichiers EnergyPlus (IDF, EPW), lancer des simulations, et visualiser/analyser les résultats énergétiques et de confort par zone/poste/temps.

## Fonctionnalités principales
- Upload, versioning et édition rapide de fichiers IDF/EPW
- Lancement de simulations EnergyPlus depuis l'interface web
- Stockage des résultats en base de données (MySQL)
- API REST pour requêtes analytiques (énergie, température, PMV, etc.)
- Interface front-end (Next.js/React) pour l’édition, la sélection et la visualisation

---

## Structure du projet

```
Git/
├── api_server.py              # Serveur FastAPI (API principale)
├── requirements.txt           # Dépendances Python (API)
├── res/                       # Résultats CSV des simulations
├── front_modif_files/         # Front-end Next.js/React
├── API_Documentation.md       # Documentation de l'API
└── ...
```

---

## Installation & Lancement

### Prérequis
- Python 3.10+ (API)
- Node.js 18+ (front)
- MySQL (base de données)
- EnergyPlus installé (chemin modifiable dans `api_server.py`)
- (Optionnel) Docker & docker-compose

### 1. Lancer la base de données
Configurer un MySQL local avec un utilisateur `root:root` et une base `energyplus` (ou adapter la chaîne dans `api_server.py`).

### 2. Lancer l’API
```bash
pip install -r requirements.txt
python api_server.py
```
L’API sera disponible sur http://localhost:8000

### 3. Lancer le front-end
```bash
cd front_modif_files
npm install
npm run dev
```
Le front sera disponible sur http://localhost:3000


---

## Documentation de l’API

Voir le fichier [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) pour la liste complète des endpoints, paramètres et exemples de réponses.

---

## Personnalisation
- Le chemin vers EnergyPlus, le chemin pour le stockage des fichiers CSV (lignes 277, 759, 777) et eppy (ligne 20) est à adapter dans `api_server.py` selon votre installation.
- Les zones par défaut sont initialisées dans la base si absentes.
- Les résultats sont stockés dans `res/` et en base SQL.

