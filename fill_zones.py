from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String

# Configuration de la connexion (adapte si besoin)
DATABASE_URL = "mysql+mysqldb://root:root@localhost/energyplus"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)

zones_to_insert = [
    "BUREAUETAGE",
    "HALLRDC",
    "LOCALSERVEURS",
    "LOCALTECH",
    "LUMIERE",
    "NOBEL",
    "TESLA",
    "TURING"
]

def fill_zones():
    db = SessionLocal()
    try:
        for zone_name in zones_to_insert:
            # Vérifie si la zone existe déjà
            if not db.query(Zone).filter(Zone.name == zone_name).first():
                db.add(Zone(name=zone_name))
        db.commit()
        print("Zones insérées avec succès.")
    finally:
        db.close()

if __name__ == "__main__":
    fill_zones()