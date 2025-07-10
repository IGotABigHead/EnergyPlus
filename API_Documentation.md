# Documentation de l'API EnergyPlus

Cette API permet de gérer des fichiers d'entrée (IDF, EPW), de lancer des simulations EnergyPlus, et d'accéder aux résultats (énergie, température, PMV, etc.) par zone, poste, date, etc.

---

## Table des matières
- [Fichiers d'entrée](#fichiers-dentrée)
- [Simulation](#simulation)
- [Résultats et requêtes analytiques](#résultats-et-requêtes-analytiques)
- [Objets IDF](#objets-idf)
- [Divers](#divers)

---

## Fichiers d'entrée

### `GET /input_file/by_id/{file_id}`
Récupère un fichier d'entrée par son ID.

**Réponse :**
```json
{
  "_id": "1",
  "file_type": "idf",
  "filename": "NR3_V07-24.idf",
  "content": "...contenu du fichier..."
}
```

### `GET /input_file/by_simulation/{simulation_name}`
Récupère les fichiers d'entrée (idf, epw) associés à une simulation.

**Réponse :**
```json
{
  "idf": { ... },
  "epw": { ... }
}
```

### `POST /input_file/update/{file_id}`
Met à jour le contenu d'un fichier d'entrée (base64).

**Body :**
- `content` (str, requis)

**Réponse :** `{ "status": "ok" }`

### `GET /input_files/?file_type=...`
Liste les fichiers d'entrée d'un type donné (`idf` ou `epw`).

**Réponse :**
```json
[
  { "_id": "1", "filename": "...", "upload_date": "...", "version": 1 },
  ...
]
```

### `POST /input_file/save_new_version/{file_id}`
Crée une nouvelle version d'un fichier d'entrée.

**Body :**
- `content` (str, requis)
- `filename` (str, optionnel)

**Réponse :** `{ "status": "ok", "new_id": "..." }`

### `POST /input_file/upload/?file_type=...`
Upload d'un fichier d'entrée (multipart/form-data).

**Réponse :** `{ "status": "ok", "new_id": "..." }`

---

## Simulation

### `POST /run_simulation/`
Lance une simulation EnergyPlus à partir de fichiers IDF et EPW.

**Body :**
- `idf_file_id` (int, requis)
- `epw_file_id` (int, requis)

**Réponse :**
```json
{
  "status": "success",
  "simulation_name": "NR3_V07-24_1",
  "message": "Simulation ... terminée. CSV copié dans ...",
  "results_count": 8760,
  "stdout": "...",
  "stderr": "",
  "elapsed_time_seconds": 12.34
}
```

---

## Résultats et requêtes analytiques

### `GET /zones/`
Liste les zones connues.

**Réponse :**
```json
[
  { "id": 1, "name": "BUREAUETAGE" }, ...
]
```

### `GET /sum_all_energy/`
Somme de l'énergie totale (toutes zones, tout poste).

**Query params :**
- `simulation_name` (str, optionnel)
- `date` (str, optionnel, format M/D ou MM/DD)
- `hour` (str, optionnel, format H ou HH)

**Réponse :**
```json
{
  "simulation_name": "...",
  "date": "...",
  "hour": "...",
  "total_energy_all_fields": 123456.0,
  "total_energy_all_fields_kwh": 34.29
}
```

### `GET /sum_room_energy/`
Somme de l'énergie pour une zone donnée.

**Query params :**
- `room` (str, requis)
- autres : voir ci-dessus

**Réponse :**
```json
{
  "simulation_name": "...",
  "room": "NOBEL",
  "total_energy_room": 12345.0,
  "total_energy_room_kwh": 3.43
}
```

### `GET /sum_by_poste/`
Somme de l'énergie pour un poste donné (ex: Heating, Cooling, Electricity, etc.).

**Query params :**
- `poste` (str, requis)
- autres : voir ci-dessus

### `GET /sum_by_room_and_poste/`
Somme de l'énergie pour une zone et un poste donnés.

**Query params :**
- `room` (str, requis)
- `poste` (str, requis)
- autres : voir ci-dessus

### `GET /pmv_by_room/`
Liste des valeurs PMV pour une zone.

**Query params :**
- `room` (str, requis)
- autres : voir ci-dessus

### `GET /temperature_by_room/`
Liste des températures pour une zone.

**Query params :**
- `room` (str, requis)
- autres : voir ci-dessus

### `GET /room_summary/`
Résumé agrégé pour une zone (ou toutes zones).

**Query params :**
- `room` (str, optionnel)
- autres : voir ci-dessus

**Réponse :**
```json
{
  "simulation_name": "...",
  "room": "NOBEL",
  "data": {
    "total_energy_kwh": 12.3,
    "detailed_energy_kwh": { "equipment": 1.2, "lights": 0.8 },
    "total_energy_transfer_kwh": 2.1,
    "detailed_energy_transfer": { "total_heating_transfer_kwh": 1.1, "total_cooling_transfer_kwh": 1.0 },
    "fans_electricity_kwh": 0.5,
    "total_energy_consommation": 14.9,
    "pmv_values": 0.2,
    "temperature_values": 22.5,
    "humidity_values": 45.0
  }
}
```

---

## Objets IDF

### `GET /get_idf_objects/{file_id}`
Retourne la structure des objets IDF d'un fichier.

**Réponse :**
```json
{
  "ZONE": [ { "fields": { ... } }, ... ],
  ...
}
```

### `POST /update_idf_field/{file_id}`
Met à jour un champ d'un objet IDF.

**Body :**
```json
{
  "object_type": "ZONE",
  "object_index": 0,
  "field_name": "Name",
  "new_value": "NOUVEAU_NOM"
}
```

**Réponse :** `{ "status": "success", "new_content": "..." }`

---

## Divers

### `GET /simulations`
Liste les simulations existantes (par nom).

**Réponse :**
```json
{ "simulations": [ "NR3_V07-24_1", ... ] }
```

---

## Notes
- Tous les endpoints peuvent retourner des erreurs HTTP 404 ou 500 en cas de problème.
- Les paramètres de date/heure sont optionnels et permettent de filtrer les résultats.
- Les unités d'énergie sont en Joules, sauf indication contraire (kWh calculé).
- Pour plus de détails, voir le code source `api_server.py`. 