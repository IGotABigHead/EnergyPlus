import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

interface IDFQuickEditorProps {
  fileId: string;
  onChange: (value: string) => void;
}

type IdfObjects = {
  [key: string]: { fields: { [key: string]: string | number } }[];
};

const IDFQuickEditor: React.FC<IDFQuickEditorProps> = ({ fileId, onChange }) => {
  const [objects, setObjects] = useState<IdfObjects>({});
  const [selectedType, setSelectedType] = useState<string>('');
  const [selectedInstance, setSelectedInstance] = useState<number>(0);
  const [selectedField, setSelectedField] = useState<string>('');
  const [newValue, setNewValue] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!fileId) return;
    const fetchObjects = async () => {
      setIsLoading(true);
      setError('');
      try {
        const response = await axios.get(`${API_BASE_URL}/get_idf_objects/${fileId}`);
        setObjects(response.data);
      } catch (err: any) {
        setError('Erreur de chargement des objets IDF: ' + (err.response?.data?.detail || err.message));
        setObjects({});
      } finally {
        setIsLoading(false);
      }
    };
    fetchObjects();
  }, [fileId]);

  const types = Object.keys(objects);
  const instances = selectedType ? objects[selectedType] : [];
  const instanceNames = instances.map((inst, idx) => inst.fields?.Name || `Instance ${idx + 1}`);
  const fields = selectedType && instances[selectedInstance] ? Object.keys(instances[selectedInstance].fields) : [];
  const currentValue = selectedField ? (instances[selectedInstance]?.fields[selectedField] ?? '') : '';

  const handleEdit = async () => {
    if (!selectedType || !selectedField) {
      setError("Veuillez sélectionner un type, une instance et un champ.");
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/update_idf_field/${fileId}`, {
        object_type: selectedType,
        object_index: selectedInstance,
        field_name: selectedField,
        new_value: newValue,
      });
      // Mettre à jour le contenu dans l'éditeur principal
      onChange(response.data.new_content);
      // Re-synchroniser les objets pour voir la nouvelle valeur
      const updatedObjects = await axios.get(`${API_BASE_URL}/get_idf_objects/${fileId}`);
      setObjects(updatedObjects.data);
      setNewValue(''); // Reset input field
    } catch (err: any) {
      setError('Erreur de mise à jour: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <div className="p-2 text-sm text-gray-500">Chargement des objets IDF...</div>;
  }
  
  if (error) {
    return <div className="p-2 text-sm text-red-500">{error}</div>
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="flex flex-col gap-2 p-2 bg-green-50 rounded mb-2 min-w-0">
        <div className="flex flex-col md:flex-row items-center gap-2 w-full">
          <select
            className="border rounded px-2 py-1 text-sm max-w-xs truncate"
            value={selectedType}
            onChange={e => {
              setSelectedType(e.target.value);
              setSelectedInstance(0);
              setSelectedField('');
            }}
          >
            <option value="">-- Type d'objet --</option>
            {types.map(type => <option key={type} value={type} className="truncate max-w-xs">{type}</option>)}
          </select>

          {selectedType && (
            <select
              className="border rounded px-2 py-1 text-sm max-w-xs truncate"
              value={selectedInstance}
              onChange={e => {
                setSelectedInstance(Number(e.target.value));
                setSelectedField('');
              }}
            >
              <option value="">-- Instance --</option>
              {instanceNames.map((name, idx) => <option key={idx} value={idx} className="truncate max-w-xs">{name}</option>)}
            </select>
          )}

          {selectedType && (
            <select
              className="border rounded px-2 py-1 text-sm max-w-xs truncate"
              value={selectedField}
              onChange={e => setSelectedField(e.target.value)}
            >
              <option value="">-- Champ --</option>
              {fields.map(field => <option key={field} value={field} className="truncate max-w-xs">{field}</option>)}
            </select>
          )}
        </div>
        {selectedField && (
          <div className="flex flex-row items-center gap-2 w-full mt-1">
            <input
              type="text"
              className="border rounded px-2 py-1 w-32 max-w-xs truncate text-sm"
              value={newValue}
              onChange={e => setNewValue(e.target.value)}
              placeholder={String(currentValue)}
            />
            <button
              className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
              onClick={handleEdit}
            >
              Appliquer
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default IDFQuickEditor; 