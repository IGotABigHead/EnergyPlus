'use client'

import { useState } from 'react'
import { ChevronDownIcon, SearchIcon, LoaderIcon } from './Icons'

interface SimulationSelectorProps {
  simulations: string[]
  selectedSimulation: string
  onSelect: (simulation: string) => void
  isLoading: boolean
}

export default function SimulationSelector({
  simulations,
  selectedSimulation,
  onSelect,
  isLoading
}: SimulationSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const filteredSimulations = simulations.filter(simulation =>
    simulation.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="relative">
   

      {/* Dropdown */}
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-3 py-2 border border-gray-300 rounded-md bg-white shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <span className={selectedSimulation ? 'text-gray-900' : 'text-gray-500'}>
            {selectedSimulation || 'Select a simulation...'}
          </span>
          <ChevronDownIcon className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-4">
                <LoaderIcon className="h-4 w-4 text-gray-400" />
                <span className="ml-2 text-gray-500">Loading...</span>
              </div>
            ) : filteredSimulations.length === 0 ? (
              <div className="px-3 py-2 text-gray-500">No simulations found</div>
            ) : (
              <div className="py-1">
                {filteredSimulations.map((simulation) => (
                  <button
                    key={simulation}
                    onClick={() => {
                      onSelect(simulation)
                      setIsOpen(false)
                      setSearchTerm('')
                    }}
                    className={`w-full text-left px-3 py-2 hover:bg-gray-100 focus:bg-gray-100 focus:outline-none ${
                      selectedSimulation === simulation ? 'bg-blue-50 text-blue-700' : 'text-gray-900'
                    }`}
                  >
                    {simulation}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

    
    </div>
  )
} 