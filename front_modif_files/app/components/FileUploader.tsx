'use client'

interface FileUploaderProps {
  fileType: 'idf' | 'epw'
  onUpload?: () => void
  onFileUploaded?: (fileId: string) => void
}

export default function FileUploader({ fileType, onUpload, onFileUploaded }: FileUploaderProps) {
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`http://localhost:8000/input_file/upload/?file_type=${fileType}`, {
      method: 'POST',
      body: formData
    })
    if (onUpload) onUpload()
    if (response.ok) {
      const data = await response.json()
      if (onFileUploaded && data.new_id) onFileUploaded(data.new_id)
    }
  }
  return (
    <div>
      <input
        type="file"
        accept={fileType === 'idf' ? '.idf' : '.epw'}
        onChange={handleFileChange}
        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
      />
    </div>
  )
} 