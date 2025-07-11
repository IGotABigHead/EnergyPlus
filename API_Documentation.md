# Documentation API EnergyPlus (détails des paramètres)

Cette API permet de gérer les fichiers d’entrée (IDF, EPW), lancer des simulations et consulter les résultats énergétiques, thermiques, etc.

---

## Gestion des fichiers d’entrée

### 1. Récupérer un fichier par ID  
`GET /input_file/by_id/{file_id}`

- **Paramètres URL :**  
  - `file_id` (int, **requis**) : Identifiant du fichier.

**Réponse :** Contenu complet du fichier.

---

### 2. Récupérer les fichiers liés à une simulation  
`GET /input_file/by_simulation/{simulation_name}`

- **Paramètres URL :**  
  - `simulation_name` (string, **requis**) : Nom de la simulation.

**Réponse :** Les fichiers `idf` et `epw` associés.

---

### 3. Mettre à jour un fichier (contenu base64)  
`POST /input_file/update/{file_id}`

- **Paramètres URL :**  
  - `file_id` (int, **requis**)

- **Body JSON :**  
  - `content` (string, **requis**) : Contenu du fichier encodé en base64.

---

### 4. Lister les fichiers d’un type  
`GET /input_files/`

- **Query params :**  
  - `file_type` (string, **optionnel**) : Type de fichier, soit `"idf"` soit `"epw"`.

---

### 5. Créer une nouvelle version d’un fichier  
`POST /input_file/save_new_version/{file_id}`

- **Paramètres URL :**  
  - `file_id` (int, **requis**)

- **Body JSON :**  
  - `content` (string, **requis**) : Nouveau contenu base64.  
  - `filename` (string, **optionnel**) : Nom du fichier.

---

### 6. Upload d’un nouveau fichier  
`POST /input_file/upload/`

- **Query params :**  
  - `file_type` (string, **requis**) : `"idf"` ou `"epw"`.

- **Body :**  
  - Multipart/form-data avec fichier à uploader.

---

## Simulation

### 7. Lancer une simulation EnergyPlus  
`POST /run_simulation/`

- **Body JSON :**  
  - `idf_file_id` (int, **requis**) : ID du fichier IDF.  
  - `epw_file_id` (int, **requis**) : ID du fichier EPW.

---

## Consultation des résultats

Tous ces endpoints acceptent en query params optionnels pour filtrer :

- `simulation_name` (string, optionnel) : Nom de la simulation.  
- `date` (string, optionnel) : Date au format `M/D` ou `MM/DD` (ex : `10/25`).  
- `hour` (string, optionnel) : Heure au format `H` ou `HH` (ex : `14`).

---

### 8. Lister les zones  
`GET /zones/`

- Pas de paramètres.

---

### 9. Somme de l’énergie totale (toutes zones, postes)  
`GET /sum_all_energy/`

- **Query params (optionnels) :**  
  - `simulation_name` (string)  
  - `date` (string)  
  - `hour` (string)

---

### 10. Somme d’énergie pour une zone  
`GET /sum_room_energy/`

- **Query params :**  
  - `room` (string, **requis**) : Nom de la zone.  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

### 11. Somme d’énergie par poste  
`GET /sum_by_poste/`

- **Query params :**  
  - `poste` (string, **requis**) : Ex : `"Heating"`, `"Cooling"`, `"Electricity"`.  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

### 12. Somme d’énergie par zone et poste  
`GET /sum_by_room_and_poste/`

- **Query params :**  
  - `room` (string, **requis**)  
  - `poste` (string, **requis**)  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

### 13. Valeurs PMV pour une zone  
`GET /pmv_by_room/`

- **Query params :**  
  - `room` (string, **requis**)  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

### 14. Températures pour une zone  
`GET /temperature_by_room/`

- **Query params :**  
  - `room` (string, **requis**)  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

### 15. Résumé énergétique d’une zone (ou toutes zones)  
`GET /room_summary/`

- **Query params :**  
  - `room` (string, **optionnel**)  
  - `simulation_name` (string, optionnel)  
  - `date` (string, optionnel)  
  - `hour` (string, optionnel)

---

## Gestion des objets IDF

### 16. Récupérer les objets IDF d’un fichier  
`GET /get_idf_objects/{file_id}`

- **Paramètres URL :**  
  - `file_id` (int, **requis**)

---

### 17. Modifier un champ d’un objet IDF  
`POST /update_idf_field/{file_id}`

- **Paramètres URL :**  
  - `file_id` (int, **requis**)

- **Body JSON :**  
  - `object_type` (string, **requis**) : Type d’objet IDF, ex : `"ZONE"`.  
  - `object_index` (int, **requis**) : Index de l’objet dans la liste.  
  - `field_name` (string, **requis**) : Nom du champ à modifier.  
  - `new_value` (string, **requis**) : Nouvelle valeur du champ.

---

## Divers

### 18. Lister les simulations existantes  
`GET /simulations`

- Pas de paramètres.

---

## Notes

- Les paramètres optionnels `date` et `hour` permettent de filtrer les résultats.  
- L’énergie est renvoyée en Joules, sauf indication explicite en kWh.  
- En cas d’erreur, les réponses HTTP peuvent être 404 (non trouvé) ou 500 (erreur serveur).
