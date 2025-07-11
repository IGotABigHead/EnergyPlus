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
├── api_server.py                    # Serveur FastAPI (API principale)
├── requirements.txt                 # Dépendances Python (API)
├── front_modif_files/               # Front-end Next.js/React
├── API_Documentation.md             # Documentation de l'API
├── config.json                      # Fichier de configuration de l'app
├── API_Documentation.md             # Documentation de l'API
├── FRA_Paris.Orly.071490_IWEC.epw   # Fichier météo
├── NR3_V07-24.idf                   # Fichier batiment
└── ...
```

---

## Configuration

Toute la configuration de l’API (chemin du fichier IDD EnergyPlus, chemin de la librairie eppy, chaîne de connexion à la base de données, CORS, etc.) se fait désormais dans le fichier `config.json` à la racine du projet.

Exemple de contenu du fichier `config.json` :

```json
{
  "ENERGYPLUS_IDD_PATH": "C:/EnergyPlusV9-4-0/Energy+.idd",
  "EPPY_LIB_PATH": "C:/Users/Cesi/AppData/Local/Programs/Python/Python313/Lib/site-packages/eppy",
  "DATABASE_URL": "mysql+mysqldb://root:root@localhost/energyplus",
  "CORS_ORIGINS": ["http://localhost:3000"],
  "API_HOST": "0.0.0.0",
  "API_PORT": 8000
}
```

Pour modifier un paramètre, il suffit de changer la valeur correspondante dans ce fichier, puis de relancer l’API.

---

## Installation & Lancement

### Prérequis
- Python 3.10+ (API)
- Node.js 18+ (front)
- MySQL (base de données)
- EnergyPlus installé (chemin modifiable dans `api_server.py`)
- (Optionnel) Docker & docker-compose

## Personnalisation
- Le chemin vers EnergyPlus (ligne 27 du fichier API) et eppy (ligne 20 du fichier API) sont à adapter dans `api_server.py` selon votre installation.
- Penser à changer tous les chemins qui sont en localhost vers l'adresse des serveurs à utiliser
- Pour la BD, il faut modifier la variable "DATABASE_URL" (ligne 30) du fichier API, en modifiant le user, mdp et le nom de la base utilisé

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
De plus une documentation générée automatiquement est disponible à la route suivante : http://localhost:8000/docs

---

Retrouver le projet Unreal Engine sur le dépôt : https://github.com/IGotABigHead/EnergyPlus_UnrealEngine