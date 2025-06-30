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
import re
from pydantic import BaseModel
import numpy as np

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
                
                # Nommage de la simulation avec version du fichier IDF
                base_name = os.path.basename(idf_path).replace('.idf', '')
                # Chercher le nombre de simulations existantes avec ce base_name
                existing_sim_names = simulation_runs.distinct("simulation_name", {"simulation_name": {"$regex": f"^{re.escape(base_name)}_\\d+$"}})
                existing_count = len(existing_sim_names)
                simulation_name = f"{base_name}_{existing_count + 1}"
                
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

# http://localhost:8000/room_summary/?simulation_name=NR3_V07-24_1&room=TESLA&hour=16&date=06/26
@app.get("/room_summary/")
def get_room_summary(
    simulation_name: Optional[str] = Query(None, description="Nom de la simulation. Si non fourni, la dernière est utilisée."),
    room: Optional[str] = Query(None, description="Nom de la salle, ex: TESLA. Si non fourni, somme sur toutes les rooms."),
    date: Optional[str] = Query(None, description="Date au format 'JJ/MM' (optionnel)."),
    hour: Optional[str] = Query(None, description="Heure au format HH (ex: '01', '14').")
):
    """
    Retourne un résumé complet (énergie, PMV, température, humidité) pour une salle donnée ou la somme sur toutes les salles si non spécifiée.
    """
    sim_name = get_latest_simulation_name_if_none(simulation_name)
    normalized_date = normalize_date(date)
    if room:
        docs = [simulation_runs.find_one({"simulation_name": sim_name, "zone": room})]
    else:
        docs = list(simulation_runs.find({"simulation_name": sim_name}))
    if not docs or docs[0] is None:
        raise HTTPException(status_code=404, detail="Simulation ou zone non trouvée")

    total_energy = 0.0
    energy_equipment = 0.0
    energy_lights = 0.0
    pmv_values = []
    temperature_values = []
    humidity_values = []
    total_energy_transfer = 0.0
    total_heating_transfer = 0.0
    total_cooling_transfer = 0.0
    fans_electricity = 0.0

    for doc in docs:
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
                # Somme de l'énergie transférée (EnergyTransfer:Zone)
                if key.strip().lower().startswith("energytransfer:zone"):
                    try:
                        total_energy_transfer += float(value)
                    except Exception:
                        pass
                # Somme du heating transfer
                if key.strip().lower().startswith("heating:energytransfer:zone"):
                    try:
                        total_heating_transfer += float(value)
                    except Exception:
                        pass
                # Somme du cooling transfer
                if key.strip().lower().startswith("cooling:energytransfer:zone"):
                    try:
                        total_cooling_transfer += float(value)
                    except Exception:
                        pass
                # Somme de la consommation des ventilateurs (Fans:Electricity)
                if "fans:electricity" in key_lower:
                    try:
                        fans_electricity += float(value)
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
    elif len(temperature_values) > 1:
        final_temperature = float(np.mean(temperature_values))
    elif len(temperature_values) == 0:
        final_temperature = None

    final_pmv = pmv_values
    if len(pmv_values) == 1:
        final_pmv = pmv_values[0]
    elif len(pmv_values) > 1:
        final_pmv = float(np.mean(pmv_values))
    elif len(pmv_values) == 0:
        final_pmv = None

    final_humidity = humidity_values
    if len(humidity_values) == 1:
        final_humidity = humidity_values[0]
    elif len(humidity_values) > 1:
        final_humidity = float(np.mean(humidity_values))
    elif len(humidity_values) == 0:
        final_humidity = None

    return {
        "simulation_name": sim_name,
        "room": room if room else "ALL",
        "date": date,
        "hour": hour,
        #TOTAL_GLOBAL = total energy(light+equipment) + total energy transfer(cooling+heating) + fans
        "data": {

            "total_energy_kwh": total_energy / 3600000,
            "detailed_energy_kwh": {
                "equipment": energy_equipment / 3600000,
                "lights": energy_lights / 3600000
            },

            "total_energy_transfer_kwh": total_energy_transfer / 3600000,
            "detailed_energy_transfer": {
                "total_heating_transfer_kwh": total_heating_transfer / 3600000,
                "total_cooling_transfer_kwh": total_cooling_transfer / 3600000,
            },

            "fans_electricity_kwh": fans_electricity / 3600000,

            "total_energy_consommation": (total_energy + total_energy_transfer + fans_electricity) / 3600000,


            "pmv_values": final_pmv,
            "temperature_values": final_temperature,
            "humidity_values": final_humidity,
            
        },
    }

@app.get("/get_idf_objects/{file_id}")
def get_idf_objects(file_id: str):
    """
    Parse un fichier IDF et retourne sa structure en JSON.
    Utilise eppy pour une analyse robuste.
    """
    try:
        file_doc = input_files.find_one({"_id": ObjectId(file_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID de fichier invalide")
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Utiliser un fichier temporaire pour eppy
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".idf", encoding='utf-8') as tmp:
            if "content_b64" in file_doc:
                content = base64.b64decode(file_doc["content_b64"]).decode('utf-8')
            elif "content" in file_doc:
                content = file_doc["content"]
            else:
                raise HTTPException(status_code=404, detail="Contenu du fichier introuvable")
            tmp.write(content)
            tmp_path = tmp.name

        iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
        IDF.setiddname(iddfile)
        idf = IDF(tmp_path)
        
        structured_idf = {}
        for obj_type in idf.idfobjects:
            obj_type_upper = obj_type.upper()
            if not idf.idfobjects[obj_type]:
                continue
            
            structured_idf[obj_type_upper] = []
            for instance in idf.idfobjects[obj_type]:
                fields = {fn: fv for fn, fv in zip(instance.fieldnames, instance.fieldvalues)}
                structured_idf[obj_type_upper].append({"fields": fields})

        return structured_idf
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du parsing IDF avec eppy: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

class IDFFieldUpdate(BaseModel):
    object_type: str
    object_index: int
    field_name: str
    new_value: str

@app.post("/update_idf_field/{file_id}")
def update_idf_field(file_id: str, update_data: IDFFieldUpdate):
    """Met à jour un champ spécifique dans un fichier IDF et retourne le nouveau contenu."""
    try:
        file_doc = input_files.find_one({"_id": ObjectId(file_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID de fichier invalide")
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".idf", encoding='utf-8') as tmp:
            if "content_b64" in file_doc:
                content = base64.b64decode(file_doc["content_b64"]).decode('utf-8')
            else:
                content = file_doc["content"]
            tmp.write(content)
            tmp_path = tmp.name

        iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
        IDF.setiddname(iddfile)
        idf = IDF(tmp_path)
        
        # Accéder à l'objet et mettre à jour le champ
        objects_of_type = idf.idfobjects.get(update_data.object_type.upper())
        if not objects_of_type or update_data.object_index >= len(objects_of_type):
            raise HTTPException(status_code=404, detail="Objet IDF non trouvé (type ou index invalide)")

        target_object = objects_of_type[update_data.object_index]
        
        if not target_object:
            raise HTTPException(status_code=404, detail="Objet IDF non trouvé")
        
        setattr(target_object, update_data.field_name, update_data.new_value)
        
        idf.save() # Sauvegarde les modifications dans le fichier temporaire

        # Lire le nouveau contenu
        with open(tmp_path, "r", encoding='utf-8') as f:
            new_content = f.read()

        # Mettre à jour dans MongoDB et retourner
        new_content_b64 = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        input_files.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"content_b64": new_content_b64}}
        )

        return {"status": "success", "new_content": new_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour de l'IDF: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 