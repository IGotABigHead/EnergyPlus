'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import { FileTextIcon, SaveIcon, RotateCcwIcon, DownloadIcon } from './components/Icons'
import IDFEditor from './components/IDFEditor'
import SimulationSelector from './components/SimulationSelector'
import FileUploader from './components/FileUploader'
import EPWQuickEditor from './components/EPWQuickEditor'
import IDFQuickEditor from './components/IDFQuickEditor'

const API_BASE_URL = 'http://localhost:8000'

type FileType = 'idf' | 'epw'

type InputFile = {
  _id: string
  filename: string
  upload_date?: string
  version?: number
}

export default function Home() {
  const [simulations, setSimulations] = useState<string[]>([])
  const [selectedSimulation, setSelectedSimulation] = useState<string>('')
  const [idfContent, setIdfContent] = useState<string>('')
  const [idfFileId, setIdfFileId] = useState<string>('')
  const [epwContent, setEpwContent] = useState<string>('')
  const [epwFileId, setEpwFileId] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [fileType, setFileType] = useState<FileType>('idf')
  const [isRunning, setIsRunning] = useState(false)
  const [runResult, setRunResult] = useState<null | { status: string, stdout: string, stderr: string, message?: string }>(null)
  const [idfFiles, setIdfFiles] = useState<InputFile[]>([])
  const [epwFiles, setEpwFiles] = useState<InputFile[]>([])
  const [selectedIdfId, setSelectedIdfId] = useState<string>('')
  const [selectedEpwId, setSelectedEpwId] = useState<string>('')
  const [idfFilename, setIdfFilename] = useState<string>('')
  const [epwFilename, setEpwFilename] = useState<string>('')

  // Fetch simulations and input files on mount
  useEffect(() => {
    fetchSimulations()
    fetchInputFilesList('idf')
    fetchInputFilesList('epw')
  }, [])

  const fetchSimulations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/simulations`)
      setSimulations(response.data.simulations)
    } catch (error) {
      console.error('Error fetching simulations:', error)
    }
  }

  const fetchInputFilesList = async (type: FileType) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/input_files/?file_type=${type}`)
      if (type === 'idf') setIdfFiles(response.data)
      if (type === 'epw') setEpwFiles(response.data)
    } catch (error) {
      console.error('Error fetching input files list:', error)
    }
  }

  const fetchInputFiles = async (simulationName: string) => {
    setIsLoading(true)
    setRunResult(null)
    try {
      const response = await axios.get(`${API_BASE_URL}/input_file/by_simulation/${simulationName}`)
      if (response.data.idf) {
        setIdfContent(response.data.idf.content)
        setIdfFileId(response.data.idf._id)
        setSelectedIdfId(response.data.idf._id)
        setIdfFilename(response.data.idf.filename)
      } else {
        setIdfContent('')
        setIdfFileId('')
        setSelectedIdfId('')
        setIdfFilename('')
      }
      if (response.data.epw) {
        setEpwContent(response.data.epw.content)
        setEpwFileId(response.data.epw._id)
        setSelectedEpwId(response.data.epw._id)
        setEpwFilename(response.data.epw.filename)
      } else {
        setEpwContent('')
        setEpwFileId('')
        setSelectedEpwId('')
        setEpwFilename('')
      }
    } catch (error) {
      console.error('Error fetching input files:', error)
      setIdfContent('')
      setIdfFileId('')
      setSelectedIdfId('')
      setIdfFilename('')
      setEpwContent('')
      setEpwFileId('')
      setSelectedEpwId('')
      setEpwFilename('')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSimulationSelect = (simulationName: string) => {
    setSelectedSimulation(simulationName)
    fetchInputFiles(simulationName)
  }

  const handleSave = async () => {
    const fileId = fileType === 'idf' ? idfFileId : epwFileId
    const content = fileType === 'idf' ? idfContent : epwContent
    let filename = fileType === 'idf' ? idfFilename : epwFilename
    // Force l'extension correcte
    if (fileType === 'idf' && !filename.toLowerCase().endsWith('.idf')) {
      filename = filename.replace(/\.[^.]+$/, '') + '.idf'
    }
    if (fileType === 'epw' && !filename.toLowerCase().endsWith('.epw')) {
      filename = filename.replace(/\.[^.]+$/, '') + '.epw'
    }
    // Encodage base64 du contenu avant envoi
    const contentBase64 = btoa(unescape(encodeURIComponent(content)))
    if (!fileId) return
    setIsSaving(true)
    setSaveStatus('idle')
    try {
      const response = await axios.post(
        `${API_BASE_URL}/input_file/save_new_version/${fileId}`,
        { content: contentBase64, filename },
        { headers: { 'Content-Type': 'application/json' } }
      )
      setSaveStatus('success')
      if (fileType === 'idf') setSelectedIdfId(response.data.new_id)
      if (fileType === 'epw') setSelectedEpwId(response.data.new_id)
      fetchInputFilesList(fileType)
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch (error) {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDownload = () => {
    const content = fileType === 'idf' ? idfContent : epwContent
    const ext = fileType
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedSimulation}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleReset = () => {
    if (selectedSimulation) {
      fetchInputFiles(selectedSimulation)
    }
  }

  const handleRunSimulation = async () => {
    if (!selectedIdfId || !selectedEpwId) return
    setIsRunning(true)
    setRunResult(null)
    try {
      const response = await axios.post(`${API_BASE_URL}/run_simulation/`, {
        idf_file_id: selectedIdfId,
        epw_file_id: selectedEpwId
      })
      setRunResult(response.data)
    } catch (error: any) {
      setRunResult({
        status: 'error',
        stdout: '',
        stderr: error?.response?.data?.detail || error.message || 'Unknown error'
      })
    } finally {
      setIsRunning(false)
    }
  }

  // Sélection automatique après upload
  const handleIdfUploaded = async (fileId: string) => {
    await fetchInputFilesList('idf')
    setSelectedIdfId(fileId)
  }
  const handleEpwUploaded = async (fileId: string) => {
    await fetchInputFilesList('epw')
    setSelectedEpwId(fileId)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <FileTextIcon className="h-8 w-8 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900">
                EnergyPlus Input File Editor
              </h1>
            </div>
            {/* File uploaders */}
            {/* <div className="flex items-center space-x-4">
              <FileUploader fileType="idf" onUpload={() => fetchInputFilesList('idf')} />
              <FileUploader fileType="epw" onUpload={() => fetchInputFilesList('epw')} />
            </div> */}
            {/* End file uploaders */}
            <div className="flex items-center space-x-2">
              {selectedSimulation && (
                <>
                  <button
                    onClick={handleReset}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <RotateCcwIcon className="h-4 w-4 mr-2" />
                    Reset
                  </button>
                  <button
                    onClick={handleDownload}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <DownloadIcon className="h-4 w-4 mr-2" />
                    Download
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isSaving || !(fileType === 'idf' ? idfFileId : epwFileId)}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <SaveIcon className="h-4 w-4 mr-2" />
                    {isSaving ? 'Saving...' : 'Save Changes'}
                  </button>
                  <input
                    type="text"
                    className="ml-4 px-2 py-1 border border-gray-300 rounded"
                    value={fileType === 'idf' ? idfFilename : epwFilename}
                    onChange={e => fileType === 'idf' ? setIdfFilename(e.target.value) : setEpwFilename(e.target.value)}
                    placeholder="Nom du fichier"
                    style={{ minWidth: 180 }}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Sélection indépendante des fichiers IDF/EPW */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6 flex flex-col md:flex-row gap-4 items-center">
        <div className="w-full mb-4">
          <div className="bg-white rounded-lg shadow p-4 mb-4">
            <p className="mb-12  text-gray-700 font-medium">Vous pouvez importer de nouveaux fichiers </p>
            <div className="flex flex-col md:flex-row gap-4 mb-3">
              <p>EPW Files</p><FileUploader fileType="epw" onUpload={() => fetchInputFilesList('epw')} onFileUploaded={handleEpwUploaded} />
            </div>
            <div className="flex flex-col md:flex-row gap-4 mb-3">
            <p>IDF Files</p><FileUploader fileType="idf" onUpload={() => fetchInputFilesList('idf')} onFileUploaded={handleIdfUploaded} />
            </div>
          </div>
        </div>
        <p>ou</p>
        <div className="w-full mb-4">
          <div className="bg-white rounded-lg shadow p-4 mb-4">
            <p className="mb-8 text-gray-700 font-medium">Vous pouvez utiliser les fichiers existants ci-dessous.</p>
            <div className="flex flex-col md:flex-row gap-4">
            <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">IDF file à utiliser pour la simulation</label>
            <select
              className="w-64 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={selectedIdfId}
              onChange={e => setSelectedIdfId(e.target.value)}
            >
              <option value="">-- Choisir un fichier IDF --</option>
              {idfFiles.map(f => (
                <option key={f._id} value={f._id}>{f.filename} (v{f.version || 1})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">EPW file à utiliser pour la simulation</label>
            <select
              className="w-64 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={selectedEpwId}
              onChange={e => setSelectedEpwId(e.target.value)}
            >
              <option value="">-- Choisir un fichier EPW --</option>
              {epwFiles.map(f => (
                <option key={f._id} value={f._id}>{f.filename} (v{f.version || 1})</option>
              ))}
            </select>
          </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col md:flex-row gap-4 w-full md:w-auto">
          
          <div className="flex items-end">
            <button
              onClick={handleRunSimulation}
              disabled={isRunning || !selectedIdfId || !selectedEpwId}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRunning ? 'Running...' : 'Run Simulation'}
            </button>
          </div>
        </div>
      </div>

      {/* Run Simulation Result */}
      {runResult && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className={`rounded-md p-4 ${runResult.status === 'success' ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'}`}>
            <div className="font-bold mb-2">Simulation {runResult.status === 'success' ? 'success' : 'error'}</div>
            <div className="mb-2">
              <span className="font-semibold">stdout:</span>
              <pre className="whitespace-pre-wrap text-xs bg-gray-100 rounded p-2 mt-1 overflow-x-auto max-h-40">{runResult.stdout || runResult.message}</pre>
            </div>

          </div>
        </div>
      )}

      {/* Save Status */}
      {saveStatus !== 'idle' && (
        <div className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4`}>
          <div className={`rounded-md p-4 ${
            saveStatus === 'success' 
              ? 'bg-green-50 border border-green-200 text-green-800' 
              : 'bg-red-50 border border-red-200 text-red-800'
          }`}>
            {saveStatus === 'success' ? '✅ File saved successfully!' : '❌ Error saving file'}
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Simulations
              </h2>
              <SimulationSelector
                simulations={simulations}
                selectedSimulation={selectedSimulation}
                onSelect={handleSimulationSelect}
                isLoading={isLoading}
              />
            </div>
          </div>

          {/* Editor with toggle */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow">
              {selectedSimulation ? (
                <>
                  <div className="flex space-x-2 border-b border-gray-200 px-4 pt-4">
                    <button
                      onClick={() => setFileType('idf')}
                      className={`px-4 py-2 rounded-t-md font-medium focus:outline-none transition-colors ${fileType === 'idf' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-blue-50'}`}
                    >
                      IDF
                    </button>
                    <button
                      onClick={() => setFileType('epw')}
                      className={`px-4 py-2 rounded-t-md font-medium focus:outline-none transition-colors ${fileType === 'epw' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-blue-50'}`}
                    >
                      EPW
                    </button>
                  </div>
                  {fileType === 'idf' ? (
                    <>
                      <IDFQuickEditor
                        fileId={idfFileId}
                        onChange={setIdfContent}
                      />
                      <IDFEditor
                        content={idfContent}
                        onChange={setIdfContent}
                        filename={`${selectedSimulation}.idf`}
                        isLoading={isLoading}
                      />
                    </>
                  ) : (
                    <>
                      <EPWQuickEditor
                        content={epwContent}
                        onChange={setEpwContent}
                      />
                      <IDFEditor
                        content={epwContent}
                        onChange={setEpwContent}
                        filename={`${selectedSimulation}.epw`}
                        isLoading={isLoading}
                      />
                    </>
                  )}
                </>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <FileTextIcon className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>Select a simulation to edit its input files</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
