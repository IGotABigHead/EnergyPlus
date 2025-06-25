from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from typing import List, Dict, Optional
import tempfile
import subprocess
import os
import sys
import pandas as pd
import base64
import shutil

# Ajouter le chemin vers eppy
pathnameto_eppy = 'C:\\Users\\Cesi\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\eppy'
sys.path.append(pathnameto_eppy)

from eppy.modeleditor import IDF

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # autorise ton front Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connexion à MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['EnergyPlus']
simulation_runs = db['simulation_runs']
input_files = db['input_files']

#----------------------------#
#----- route de base --------#
#----------------------------#

@app.get("/")
def read_root():
    return {"message": "EnergyPlus Data API"}

@app.get("/simulations")
def get_simulations():
    """Récupère la liste de toutes les simulations disponibles"""
    simulations = simulation_runs.distinct("simulation_name")
    return {"simulations": simulations}

@app.get("/data/{simulation_name}")
def get_simulation_data(simulation_name: str):
    """Récupère toutes les données d'une simulation spécifique"""
    doc = simulation_runs.find_one({"simulation_name": simulation_name})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")
    return {"data": doc.get("results", [])}


#----------------------------#
#----- Interface web --------#
#----------------------------#

@app.get("/input_file/by_id/{file_id}")
def get_input_file_by_id(file_id: str):
    try:
        file_doc = input_files.find_one({"_id": ObjectId(file_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalide")
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    # Correction rétrocompatibilité
    if "content" in file_doc:
        content = file_doc["content"]
    elif "content_b64" in file_doc:
        content = base64.b64decode(file_doc["content_b64"]).decode('utf-8')
    else:
        content = None
    return {
        "_id": str(file_doc["_id"]),
        "file_type": file_doc["file_type"],
        "filename": file_doc["filename"],
        "content": content
    }


@app.get("/input_file/by_simulation/{simulation_name}")
def get_input_files_by_simulation(simulation_name: str):
    doc = simulation_runs.find_one({"simulation_name": simulation_name})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")
    idf_file = input_files.find_one({"_id": doc["idf_file_id"]})
    epw_file = input_files.find_one({"_id": doc["epw_file_id"]})
    def extract_content(file_doc):
        if not file_doc:
            return None
        if "content" in file_doc:
            content = file_doc["content"]
        elif "content_b64" in file_doc:
            content = base64.b64decode(file_doc["content_b64"]).decode('utf-8')
        else:
            content = None
        return {
            "_id": str(file_doc["_id"]),
            "filename": file_doc["filename"],
            "content": content
        }
    return {
        "idf": extract_content(idf_file),
        "epw": extract_content(epw_file)
    }


@app.post("/input_file/update/{file_id}")
def update_input_file(file_id: str, content: str = Body(...)):
    try:
        result = input_files.update_one({"_id": ObjectId(file_id)}, {"$set": {"content": content}})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalide")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    return {"status": "ok"}


@app.get("/input_files/")
def list_input_files(file_type: str = Query(...)):
    files = list(input_files.find({"file_type": file_type}))
    return [
        {
            "_id": str(f["_id"]),
            "filename": f["filename"],
            "upload_date": f.get("upload_date"),
            "version": f.get("version", 1)
        }
        for f in files
    ]

@app.post("/input_file/save_new_version/{file_id}")
def save_new_version(file_id: str, content: str = Body(...), filename: Optional[str] = Body(None)):
    orig = input_files.find_one({"_id": ObjectId(file_id)})
    if not orig:
        raise HTTPException(status_code=404, detail="Fichier d'origine non trouvé")
    base_filename = filename if filename else orig["filename"]
    version_count = input_files.count_documents({"filename": base_filename})
    # Encodage base64 systématique
    try:
        # Si le contenu est déjà du base64 (cas rare), on ne le re-encode pas
        base64.b64decode(content)
        content_b64 = content
    except Exception:
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    new_doc = {
        "file_type": orig["file_type"],
        "filename": base_filename,
        "content_b64": content_b64,
        "upload_date": datetime.now(),
        "previous_version_id": str(orig["_id"]),
        "version": version_count + 1
    }
    result = input_files.insert_one(new_doc)
    return {"status": "ok", "new_id": str(result.inserted_id)}

@app.post("/input_file/upload/")
async def upload_input_file(file: UploadFile = File(...), file_type: str = Query(...)):
    content_bytes = await file.read()
    content_b64 = base64.b64encode(content_bytes).decode('ascii')
    doc = {
        "file_type": file_type,
        "filename": file.filename,
        "content_b64": content_b64,
        "upload_date": datetime.now(),
        "version": 1
    }
    result = input_files.insert_one(doc)
    return {"status": "ok", "new_id": str(result.inserted_id)}


@app.post("/run_simulation/")
def run_simulation(idf_file_id: str = Body(...), epw_file_id: str = Body(...)):
    # Récupérer les fichiers depuis MongoDB
    idf_doc = input_files.find_one({"_id": ObjectId(idf_file_id)})
    epw_doc = input_files.find_one({"_id": ObjectId(epw_file_id)})
    if not idf_doc or not epw_doc:
        raise HTTPException(status_code=404, detail="Fichier IDF ou EPW non trouvé")

    # Créer des fichiers temporaires
    with tempfile.TemporaryDirectory() as tmpdir:
        idf_path = os.path.join(tmpdir, idf_doc["filename"])
        epw_path = os.path.join(tmpdir, epw_doc["filename"])
        
        # Écrire les fichiers temporaires
        # IDF
        if "content_b64" in idf_doc:
            idf_bytes = base64.b64decode(idf_doc["content_b64"])
            with open(idf_path, "wb") as f:
                f.write(idf_bytes)
        else:
            with open(idf_path, "w", encoding="utf-8") as f:
                f.write(idf_doc["content"])
        # EPW
        if "content_b64" in epw_doc:
            epw_bytes = base64.b64decode(epw_doc["content_b64"])
            with open(epw_path, "wb") as f:
                f.write(epw_bytes)
        else:
            with open(epw_path, "w", encoding="utf-8") as f:
                f.write(epw_doc["content"])

        try:
            # Configuration EnergyPlus
            iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
            IDF.setiddname(iddfile)
            
            # Créer l'objet IDF
            idf = IDF(idf_path, epw_path)
            
            # Options de simulation
            idfversion = idf.idfobjects['version'][0].Version_Identifier.split('.')
            idfversion.extend([0] * (3 - len(idfversion)))
            idfversionstr = '-'.join([str(item) for item in idfversion])
            fname = idf.idfname
            options = {
                'output_prefix': os.path.basename(fname).split('.')[0],
                'output_suffix': 'C',
                'output_directory': os.path.dirname(fname),
                'readvars': True,
                'expandobjects': True
            }
            
            # Lancer la simulation
            idf.encoding = "utf-8"
            idf.run(**options)
            
            # Chercher le premier fichier CSV généré dans le dossier temporaire
            csv_dir = os.path.dirname(fname)
            csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
            if csv_files:
                csv_output_path = os.path.join(csv_dir, csv_files[0])
                
                # Nommage de la simulation
                base_name = os.path.basename(idf_path).replace('.idf', '')
                existing_count = simulation_runs.count_documents({"simulation_name": {"$regex": f"^{base_name}(_[0-9]+)?$"}})
                existing_count_nb_salle = existing_count/8
                simulation_name = f"{base_name}_{existing_count_nb_salle + 1}"

                # Copie du fichier de résultats
                res_dir = r"C:\Users\Cesi\Desktop\IR_THEO_BOSSET\Solution\res"
                os.makedirs(res_dir, exist_ok=True)
                dest_csv_path = os.path.join(res_dir, f"{simulation_name}.csv")
                shutil.copy2(csv_output_path, dest_csv_path)

                # Lecture et stockage dans MongoDB
                df = pd.read_csv(csv_output_path)
                store_results_by_zone(df, simulation_name, ObjectId(idf_file_id), ObjectId(epw_file_id))

                return {
                    "status": "success",
                    "simulation_name": simulation_name,
                    "message": f"Simulation '{simulation_name}' terminée. CSV copié dans {dest_csv_path}",
                    "results_count": len(df),
                    "stdout": f"Simulation '{simulation_name}' terminée avec succès.",
                    "stderr": ""
                }
            else:
                return {
                    "status": "error",
                    "message": "Aucun fichier CSV trouvé dans le dossier temporaire après la simulation.",
                    "stdout": "",
                    "stderr": "Aucun fichier CSV trouvé dans le dossier temporaire après la simulation."
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "stdout": "",
                "stderr": str(e)
            }
        



#----------------------------#
#---route Jumeau Numérique---#
#----------------------------#

# Si aucun nom de simulation n'est fourni dans la requete, prends par défaut la simulation la plus récente
def get_latest_simulation_name_if_none(simulation_name: Optional[str]) -> str:
    """
    Retourne le nom de la simulation fournie, ou récupère la plus récente si non fournie.
    """
    if simulation_name:
        return simulation_name
    # Trouve la dernière simulation en se basant sur le timestamp
    latest_simulation = simulation_runs.find_one(sort=[("timestamp", -1)])
    if not latest_simulation:
        raise HTTPException(status_code=404, detail="Aucune simulation trouvée dans la base de données.")
    return latest_simulation["simulation_name"]

def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Normalise une date JJ/MM pour qu'elle ait toujours des zéros (ex: 1/8 -> 01/08)."""
    if not date_str:
        return None
    try:
        day, month = date_str.split('/')
        return f"{day.zfill(2)}/{month.zfill(2)}"
    except ValueError:
        return date_str # Retourne tel quel si le format est inattendu

#http://localhost:8000/sum_all_energy/?simulation_name=NR3_V07-24_1&date=01/08
@app.get("/sum_all_energy/")
def sum_all_energy(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Calcule la somme de toutes les consommations énergétiques pour une simulation et une date/heure données.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    docs = simulation_runs.find({"simulation_name": sim_name})
    total = 0.0
    normalized_date = normalize_date(date)
    for doc in docs:
        for row in doc.get("results", []):
            datetime_str = row.get("Date/Time", "").strip()
            if normalized_date and not datetime_str.startswith(normalized_date):
                continue
            if hour:
                time_parts = datetime_str.split("  ")
                if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                    continue

            for key, value in row.items():
                if key == "Date/Time":
                    continue
                key_lower = key.lower()
                if key.strip().lower().startswith("electricity:zone"):
                    try:
                        total += float(value)

                    except Exception:
                        continue
    return {
        "simulation_name": sim_name,
        "date": date,
        "hour": hour,
        "total_energy_all_fields": total,
        "total_energy_all_fields_kwh": total/3600000
    }

#http://localhost:8000/sum_room_energy/?simulation_name=NR3_V07-24_1&date=01/08&room=TESLA
@app.get("/sum_room_energy/")
def sum_room_energy(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14')."),
    room: str = Query(..., description="Nom de la salle, ex: TESLA")
):
    """
    Calcule la somme de la consommation énergétique pour une salle donnée, à une date donnée, dans une simulation.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    doc = simulation_runs.find_one({"simulation_name": sim_name, "zone": room})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")
    total = 0.0
    normalized_date = normalize_date(date)
    for row in doc.get("results", []):
        datetime_str = row.get("Date/Time", "").strip()
        if normalized_date and not datetime_str.startswith(normalized_date):
            continue
        if hour:
            time_parts = datetime_str.split("  ")
            if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                continue

        for key, value in row.items():
            if key == "Date/Time":
                continue
            key_lower = key.lower()
            if key.strip().lower().startswith("electricity:zone"):
                try:
                    total += float(value)
                except Exception:
                    continue
    return {
        "simulation_name": sim_name,
        "date": date,
        "hour": hour,
        "room": room,
        "total_energy_room": total,
        "total_energy_room_kwh": total/3600000
    }



#http://localhost:8000/sum_by_poste/?simulation_name=NR3_V07-24_1&poste=InteriorEquipment&date=01/08
@app.get("/sum_by_poste/")
def sum_by_poste(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14')."),
    poste: str = Query(None, description="Nom du poste (optionnel, filtre partiel sur le nom de la colonne)")
):
    """
    Calcule la consommation totale pour un poste donné (ex: 'Heating:Electricity') dans une simulation, éventuellement à une date donnée.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    docs = simulation_runs.find({"simulation_name": sim_name})
    total = 0.0
    normalized_date = normalize_date(date)
    for doc in docs:
        for row in doc.get("results", []):
            datetime_str = row.get("Date/Time", "").strip()
            if normalized_date and not datetime_str.startswith(normalized_date):
                continue
            if hour:
                time_parts = datetime_str.split("  ")
                if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                    continue
            
            for key, value in row.items():
                if key in ["Date/Time"]:
                    continue
                if poste and poste.lower() not in key.lower():
                    continue
                try:
                    total += float(value)
                except Exception:
                    continue
    return {
        "simulation_name": sim_name,
        "date": date,
        "hour": hour,
        "poste": poste,
        "total_energy_poste": total,
        "total_energy_poste_kwh": total/3600000
    }

#http://localhost:8000/sum_by_room_and_poste/?simulation_name=NR3_V07-24_1&poste=InteriorEquipment&room=TESLA&date=01/08&hour=16
@app.get("/sum_by_room_and_poste/")
def sum_by_room_and_poste(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    poste: str = Query(..., description="Nom du poste (colonne, ex: 'Heating:Electricity')"),
    room: str = Query(..., description="Nom de la salle, ex: TESLA"),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Calcule la consommation totale pour un poste et une salle donnés, à une date donnée, dans une simulation.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    doc = simulation_runs.find_one({"simulation_name": sim_name, "zone": room})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")
    total = 0.0
    normalized_date = normalize_date(date)
    for row in doc.get("results", []):
        datetime_str = row.get("Date/Time", "").strip()
        if normalized_date and not datetime_str.startswith(normalized_date):
            continue
        if hour:
            time_parts = datetime_str.split("  ")
            if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                continue
        
        for key, value in row.items():
            if poste.lower() in key.lower():
                try:
                    total += float(value)
                except Exception:
                    continue
    return {
        "simulation_name": sim_name,
        "poste": poste,
        "room": room,
        "date": date,
        "hour": hour,
        "total_energy_room_poste": total,
        "total_energy_room_poste_kwh": total/3600000
    }

# http://localhost:8000/pmv_by_room/?simulation_name=NR3_V07-24_1&room=TESLA&date=01/08&hour=10
@app.get("/pmv_by_room/")
def pmv_by_room(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    room: str = Query(..., description="Nom de la salle, ex: TESLA"),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Retourne la liste des valeurs PMV (Thermal Comfort Fanger Model PMV) pour une salle donnée, à une date donnée (optionnelle), dans une simulation.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    doc = simulation_runs.find_one({"simulation_name": sim_name, "zone": room})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")
    pmv_values = []
    normalized_date = normalize_date(date)
    for row in doc.get("results", []):
        datetime_str = row.get("Date/Time", "").strip()
        if normalized_date and not datetime_str.startswith(normalized_date):
            continue
        if hour:
            time_parts = datetime_str.split("  ")
            if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                continue
        
        for key, value in row.items():
            if "thermal comfort fanger model pmv" in key.lower():
                try:
                    pmv_values.append(float(value))
                except Exception:
                    continue
    return {
        "simulation_name": sim_name,
        "room": room,
        "date": date,
        "hour": hour,
        "pmv_values": pmv_values
    }

# http://localhost:8000/temperature_by_room/?simulation_name=NR3_V07-24_1&room=TESLA&date=01/08
@app.get("/temperature_by_room/")
def temperature_by_room(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    room: str = Query(..., description="Nom de la salle, ex: TESLA"),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM', ex: '01/01' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Retourne la liste des valeurs de température (Zone Thermostat Air Temperature) pour une salle donnée, à une date donnée (optionnelle), dans une simulation.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    doc = simulation_runs.find_one({"simulation_name": sim_name, "zone": room})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")
    temperature_values = []
    normalized_date = normalize_date(date)
    for row in doc.get("results", []):
        datetime_str = row.get("Date/Time", "").strip()
        if normalized_date and not datetime_str.startswith(normalized_date):
            continue
        if hour:
            time_parts = datetime_str.split("  ")
            if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                continue

        for key, value in row.items():
            if "Zone Thermostat Air Temperature" in key:
                try:
                    temperature_values.append(float(value))
                except Exception:
                    continue
    return {
        "simulation_name": sim_name,
        "room": room,
        "date": date,
        "hour": hour,
        "temperature_values": temperature_values
    }

def store_results_by_zone(df, simulation_name, idf_file_id, epw_file_id):
    """
    Partitionne le DataFrame par zone (d'après les colonnes) et insère un document MongoDB par zone.
    """
    # Liste des zones explicitement définie
    zones = ['BUREAUETAGE', 'HALLRDC', 'LOCALTECH', 'LOCALSERVEURS', 'LUMIERE', 'NOBEL', 'TESLA', 'TURING']
    for zone in zones:
        # Inclure toutes les colonnes dont le nom contient le nom de la zone (insensible à la casse)
        zone_cols = [col for col in df.columns if zone.lower() in col.lower()]
        cols_to_keep = ["Date/Time"] + zone_cols
        zone_df = df[cols_to_keep].copy()
        # Nettoyer les espaces dans la colonne Date/Time
        if "Date/Time" in zone_df.columns:
            zone_df["Date/Time"] = zone_df["Date/Time"].astype(str).str.strip()
        doc = {
            "simulation_name": simulation_name,
            "zone": zone,
            "idf_file_id": idf_file_id,
            "epw_file_id": epw_file_id,
            "timestamp": datetime.now(),
            "results": zone_df.to_dict('records')
        }
        simulation_runs.insert_one(doc)

# http://localhost:8000/room_summary/?room=TESLA
@app.get("/room_summary/")
def get_room_summary(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    room: str = Query(..., description="Nom de la salle, ex: TESLA"),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Retourne un résumé complet (énergie, PMV, température, humidité) pour une salle donnée.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    doc = simulation_runs.find_one({"simulation_name": sim_name, "zone": room})
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")

    total_energy = 0.0
    energy_equipment = 0.0
    energy_lights = 0.0
    pmv_values = []
    temperature_values = []
    humidity_values = []
    normalized_date = normalize_date(date)

    for row in doc.get("results", []):
        datetime_str = row.get("Date/Time", "").strip()
        
        # Filtre par date
        if normalized_date and not datetime_str.startswith(normalized_date):
            continue
            
        # Filtre par heure
        if hour:
            time_parts = datetime_str.split("  ")
            if len(time_parts) < 2 or not time_parts[1].startswith(f"{hour.zfill(2)}:"):
                continue

        # Extraction des données en une seule passe
        for key, value in row.items():
            if key == "Date/Time":
                continue
            
            key_lower = key.lower()

            # Somme de l'énergie
            if key.strip().lower().startswith("electricity:zone"):
                try:
                    total_energy += float(value)

                except Exception:
                    pass
            
            # Consommation détaillée
            if "interiorequipment" in key_lower:
                try:
                    energy_equipment += float(value)
                except Exception:
                    pass
            
            if "interiorlights" in key_lower:
                try:
                    energy_lights += float(value)
                except Exception:
                    pass

            # Liste des valeurs PMV
            if "thermal comfort fanger model pmv" in key_lower:
                try:
                    pmv_values.append(float(value))
                except Exception:
                    pass

            # Liste des valeurs de Température
            if "zone thermostat air temperature" in key_lower:
                try:
                    temperature_values.append(float(value))
                except Exception:
                    pass
            
            # Liste des valeurs d'Humidité
            if "air relative humidity" in key_lower:
                try:
                    humidity_values.append(float(value))
                except Exception:
                    pass

    final_temperature = temperature_values
    if len(temperature_values) == 1:
        final_temperature = temperature_values[0]

    final_pmv = pmv_values
    if len(pmv_values) == 1:
        final_pmv = pmv_values[0]

    final_humidity = humidity_values
    if len(humidity_values) == 1:
        final_humidity = humidity_values[0]

    return {
        "simulation_name": sim_name,
        "room": room,
        "date": date,
        "hour": hour,
        "data": {
            "total_energy_kwh": total_energy / 3600000,
            "detailed_energy_kwh": {
                "equipment": energy_equipment / 3600000,
                "lights": energy_lights / 3600000
            },
            "total_energy": total_energy ,
            "detailed_energy": {
                "equipment": energy_equipment ,
                "lights": energy_lights 
            },
            "pmv_values": final_pmv,
            "temperature_values": final_temperature,
            "humidity_values": final_humidity
        },
        
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 