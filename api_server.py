from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import sessionmaker, relationship, Session, declarative_base
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
from sqlalchemy.dialects.mysql import LONGTEXT

# Ajouter le chemin vers eppy
pathnameto_eppy = 'C:\\Users\\Cesi\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\eppy'
sys.path.append(pathnameto_eppy)

from eppy.modeleditor import IDF

# --- Configuration SQLAlchemy ---
DATABASE_URL = "mysql+mysqldb://root:root@localhost/energyplus"  # Adaptez avec vos identifiants

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modèles SQLAlchemy ---
class InputFile(Base):
    __tablename__ = "input_files"
    id = Column(Integer, primary_key=True, index=True)
    file_type = Column(String(50), index=True)
    filename = Column(String(255))
    content_b64 = Column(LONGTEXT)
    upload_date = Column(DateTime, default=datetime.now)
    version = Column(Integer, default=1)
    previous_version_id = Column(Integer, ForeignKey("input_files.id"), nullable=True)

class Simulation(Base):
    __tablename__ = "simulations"
    id = Column(Integer, primary_key=True, index=True)
    simulation_name = Column(String(100), unique=True, index=True)
    idf_file_id = Column(Integer, ForeignKey("input_files.id"))
    epw_file_id = Column(Integer, ForeignKey("input_files.id"))
    timestamp = Column(DateTime, default=datetime.now)

    idf_file = relationship("InputFile", foreign_keys=[idf_file_id])
    epw_file = relationship("InputFile", foreign_keys=[epw_file_id])

class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)

class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, ForeignKey("simulations.id"))
    zone_id = Column(Integer, ForeignKey("zones.id"))
    datetime = Column(String(100))
    variable = Column(String(100))
    value = Column(Float)

# Création des tables dans la base de données
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dépendance pour la session de base de données ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#----------------------------#
#----- Interface web --------#
#----------------------------#

@app.get("/input_file/by_id/{file_id}")
def get_input_file_by_id(file_id: int, db: Session = Depends(get_db)):
    file_doc = db.query(InputFile).filter(InputFile.id == file_id).first()
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    content = base64.b64decode(file_doc.content_b64).decode('utf-8')
    return {
        "_id": str(file_doc.id),
        "file_type": file_doc.file_type,
        "filename": file_doc.filename,
        "content": content
    }

@app.get("/input_file/by_simulation/{simulation_name}")
def get_input_files_by_simulation(simulation_name: str, db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.simulation_name == simulation_name).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")

    def extract_content(file_doc):
        if not file_doc:
            return None
        content = base64.b64decode(file_doc.content_b64).decode('utf-8')
        return {
            "_id": str(file_doc.id),
            "filename": file_doc.filename,
            "content": content
        }
    return {
        "idf": extract_content(sim.idf_file),
        "epw": extract_content(sim.epw_file)
    }

@app.post("/input_file/update/{file_id}")
def update_input_file(file_id: int, content: str = Body(...), db: Session = Depends(get_db)):
    file_doc = db.query(InputFile).filter(InputFile.id == file_id).first()
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    file_doc.content_b64 = content_b64
    db.commit()
    return {"status": "ok"}

@app.get("/input_files/")
def list_input_files(file_type: str = Query(...), db: Session = Depends(get_db)):
    files = db.query(InputFile).filter(InputFile.file_type == file_type).all()
    return [
        {
            "_id": str(f.id),
            "filename": f.filename,
            "upload_date": f.upload_date,
            "version": f.version
        }
        for f in files
    ]

@app.post("/input_file/save_new_version/{file_id}")
def save_new_version(file_id: int, content: str = Body(...), filename: Optional[str] = Body(None), db: Session = Depends(get_db)):
    orig = db.query(InputFile).filter(InputFile.id == file_id).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Fichier d'origine non trouvé")

    base_filename = filename if filename else orig.filename
    version_count = db.query(InputFile).filter(InputFile.filename == base_filename).count()
    
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    
    new_file = InputFile(
        file_type=orig.file_type,
        filename=base_filename,
        content_b64=content_b64,
        upload_date=datetime.now(),
        previous_version_id=orig.id,
        version=version_count + 1
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return {"status": "ok", "new_id": str(new_file.id)}

@app.post("/input_file/upload/")
async def upload_input_file(file: UploadFile = File(...), file_type: str = Query(...), db: Session = Depends(get_db)):
    content_bytes = await file.read()
    content_b64 = base64.b64encode(content_bytes).decode('ascii')
    
    new_file = InputFile(
        file_type=file_type,
        filename=file.filename,
        content_b64=content_b64,
        upload_date=datetime.now(),
        version=1
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return {"status": "ok", "new_id": str(new_file.id)}

@app.post("/run_simulation/")
def run_simulation(idf_file_id: int = Body(...), epw_file_id: int = Body(...), db: Session = Depends(get_db)):
    idf_doc = db.query(InputFile).filter(InputFile.id == idf_file_id).first()
    epw_doc = db.query(InputFile).filter(InputFile.id == epw_file_id).first()
    if not idf_doc or not epw_doc:
        raise HTTPException(status_code=404, detail="Fichier IDF ou EPW non trouvé")

    with tempfile.TemporaryDirectory() as tmpdir:
        idf_path = os.path.join(tmpdir, idf_doc.filename)
        epw_path = os.path.join(tmpdir, epw_doc.filename)
        
        idf_bytes = base64.b64decode(idf_doc.content_b64)
        with open(idf_path, "wb") as f:
            f.write(idf_bytes)
        
        epw_bytes = base64.b64decode(epw_doc.content_b64)
        with open(epw_path, "wb") as f:
            f.write(epw_bytes)

        try:
            iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
            IDF.setiddname(iddfile)
            idf = IDF(idf_path, epw_path)
            
            idfversion = idf.idfobjects['version'][0].Version_Identifier.split('.')
            idfversion.extend([0] * (3 - len(idfversion)))
            fname = idf.idfname
            options = {
                'output_prefix': os.path.basename(fname).split('.')[0],
                'output_suffix': 'C',
                'output_directory': os.path.dirname(fname),
                'readvars': True,
                'expandobjects': True
            }
            
            idf.encoding = "utf-8"
            idf.run(**options)
            
            csv_dir = os.path.dirname(fname)
            csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
            if csv_files:
                csv_output_path = os.path.join(csv_dir, csv_files[0])
                
                base_name = os.path.basename(idf_path).replace('.idf', '')
                
                existing_sim_count = db.query(Simulation).filter(Simulation.simulation_name.like(f"{base_name}_%")).count()
                simulation_name = f"{base_name}_{existing_sim_count + 1}"
                
                res_dir = r"C:\Users\Cesi\Desktop\IR_THEO_BOSSET\Git\res"
                os.makedirs(res_dir, exist_ok=True)
                dest_csv_path = os.path.join(res_dir, f"{simulation_name}.csv")
                shutil.copy2(csv_output_path, dest_csv_path)

                df = pd.read_csv(csv_output_path)
                
                # Créer la simulation dans la base de données
                new_sim = Simulation(
                    simulation_name=simulation_name,
                    idf_file_id=idf_file_id,
                    epw_file_id=epw_file_id,
                    timestamp=datetime.now()
                )
                db.add(new_sim)
                db.commit()
                db.refresh(new_sim)

                store_results_by_zone(df, new_sim.id, db)

                return {
                    "status": "success",
                    "simulation_name": simulation_name,
                    "message": f"Simulation '{simulation_name}' terminée. CSV copié dans {dest_csv_path}",
                    "results_count": len(df),
                    "stdout": f"Simulation '{simulation_name}' terminée avec succès.",
                    "stderr": ""
                }
            else:
                return {"status": "error", "message": "Aucun fichier CSV de résultat trouvé."}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

#----------------------------#
#------Jumeau Numérique------#
#----------------------------#
def get_latest_simulation_name_if_none(simulation_name: Optional[str], db: Session) -> str:
    if simulation_name:
        return simulation_name
    latest_simulation = db.query(Simulation).order_by(Simulation.timestamp.desc()).first()
    if not latest_simulation:
        raise HTTPException(status_code=404, detail="Aucune simulation trouvée.")
    return latest_simulation.simulation_name

def normalize_date_str(s):
    # Enlève les espaces, zéros non significatifs, etc.
    s = s.strip()
    s = re.sub(r' +', ' ', s)  # remplace plusieurs espaces par un seul
    if ' ' in s:
        date_part = s.split(' ')[0]
    else:
        date_part = s
    # Enlève les zéros non significatifs
    parts = date_part.split('/')
    parts = [str(int(p)) for p in parts if p.isdigit()]
    return '/'.join(parts)

def normalize_hour_str(s):
    s = s.strip()
    if ':' in s:
        hour_part = s.split(':')[0]
    else:
        hour_part = s
    return str(int(hour_part))  # enlève zéro devant

@app.get("/zones/")
def get_zones(db: Session = Depends(get_db)):
    zones = db.query(Zone).all()
    return [{"id": z.id, "name": z.name} for z in zones]

@app.get("/sum_all_energy/")
def sum_all_energy(
    simulation_name: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")

    query = db.query(func.sum(Result.value)).filter(Result.variable == 'Electricity')
    query = query.filter(Result.simulation_id == sim.id)

    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))
        
    total = query.scalar() or 0.0
    return {
        "simulation_name": sim_name, "date": date, "hour": hour,
        "total_energy_all_fields": total, "total_energy_all_fields_kwh": total/3600000
    }

@app.get("/sum_room_energy/")
def sum_room_energy(
    simulation_name: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    room: str = Query(...),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")
    
    zone = db.query(Zone).filter(Zone.name == room).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone non trouvée")

    query = db.query(func.sum(Result.value)).filter(Result.variable == 'Electricity')
    query = query.filter(Result.simulation_id == sim.id, Result.zone_id == zone.id)

    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))
    
    total = query.scalar() or 0.0
    return {
        "simulation_name": sim_name, "date": date, "hour": hour, "room": room,
        "total_energy_room": total, "total_energy_room_kwh": total/3600000
    }

@app.get("/sum_by_poste/")
def sum_by_poste(
    simulation_name: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    poste: str = Query(...),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation non trouvée")

    query = db.query(func.sum(Result.value)).filter(Result.variable == poste)
    query = query.filter(Result.simulation_id == sim.id)
    
    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))

    total = query.scalar() or 0.0
    return {
        "simulation_name": sim_name, "date": date, "hour": hour, "poste": poste,
        "total_energy_poste": total, "total_energy_poste_kwh": total/3600000
    }

@app.get("/sum_by_room_and_poste/")
def sum_by_room_and_poste(
    simulation_name: Optional[str] = Query(None),
    poste: str = Query(...),
    room: str = Query(...),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim: raise HTTPException(status_code=404, detail="Simulation non trouvée")
    zone = db.query(Zone).filter(Zone.name == room).first()
    if not zone: raise HTTPException(status_code=404, detail="Zone non trouvée")

    query = db.query(func.sum(Result.value)).filter(Result.simulation_id == sim.id, Result.zone_id == zone.id)
    query = query.filter(Result.variable == poste)
    
    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))

    total = query.scalar() or 0.0
    return {
        "simulation_name": sim_name, "poste": poste, "room": room, "date": date, "hour": hour,
        "total_energy_room_poste": total, "total_energy_room_poste_kwh": total/3600000
    }

@app.get("/pmv_by_room/")
def pmv_by_room(
    simulation_name: Optional[str] = Query(None),
    room: str = Query(...),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim: raise HTTPException(status_code=404, detail="Simulation non trouvée")
    zone = db.query(Zone).filter(Zone.name == room).first()
    if not zone: raise HTTPException(status_code=404, detail="Zone non trouvée")

    query = db.query(Result.value).filter(Result.simulation_id == sim.id, Result.zone_id == zone.id)
    query = query.filter(Result.variable == 'PMV')

    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))

    pmv_values = [v[0] for v in query.all()]
    return {"simulation_name": sim_name, "room": room, "date": date, "hour": hour, "pmv_values": pmv_values}

@app.get("/temperature_by_room/")
def temperature_by_room(
    simulation_name: Optional[str] = Query(None),
    room: str = Query(...),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim: raise HTTPException(status_code=404, detail="Simulation non trouvée")
    zone = db.query(Zone).filter(Zone.name == room).first()
    if not zone: raise HTTPException(status_code=404, detail="Zone non trouvée")

    query = db.query(Result.value).filter(Result.simulation_id == sim.id, Result.zone_id == zone.id)
    query = query.filter(Result.variable == 'Thermostat')

    normalized_date = normalize_date_str(date)
    if normalized_date:
        query = query.filter(Result.datetime.like(f"{normalized_date}%"))
    if hour:
        query = query.filter(Result.datetime.like(f"%{hour.zfill(2)}:%"))

    temperature_values = [v[0] for v in query.all()]
    return {"simulation_name": sim_name, "room": room, "date": date, "hour": hour, "temperature_values": temperature_values}

KEYWORDS = [
    "Humidity", "Thermostat", "Fans", "Heating", "EnergyTransfer",
    "Cooling", "InteriorLights", "InteriorEquipment", "Electricity", "PMV"
]

def extract_zone_and_type(col_name):
    # Exemple de colonne : "ETAGE:NOBEL:Zone Air Relative Humidity [%](Hourly)"
    for keyword in KEYWORDS:
        if keyword.lower() in col_name.lower():
            # Recherche du nom de la zone (ex: NOBEL)
            match = re.search(r":([A-Z0-9_]+):", col_name)
            zone = match.group(1) if match else None
            return zone, keyword
    return None, None

def store_results_by_zone(df: pd.DataFrame, simulation_id: int, db: Session):
    # Récupérer toutes les zones de la base
    zones = db.query(Zone).all()
    zone_map = {z.name.upper(): z.id for z in zones}

    for col in df.columns:
        if col == "Date/Time":
            continue

        # Chercher la zone dans le nom de colonne
        zone_found = None
        for zone_name in zone_map:
            if zone_name in col.upper():
                zone_found = zone_name
                break
        if not zone_found:
            continue

        # Chercher le type de donnée dans le nom de colonne
        data_type = None
        for keyword in KEYWORDS:
            if keyword.lower() in col.lower():
                data_type = keyword
                break
        if not data_type:
            continue

        zone_id = zone_map[zone_found]
        for idx, value in enumerate(df[col]):
            datetime_val = df["Date/Time"].iloc[idx]
            result = Result(
                simulation_id=simulation_id,
                zone_id=zone_id,
                datetime=datetime_val,
                variable=data_type,
                value=value
            )
            db.add(result)
    db.commit()

def build_like_pattern(date, hour):
    # Construit un pattern LIKE SQL pour le champ datetime
    # date attendu au format M/D ou MM/DD
    if not date:
        return None
    date_parts = date.strip().split('/')
    if len(date_parts) == 2:
        month = f"{int(date_parts[0]):02d}"
        day = f"{int(date_parts[1]):02d}"
        date_sql = f"{month}/{day}"
    else:
        date_sql = date.strip()
    if hour:
        hour_sql = f"{int(hour):02d}"
        return f"%{date_sql}%{hour_sql}:%"
    else:
        return f"%{date_sql}%"

@app.get("/room_summary/")
def get_room_summary(
    simulation_name: Optional[str] = Query(None),
    room: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    hour: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_name = get_latest_simulation_name_if_none(simulation_name, db)
    sim = db.query(Simulation).filter(Simulation.simulation_name == sim_name).first()
    if not sim: raise HTTPException(status_code=404, detail="Simulation non trouvée")

    query = db.query(Result.variable, Result.value, Result.datetime)
    query = query.filter(Result.simulation_id == sim.id)

    if room:
        zone = db.query(Zone).filter(Zone.name == room).first()
        if not zone: raise HTTPException(status_code=404, detail="Zone non trouvée")
        query = query.filter(Result.zone_id == zone.id)

    # Filtrage SQL performant sur la date et l'heure
    if date:
        like_pattern = build_like_pattern(date, hour)
        if like_pattern:
            query = query.filter(Result.datetime.like(like_pattern))

    results = query.all()

    total_energy = 0.0; energy_equipment = 0.0; energy_lights = 0.0
    pmv_values = []; temperature_values = []; humidity_values = []
    total_energy_transfer = 0.0; total_heating_transfer = 0.0; total_cooling_transfer = 0.0
    fans_electricity = 0.0

    for key, value, _ in results:
        key_lower = key.lower()
        if key_lower.startswith("electricity"): total_energy += value
        if key_lower.startswith("energytransfer"): total_energy_transfer += value
        if key_lower.startswith("heating"): total_heating_transfer += value
        if key_lower.startswith("cooling"): total_cooling_transfer += value
        if "fans" in key_lower: fans_electricity += value
        if "interiorequipment" in key_lower: energy_equipment += value
        if "interiorlights" in key_lower: energy_lights += value
        if "pmv" in key_lower: pmv_values.append(value)
        if "thermostat" in key_lower: temperature_values.append(value)
        if "humidity" in key_lower: humidity_values.append(value)
    
    def calculate_final_value(values):
        if not values: return None
        return np.mean(values)

    return {
        "simulation_name": sim_name, "room": room if room else "ALL", "date": date, "hour": hour,
        "data": {
            "total_energy_kwh": total_energy / 3600000,
            "detailed_energy_kwh": { "equipment": energy_equipment / 3600000, "lights": energy_lights / 3600000 },
            "total_energy_transfer_kwh": total_energy_transfer / 3600000,
            "detailed_energy_transfer": {
                "total_heating_transfer_kwh": total_heating_transfer / 3600000,
                "total_cooling_transfer_kwh": total_cooling_transfer / 3600000,
            },
            "fans_electricity_kwh": fans_electricity / 3600000,
            "total_energy_consommation": (total_energy + total_energy_transfer + fans_electricity) / 3600000,
            "pmv_values": calculate_final_value(pmv_values),
            "temperature_values": calculate_final_value(temperature_values),
            "humidity_values": calculate_final_value(humidity_values),
        },
    }

@app.get("/get_idf_objects/{file_id}")
def get_idf_objects(file_id: int, db: Session = Depends(get_db)):
    file_doc = db.query(InputFile).filter(InputFile.id == file_id).first()
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".idf", encoding='utf-8') as tmp:
            content = base64.b64decode(file_doc.content_b64).decode('utf-8')
            tmp.write(content)
            tmp_path = tmp.name

        iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
        IDF.setiddname(iddfile)
        idf = IDF(tmp_path)
        
        structured_idf = {}
        for obj_type in idf.idfobjects:
            obj_type_upper = obj_type.upper()
            if not idf.idfobjects[obj_type]: continue
            
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
def update_idf_field(file_id: int, update_data: IDFFieldUpdate, db: Session = Depends(get_db)):
    file_doc = db.query(InputFile).filter(InputFile.id == file_id).first()
    if not file_doc:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".idf", encoding='utf-8') as tmp:
            content = base64.b64decode(file_doc.content_b64).decode('utf-8')
            tmp.write(content)
            tmp_path = tmp.name

        iddfile = "C:\\EnergyPlusV9-4-0\\Energy+.idd"
        IDF.setiddname(iddfile)
        idf = IDF(tmp_path)
        
        objects_of_type = idf.idfobjects.get(update_data.object_type.upper())
        if not objects_of_type or update_data.object_index >= len(objects_of_type):
            raise HTTPException(status_code=404, detail="Objet IDF non trouvé")

        target_object = objects_of_type[update_data.object_index]
        setattr(target_object, update_data.field_name, update_data.new_value)
        idf.save()

        with open(tmp_path, "r", encoding='utf-8') as f:
            new_content = f.read()

        new_content_b64 = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        file_doc.content_b64 = new_content_b64
        db.commit()

        return {"status": "success", "new_content": new_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour de l'IDF: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 