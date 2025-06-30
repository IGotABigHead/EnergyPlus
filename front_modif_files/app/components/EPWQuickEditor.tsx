import React, { useState } from 'react';

// Liste standard des colonnes EPW (35 colonnes)
const EPW_COLUMNS = [
  'Year',
  'Month',
  'Day',
  'Hour',
  'Minute',
  'Data Source and Uncertainty Flags',
  'Dry Bulb Temperature (°C)',
  'Dew Point Temperature (°C)',
  'Relative Humidity (%)',
  'Atmospheric Station Pressure (Pa)',
  'Extraterrestrial Horizontal Radiation (Wh/m2)',
  'Extraterrestrial Direct Normal Radiation (Wh/m2)',
  'Horizontal Infrared Radiation Intensity (Wh/m2)',
  'Global Horizontal Radiation (Wh/m2)',
  'Direct Normal Radiation (Wh/m2)',
  'Diffuse Horizontal Radiation (Wh/m2)',
  'Global Horizontal Illuminance (lux)',
  'Direct Normal Illuminance (lux)',
  'Diffuse Horizontal Illuminance (lux)',
  'Zenith Luminance (Cd/m2)',
  'Wind Direction (degrees)',
  'Wind Speed (m/s)',
  'Total Sky Cover (tenths)',
  'Opaque Sky Cover (tenths)',
  'Visibility (km)',
  'Ceiling Height (m)',
  'Present Weather Observation',
  'Present Weather Codes',
  'Precipitable Water (mm)',
  'Aerosol Optical Depth (thousandths)',
  'Snow Depth (cm)',
  'Days Since Last Snowfall',
  'Albedo',
  'Liquid Precipitation Depth (mm)',
  'Liquid Precipitation Quantity (hr)'
];

interface EPWQuickEditorProps {
  content: string;
  onChange: (value: string) => void;
}

const EPWQuickEditor: React.FC<EPWQuickEditorProps> = ({ content, onChange }) => {
  const [selectedColumn, setSelectedColumn] = useState<number>(6); // Par défaut Dry Bulb Temp
  const [rowIndex, setRowIndex] = useState<number>(1); // 1 = première ligne de données
  const [newValue, setNewValue] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<string>('');
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [selectedDay, setSelectedDay] = useState<string>('');
  const [selectedHour, setSelectedHour] = useState<string>('');

  // Trouver la première ligne de données (après les headers)
  const lines = content.split('\n');
  const dataStartIdx = lines.findIndex(line => line.match(/^\d{4},/));
  const dataLines = dataStartIdx >= 0 ? lines.slice(dataStartIdx) : [];

  // Liste des années/mois/jours/heures disponibles dans les données (pour les dropdowns)
  const dateOptions = dataLines.map(line => {
    const fields = line.split(',');
    return {
      year: fields[0],
      month: fields[1],
      day: fields[2],
      hour: fields[3],
    };
  });
  const uniqueYears = Array.from(new Set(dateOptions.map(d => d.year)));
  const uniqueMonths = Array.from(new Set(dateOptions.filter(d => d.year === selectedYear || !selectedYear).map(d => d.month)));
  const uniqueDays = Array.from(new Set(dateOptions.filter(d => (d.year === selectedYear || !selectedYear) && (d.month === selectedMonth || !selectedMonth)).map(d => d.day)));
  const uniqueHours = Array.from(new Set(dateOptions.filter(d => (d.year === selectedYear || !selectedYear) && (d.month === selectedMonth || !selectedMonth) && (d.day === selectedDay || !selectedDay)).map(d => d.hour)));

  // Quand on sélectionne une date complète, on cherche la ligne correspondante
  React.useEffect(() => {
    if (selectedYear && selectedMonth && selectedDay && selectedHour) {
      const idx = dateOptions.findIndex(d => d.year === selectedYear && d.month === selectedMonth && d.day === selectedDay && d.hour === selectedHour);
      if (idx !== -1) {
        setRowIndex(idx + 1); // rowIndex est 1-based
      }
    }
  }, [selectedYear, selectedMonth, selectedDay, selectedHour]);

  // Valeur actuelle de la cellule sélectionnée
  let currentValue = '';
  if (dataLines.length && rowIndex >= 1 && rowIndex <= dataLines.length) {
    const row = lines[dataStartIdx + rowIndex - 1];
    if (row) {
      const fields = row.split(',');
      if (selectedColumn >= 0 && selectedColumn < fields.length) {
        currentValue = fields[selectedColumn];
      }
    }
  }

  const handleEdit = () => {
    setError('');
    if (!dataLines.length) {
      setError('Aucune donnée horaire trouvée dans ce fichier EPW.');
      return;
    }
    if (rowIndex < 1 || rowIndex > dataLines.length) {
      setError('Numéro de ligne invalide.');
      return;
    }
    const targetIdx = dataStartIdx + rowIndex - 1;
    const row = lines[targetIdx];
    if (!row) {
      setError('Ligne non trouvée.');
      return;
    }
    const fields = row.split(',');
    if (selectedColumn < 0 || selectedColumn >= fields.length) {
      setError('Colonne invalide.');
      return;
    }
    fields[selectedColumn] = newValue;
    const newRow = fields.join(',');
    const newLines = [...lines];
    newLines[targetIdx] = newRow;
    onChange(newLines.join('\n'));
  };

  return (
    <div className="w-full overflow-x-auto">
      <div className="flex flex-col gap-2 p-2 bg-blue-50 rounded mb-2 min-w-0">
        <div className="flex flex-col md:flex-row items-center gap-2 w-full">
          <div className="flex flex-col">
            <label className="text-sm">Colonne :</label>
            <select
              className="border rounded px-2 py-1 text-sm max-w-xs truncate"
              value={selectedColumn}
              onChange={e => setSelectedColumn(Number(e.target.value))}
            >
              {EPW_COLUMNS.map((col, idx) => (
                <option key={col} value={idx} className="truncate max-w-xs">{idx + 1}. {col}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col pl-10 pr-3">
            <label className="text-sm">Ligne :</label>
            <input
              type="number"
              min={1}
              max={dataLines.length}
              className="border rounded px-2 py-1 w-20 text-sm"
              value={rowIndex}
              onChange={e => setRowIndex(Number(e.target.value))}
            />
          </div>
          <label className='pt-4'>OU</label>
          <div className="flex flex-col min-w-0 pl-5">
            <label className="text-sm">Date :</label>
            <div className="flex flex-row items-center gap-1">
              <select className="border rounded px-1 py-1 text-sm max-w-[70px] truncate" value={selectedYear} onChange={e => setSelectedYear(e.target.value)}>
                <option value="">Année</option>
                {uniqueYears.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
              <select className="border rounded px-1 py-1 text-sm max-w-[70px] truncate" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}>
                <option value="">Mois</option>
                {uniqueMonths.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select className="border rounded px-1 py-1 text-sm max-w-[70px] truncate" value={selectedDay} onChange={e => setSelectedDay(e.target.value)}>
                <option value="">Jour</option>
                {uniqueDays.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <select className="border rounded px-1 py-1 text-sm max-w-[70px] truncate" value={selectedHour} onChange={e => setSelectedHour(e.target.value)}>
                <option value="">Heure</option>
                {uniqueHours.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>
          </div>
        </div>
        {/* Ligne d'édition */}
        <div className="flex flex-col md:flex-row items-center gap-2 w-full mt-1">
          <div className="flex flex-col md:flex-row items-center gap-2 w-full">
            <div className="flex flex-col">
              <label className="text-sm">Valeur actuelle :</label>
              <span className="px-2 py-1 bg-gray-100 rounded text-sm min-w-[40px] text-blue-900 border border-gray-200 max-w-xs truncate inline-block" title={currentValue}>{currentValue}</span>
            </div>
            <div className="flex flex-col">
              <label className="text-sm">Nouvelle valeur :</label>
              <input
                type="text"
                className="border rounded px-2 py-1 w-32 max-w-xs truncate text-sm"
                value={newValue}
                onChange={e => setNewValue(e.target.value)}
              />
            </div>
            <button
              className="mt-4 md:mt-6 px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm h-8 self-end md:self-auto"
              onClick={handleEdit}
            >
              Appliquer
            </button>
          </div>
          {error && <span className="text-red-500 text-xs ml-2">{error}</span>}
        </div>
      </div>
    </div>
  );
};

export default EPWQuickEditor; 