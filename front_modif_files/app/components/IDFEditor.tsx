'use client'

import { useRef } from 'react'
import Editor from '@monaco-editor/react'
import { LoaderIcon } from './Icons'

interface IDFEditorProps {
  content: string
  onChange: (value: string) => void
  filename: string
  isLoading: boolean
}

export default function IDFEditor({
  content,
  onChange,
  filename,
  isLoading
}: IDFEditorProps) {
  const editorRef = useRef<any>(null)

  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoaderIcon className="h-8 w-8 text-gray-400" />
        <span className="ml-2 text-gray-500">Loading IDF file...</span>
      </div>
    )
  }

  return (
    <div className="h-full">
      {/* Editor Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-900">IDF File:</span>
            <span className="text-sm text-gray-600 font-mono">{filename}</span>
          </div>
          <div className="text-xs text-gray-500">
            {content.split('\n').length} lines
          </div>
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="h-96">
        <Editor
          height="100%"
          defaultLanguage="plaintext"
          value={content}
          onChange={(value: string | undefined) => onChange(value || '')}
          onMount={handleEditorDidMount}
          options={{
            minimap: { enabled: true },
            fontSize: 14,
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            readOnly: false,
            automaticLayout: true,
            wordWrap: 'on',
            theme: 'vs-light',
            suggestOnTriggerCharacters: false,
            quickSuggestions: false,
            parameterHints: { enabled: false },
            hover: { enabled: false },
            contextmenu: true,
            folding: true,
            showFoldingControls: 'always',
            lineDecorationsWidth: 10,
            lineNumbersMinChars: 3,
            glyphMargin: true,
            overviewRulerBorder: false,
            hideCursorInOverviewRuler: true,
            overviewRulerLanes: 0,
            scrollbar: {
              vertical: 'visible',
              horizontal: 'visible',
              verticalScrollbarSize: 14,
              horizontalScrollbarSize: 14,
              useShadows: false,
              verticalHasArrows: false,
              horizontalHasArrows: false
            }
          }}
        />
      </div>
    </div>
  )
} 