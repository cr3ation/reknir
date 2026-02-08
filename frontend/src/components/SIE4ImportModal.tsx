import { useState, useRef } from 'react'
import { X, Upload, CheckCircle, XCircle, AlertTriangle, Loader2, FileText, Calendar, Hash } from 'lucide-react'
import { sie4Api } from '@/services/api'
import type { SIE4PreviewResponse, SIE4ImportResponse } from '@/types'

interface SIE4ImportModalProps {
  isOpen: boolean
  onClose: () => void
  companyId: number
  onSuccess?: () => void
}

type Step = 'upload' | 'preview' | 'importing' | 'result'

export default function SIE4ImportModal({ isOpen, onClose, companyId, onSuccess }: SIE4ImportModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<SIE4PreviewResponse | null>(null)
  const [result, setResult] = useState<SIE4ImportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const resetState = () => {
    setStep('upload')
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
    setLoading(false)
  }

  const handleClose = () => {
    if (loading) return
    resetState()
    onClose()
  }

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0]
    if (!selectedFile) return

    // Validate file extension
    const validExtensions = ['.se', '.si', '.sie']
    const hasValidExtension = validExtensions.some(ext =>
      selectedFile.name.toLowerCase().endsWith(ext)
    )
    if (!hasValidExtension) {
      setError('Filen måste vara en SIE-fil (.se, .si eller .sie)')
      return
    }

    setFile(selectedFile)
    setError(null)
    setLoading(true)

    try {
      const response = await sie4Api.preview(companyId, selectedFile)
      setPreview(response.data)
      setStep('preview')
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Kunde inte analysera filen'
      setError(errorMessage)
      setFile(null)
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    if (!file || !preview?.can_import) return

    setLoading(true)
    setStep('importing')
    setError(null)

    try {
      const response = await sie4Api.import(companyId, file)
      setResult(response.data)
      setStep('result')
      if (response.data.success && onSuccess) {
        onSuccess()
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Import misslyckades'
      setError(errorMessage)
      setResult({
        success: false,
        message: errorMessage,
        accounts_created: 0,
        accounts_updated: 0,
        verifications_created: 0,
        verifications_skipped: 0,
        default_accounts_configured: 0,
        fiscal_year_id: null,
        fiscal_year_created: false,
        errors: [errorMessage],
        warnings: [],
      })
      setStep('result')
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('sv-SE')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-gray-900">
              Importera SIE4-fil
            </h3>
            {!loading && (
              <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            )}
          </div>

          {/* Step 1: Upload */}
          {step === 'upload' && (
            <div>
              <p className="text-gray-600 mb-4">
                Välj en SIE4-fil att importera. Filen analyseras innan import.
              </p>
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  loading
                    ? 'border-gray-300 bg-gray-50'
                    : 'border-gray-300 hover:border-blue-500 hover:bg-blue-50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".se,.si,.sie"
                  onChange={handleFileSelect}
                  className="hidden"
                  disabled={loading}
                />
                {loading ? (
                  <div>
                    <Loader2 className="w-12 h-12 text-blue-500 mx-auto mb-3 animate-spin" />
                    <p className="text-gray-600">Analyserar fil...</p>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600">Klicka för att välja en SIE4-fil</p>
                    <p className="text-sm text-gray-500 mt-1">.se, .si eller .sie</p>
                  </div>
                )}
              </div>
              {error && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Step 2: Preview */}
          {step === 'preview' && preview && (
            <div>
              {/* File info */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-5 h-5 text-gray-500" />
                  <span className="font-medium text-gray-900">{file?.name}</span>
                </div>
              </div>

              {/* Fiscal year info */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <h4 className="font-medium text-blue-900 mb-3 flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Räkenskapsår
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-blue-700">Period:</span>
                    <span className="font-medium text-blue-900">
                      {formatDate(preview.fiscal_year_start)} - {formatDate(preview.fiscal_year_end)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-blue-700">Status:</span>
                    <span className={`font-medium ${preview.fiscal_year_exists ? 'text-green-700' : 'text-amber-700'}`}>
                      {preview.fiscal_year_exists ? 'Finns redan' : 'Kommer skapas'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Content summary */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <Hash className="w-5 h-5" />
                  Innehåll
                </h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="text-center p-3 bg-white rounded border">
                    <div className="text-2xl font-bold text-gray-900">{preview.accounts_count}</div>
                    <div className="text-gray-600">Konton</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded border">
                    <div className="text-2xl font-bold text-gray-900">{preview.verifications_count}</div>
                    <div className="text-gray-600">Verifikationer</div>
                  </div>
                </div>
              </div>

              {/* Blocking errors */}
              {preview.blocking_errors.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <div className="flex items-start gap-2">
                    <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-red-900">Import blockerad</h4>
                      <ul className="mt-2 text-sm text-red-800 space-y-1">
                        {preview.blocking_errors.map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Warnings */}
              {preview.warnings.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-amber-900">Varningar</h4>
                      <ul className="mt-2 text-sm text-amber-800 space-y-1">
                        {preview.warnings.map((warn, i) => (
                          <li key={i}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-between mt-6">
                <button
                  onClick={() => {
                    setStep('upload')
                    setFile(null)
                    setPreview(null)
                    setError(null)
                  }}
                  className="btn btn-secondary"
                >
                  Tillbaka
                </button>
                <button
                  onClick={handleImport}
                  disabled={!preview.can_import}
                  className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Importera
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Importing */}
          {step === 'importing' && (
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-spin" />
              <h4 className="font-medium text-gray-900 mb-2">Importerar...</h4>
              <p className="text-sm text-gray-600">
                Detta kan ta några sekunder.
              </p>
            </div>
          )}

          {/* Step 4: Result */}
          {step === 'result' && result && (
            <div>
              {result.success ? (
                <div className="text-center py-4">
                  <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                  <h4 className="text-xl font-medium text-gray-900 mb-4">
                    Import slutförd!
                  </h4>

                  {/* Statistics */}
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4 text-left">
                    <h5 className="text-sm font-medium text-gray-700 mb-3">Resultat:</h5>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Konton skapade:</span>
                        <span className="font-medium">{result.accounts_created}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Konton uppdaterade:</span>
                        <span className="font-medium">{result.accounts_updated}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Verifikationer skapade:</span>
                        <span className="font-medium">{result.verifications_created}</span>
                      </div>
                      {result.verifications_skipped > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Verifikationer hoppades över:</span>
                          <span className="font-medium text-amber-600">{result.verifications_skipped}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span className="text-gray-600">Standardkonton konfigurerade:</span>
                        <span className="font-medium">{result.default_accounts_configured}</span>
                      </div>
                      {result.fiscal_year_created && (
                        <div className="flex justify-between col-span-2">
                          <span className="text-gray-600">Räkenskapsår:</span>
                          <span className="font-medium text-green-600">Nytt skapat</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Warnings */}
                  {result.warnings.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-left">
                      <h5 className="text-sm font-medium text-amber-900 mb-2">Varningar:</h5>
                      <ul className="text-sm text-amber-800 space-y-1">
                        {result.warnings.map((warn, i) => (
                          <li key={i}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <button onClick={handleClose} className="btn btn-primary">
                    Stäng
                  </button>
                </div>
              ) : (
                <div className="text-center py-4">
                  <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                  <h4 className="text-xl font-medium text-gray-900 mb-4">
                    Import misslyckades
                  </h4>

                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-left">
                    <p className="text-sm text-red-800">{result.message}</p>
                    {result.errors.length > 0 && (
                      <ul className="mt-2 text-sm text-red-800 space-y-1">
                        {result.errors.map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <button onClick={handleClose} className="btn btn-primary">
                    Stäng
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
