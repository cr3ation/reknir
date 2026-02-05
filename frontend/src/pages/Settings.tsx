import { useState, useEffect } from 'react'
import { companyApi, sie4Api, accountApi, fiscalYearApi, postingTemplateApi, backupApi } from '@/services/api'
import type { Account, FiscalYear, PostingTemplate, PostingTemplateLine, BackupInfo } from '@/types'
import { VATReportingPeriod, AccountingBasis } from '@/types'
import { Plus, Trash2, GripVertical, Building2, Edit2, Save, X, Calendar, Upload, Image, Layout, Download, HardDrive, RotateCcw, Loader2 } from 'lucide-react'
import RestoreModal from '@/components/RestoreModal'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { useLayoutSettings } from '@/contexts/LayoutSettingsContext'
import FiscalYearSelector from '@/components/FiscalYearSelector'

export default function SettingsPage() {
  const { selectedCompany, setSelectedCompany, companies, loadCompanies } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const { settings: layoutSettings, updateSettings: updateLayoutSettings } = useLayoutSettings()
  const [allAccounts, setAllAccounts] = useState<Account[]>([])
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([])
  const [accountCountsByFiscalYear, setAccountCountsByFiscalYear] = useState<Record<number, number>>({})
  const [templates, setTemplates] = useState<PostingTemplate[]>([])
  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<PostingTemplate | null>(null)
  const [templateForm, setTemplateForm] = useState<PostingTemplate>({
    company_id: 0,
    name: '',
    description: '',
    default_series: '',
    default_journal_text: '',
    template_lines: []
  })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')
  const [activeTab, setActiveTab] = useState<'company' | 'fiscal' | 'templates' | 'import' | 'layout'>('company')
  const [showCreateFiscalYear, setShowCreateFiscalYear] = useState(false)
  const [showImportSummary, setShowImportSummary] = useState(false)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [backups, setBackups] = useState<BackupInfo[]>([])
  const [loadingBackups, setLoadingBackups] = useState(false)
  const [creatingBackup, setCreatingBackup] = useState(false)
  const [downloadingBackup, setDownloadingBackup] = useState<string | null>(null)
  const [showRestoreModal, setShowRestoreModal] = useState(false)
  const [importSummary, setImportSummary] = useState<{
    accounts_created: number
    accounts_updated: number
    verifications_created: number
    default_accounts_configured: number
    errors?: string[]
    warnings?: string[]
  } | null>(null)
  const [editingCompany, setEditingCompany] = useState(false)
  const [showCreateCompany, setShowCreateCompany] = useState(false)
  const [companyForm, setCompanyForm] = useState({
    name: '',
    org_number: '',
    address: '',
    postal_code: '',
    city: '',
    phone: '',
    email: '',
    fiscal_year_start: new Date().getFullYear() + '-01-01',
    fiscal_year_end: new Date().getFullYear() + '-12-31',
    vat_number: '',
    accounting_basis: AccountingBasis.ACCRUAL,
    vat_reporting_period: VATReportingPeriod.QUARTERLY,
  })

  const getNextFiscalYearDefaults = () => {
    const currentYear = new Date().getFullYear()
    const nextYear = fiscalYears.length > 0
      ? Math.max(...fiscalYears.map(fy => fy.year)) + 1
      : currentYear

    return {
      year: nextYear,
      label: `${nextYear}`,
      start_date: `${nextYear}-01-01`,
      end_date: `${nextYear}-12-31`,
    }
  }

  const [newFiscalYear, setNewFiscalYear] = useState(getNextFiscalYearDefaults())

  useEffect(() => {
    loadData()
  }, [selectedCompany, selectedFiscalYear])

  useEffect(() => {
    if (activeTab === 'import') {
      loadBackups()
    }
  }, [activeTab])

  const loadData = async () => {
    if (!selectedCompany) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      const fiscalYearsRes = await fiscalYearApi.list(selectedCompany.id).catch(() => ({ data: [] }))
      setFiscalYears(fiscalYearsRes.data)

      // Load account counts for each fiscal year (for the fiscal year tab)
      const accountCounts: Record<number, number> = {}
      await Promise.all(
        fiscalYearsRes.data.map(async (fy: FiscalYear) => {
          try {
            const accountsRes = await accountApi.list(selectedCompany.id, fy.id)
            accountCounts[fy.id] = accountsRes.data.length
          } catch {
            accountCounts[fy.id] = 0
          }
        })
      )
      setAccountCountsByFiscalYear(accountCounts)

      // If we have a selected fiscal year, load accounts
      if (selectedFiscalYear) {
        const [accountsRes, templatesRes] = await Promise.all([
          accountApi.list(selectedCompany.id, selectedFiscalYear.id),
          postingTemplateApi.list(selectedCompany.id).catch(() => ({ data: [] })),
        ])
        setAllAccounts(accountsRes.data)
        setTemplates(templatesRes.data)
      }
    } catch (error: any) {
      console.error('Failed to load data:', error)
      showMessage('Kunde inte ladda data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const showMessage = (msg: string, type: 'success' | 'error' = 'success') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => setMessage(''), 5000)
  }

  const handleLogoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCompany || !event.target.files || event.target.files.length === 0) return

    const file = event.target.files[0]
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      showMessage('Filen måste vara en bild', 'error')
      return
    }
    
    if (!['image/png', 'image/jpeg', 'image/jpg'].includes(file.type)) {
      showMessage('Endast PNG och JPG filer är tillåtna', 'error')
      return
    }
    
    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      showMessage('Filstorleken får inte överstiga 5MB', 'error')
      return
    }

    setUploadingLogo(true)
    try {
      const response = await companyApi.uploadLogo(selectedCompany.id, file)
      setSelectedCompany(response.data)
      showMessage('Logotyp uppladdad', 'success')
      
      // Clear the input so the same file can be selected again if needed
      event.target.value = ''
    } catch (error: any) {
      console.error('Logo upload failed:', error)
      showMessage(error.response?.data?.detail || 'Uppladdning misslyckades', 'error')
    } finally {
      setUploadingLogo(false)
    }
  }

  const handleLogoDelete = async () => {
    if (!selectedCompany || !selectedCompany.logo_filename) return
    
    if (!confirm('Är du säker på att du vill ta bort logotypen?')) return

    try {
      const response = await companyApi.deleteLogo(selectedCompany.id)
      setSelectedCompany(response.data)
      showMessage('Logotyp borttagen', 'success')
    } catch (error: any) {
      console.error('Logo delete failed:', error)
      showMessage(error.response?.data?.detail || 'Borttagning misslyckades', 'error')
    }
  }

  const startEditCompany = () => {
    if (!selectedCompany) return
    setCompanyForm({
      name: selectedCompany.name,
      org_number: selectedCompany.org_number,
      address: selectedCompany.address || '',
      postal_code: selectedCompany.postal_code || '',
      city: selectedCompany.city || '',
      phone: selectedCompany.phone || '',
      email: selectedCompany.email || '',
      fiscal_year_start: selectedCompany.fiscal_year_start,
      fiscal_year_end: selectedCompany.fiscal_year_end,
      vat_number: selectedCompany.vat_number || '',
      accounting_basis: selectedCompany.accounting_basis,
      vat_reporting_period: selectedCompany.vat_reporting_period,
    })
    setEditingCompany(true)
  }

  const cancelEditCompany = () => {
    setEditingCompany(false)
    setCompanyForm({
      name: '',
      org_number: '',
      address: '',
      postal_code: '',
      city: '',
      phone: '',
      email: '',
      fiscal_year_start: new Date().getFullYear() + '-01-01',
      fiscal_year_end: new Date().getFullYear() + '-12-31',
      vat_number: '',
      accounting_basis: AccountingBasis.ACCRUAL,
      vat_reporting_period: VATReportingPeriod.QUARTERLY,
    })
  }

  const formatErrorMessage = (error: any): string => {
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      // If detail is an array of validation errors
      if (Array.isArray(detail)) {
        return detail.map((err: any) => {
          const field = err.loc?.slice(-1)[0] || 'okänt fält'
          const message = err.msg || err.type || 'valideringsfel'
          return `• ${field}: ${message}`
        }).join('\n')
      }
      // If detail is a string
      if (typeof detail === 'string') {
        return detail
      }
      // If detail is an object, try to stringify it
      return JSON.stringify(detail, null, 2)
    }
    return `Ett fel uppstod: ${error.message || 'Okänt fel'}`
  }

  const handleUpdateCompany = async () => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      const response = await companyApi.update(selectedCompany.id, companyForm)
      setSelectedCompany(response.data)
      showMessage('Företagsinformation uppdaterad!', 'success')
      setEditingCompany(false)
      await loadCompanies()
    } catch (error: any) {
      console.error('Failed to update company:', error)
      showMessage(formatErrorMessage(error), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateCompany = async () => {
    try {
      setLoading(true)
      const response = await companyApi.create(companyForm)
      showMessage('Nytt företag skapat!', 'success')
      setShowCreateCompany(false)
      setCompanyForm({
        name: '',
        org_number: '',
        address: '',
        postal_code: '',
        city: '',
        phone: '',
        email: '',
        fiscal_year_start: new Date().getFullYear() + '-01-01',
        fiscal_year_end: new Date().getFullYear() + '-12-31',
        vat_number: '',
        accounting_basis: AccountingBasis.ACCRUAL,
        vat_reporting_period: VATReportingPeriod.QUARTERLY,
      })
      await loadCompanies()
      setSelectedCompany(response.data)
    } catch (error: any) {
      console.error('Failed to create company:', error)
      showMessage(formatErrorMessage(error), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSIE4Import = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCompany || !selectedFiscalYear) {
      showMessage('Välj ett räkenskapsår först', 'error')
      return
    }

    const file = event.target.files?.[0]
    if (!file) return

    try {
      setLoading(true)
      const response = await sie4Api.import(selectedCompany.id, selectedFiscalYear.id, file)

      // Show modal with import summary
      setImportSummary({
        accounts_created: response.data.accounts_created,
        accounts_updated: response.data.accounts_updated,
        verifications_created: response.data.verifications_created,
        default_accounts_configured: response.data.default_accounts_configured,
        errors: response.data.errors || [],
        warnings: response.data.warnings || [],
      })
      setShowImportSummary(true)

      await loadData()
    } catch (error: any) {
      console.error('SIE4 import failed:', error)
      showMessage(error.response?.data?.detail || 'Import misslyckades', 'error')
    } finally {
      setLoading(false)
      // Reset input
      event.target.value = ''
    }
  }

  const handleSIE4Export = async (includeVerifications: boolean) => {
    if (!selectedCompany || !selectedFiscalYear) {
      showMessage('Välj ett räkenskapsår först', 'error')
      return
    }

    try {
      setLoading(true)
      const response = await sie4Api.export(selectedCompany.id, selectedFiscalYear.id, includeVerifications)

      // Create download link
      const blob = new Blob([response.data], { type: 'text/plain' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `reknir_export_${new Date().toISOString().split('T')[0]}.se`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      showMessage('Export lyckades!', 'success')
    } catch (error: any) {
      console.error('SIE4 export failed:', error)
      showMessage('Export misslyckades', 'error')
    } finally {
      setLoading(false)
    }
  }

  const loadBackups = async () => {
    setLoadingBackups(true)
    try {
      const response = await backupApi.list()
      setBackups(response.data)
    } catch (error: any) {
      console.error('Failed to load backups:', error)
      showMessage('Kunde inte ladda backups', 'error')
    } finally {
      setLoadingBackups(false)
    }
  }

  const handleCreateBackup = async () => {
    setCreatingBackup(true)
    try {
      const response = await backupApi.create()

      // Trigger download
      const blob = new Blob([response.data], { type: 'application/gzip' })
      const url = window.URL.createObjectURL(blob)
      const contentDisposition = response.headers['content-disposition']
      let filename = `reknir_backup_${new Date().toISOString().split('T')[0]}.tar.gz`
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
        if (match) filename = match[1]
      }

      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      showMessage('Backup skapad och nedladdad!', 'success')
      loadBackups()
    } catch (error: any) {
      console.error('Backup creation failed:', error)
      showMessage(error.response?.data?.detail || 'Kunde inte skapa backup', 'error')
    } finally {
      setCreatingBackup(false)
    }
  }

  const handleDownloadBackup = async (filename: string) => {
    setDownloadingBackup(filename)
    try {
      const response = await backupApi.download(filename)

      const blob = new Blob([response.data], { type: 'application/gzip' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      showMessage('Backup nedladdad', 'success')
    } catch (error: any) {
      console.error('Backup download failed:', error)
      showMessage('Kunde inte ladda ner backup', 'error')
    } finally {
      setDownloadingBackup(null)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatBackupDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString('sv-SE')
  }

  const handleVATReportingPeriodChange = async (newPeriod: VATReportingPeriod) => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      await companyApi.update(selectedCompany.id, { vat_reporting_period: newPeriod })
      setSelectedCompany({ ...selectedCompany, vat_reporting_period: newPeriod })
      showMessage('Momsredovisningsperiod uppdaterad!', 'success')
    } catch (error: any) {
      console.error('Failed to update VAT reporting period:', error)
      showMessage('Kunde inte uppdatera momsredovisningsperiod', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateFiscalYear = async () => {
    if (!selectedCompany) return

    if (!newFiscalYear.label || !newFiscalYear.start_date || !newFiscalYear.end_date) {
      showMessage('Fyll i alla fält', 'error')
      return
    }

    try {
      setLoading(true)

      // Step 1: Create the new fiscal year
      const createResponse = await fiscalYearApi.create({
        company_id: selectedCompany.id,
        year: newFiscalYear.year,
        label: newFiscalYear.label,
        start_date: newFiscalYear.start_date,
        end_date: newFiscalYear.end_date,
        is_closed: false,
      })

      const newFiscalYearId = createResponse.data.id

      // Step 2: Copy chart of accounts from previous fiscal year
      // This automatically finds the most recent previous fiscal year
      showMessage('Räkenskapsår skapat! Kopierar kontoplan från föregående år...', 'success')

      try {
        const copyResponse = await fiscalYearApi.copyChartOfAccounts(newFiscalYearId)
        showMessage(`Räkenskapsår och kontoplan skapade! ${copyResponse.data.accounts_copied} konton kopierade från ${copyResponse.data.source_fiscal_year_label}.`, 'success')
      } catch (copyError: any) {
        console.error('Failed to copy chart of accounts:', copyError)
        const errorDetail = copyError.response?.data?.detail || 'Kunde inte kopiera kontoplan'
        showMessage(`Räkenskapsår skapat, men ${errorDetail}. Du kan importera BAS-kontoplan manuellt i fliken "Import".`, 'error')
      }

      await loadData()
      setShowCreateFiscalYear(false)
      // Reset to next year defaults after creating
      setTimeout(() => {
        setNewFiscalYear(getNextFiscalYearDefaults())
      }, 100)
    } catch (error: any) {
      console.error('Failed to create fiscal year:', error)
      showMessage(error.response?.data?.detail || 'Kunde inte skapa räkenskapsår', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteFiscalYear = async (fiscalYearId: number, label: string) => {
    const accountCount = accountCountsByFiscalYear[fiscalYearId] || 0
    let confirmMessage = `Är du säker på att du vill radera räkenskapsåret "${label}"?`

    if (accountCount > 0) {
      confirmMessage = `VARNING: Räkenskapsåret "${label}" har ${accountCount} konton som kommer att raderas permanent.\n\nÄr du säker på att du vill fortsätta?`
    } else {
      confirmMessage += ' Verifikationer kommer att kopplas loss.'
    }

    if (!confirm(confirmMessage)) {
      return
    }

    try {
      setLoading(true)
      await fiscalYearApi.delete(fiscalYearId)
      showMessage('Räkenskapsår raderat', 'success')
      await loadData()
    } catch (error: any) {
      console.error('Failed to delete fiscal year:', error)
      showMessage('Kunde inte radera räkenskapsår', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAssignVerifications = async (fiscalYearId: number, label: string) => {
    if (!confirm(`Tilldela alla verifikationer till räkenskapsår "${label}" baserat på transaktionsdatum?`)) {
      return
    }

    try {
      setLoading(true)
      const result = await fiscalYearApi.assignVerifications(fiscalYearId)
      showMessage(result.data.message, 'success')
      await loadData()
    } catch (error: any) {
      console.error('Failed to assign verifications:', error)
      showMessage('Kunde inte tilldela verifikationer', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleYearChange = (year: number) => {
    setNewFiscalYear({
      year,
      label: `${year}`,
      start_date: `${year}-01-01`,
      end_date: `${year}-12-31`,
    })
  }

  const handleToggleCreateForm = () => {
    if (!showCreateFiscalYear) {
      // Opening form - reset to defaults
      setNewFiscalYear(getNextFiscalYearDefaults())
    }
    setShowCreateFiscalYear(!showCreateFiscalYear)
  }

  const handleCreateTemplate = () => {
    setEditingTemplate(null)
    setTemplateForm({
      company_id: selectedCompany?.id || 0,
      name: '',
      description: '',
      default_series: '',
      default_journal_text: '',
      template_lines: [{
        account_number: 0,
        formula: '{total}',
        description: '',
        sort_order: 0
      }]
    })
    setShowCreateTemplate(true)
  }

  const handleEditTemplate = async (template: PostingTemplate) => {
    if (!selectedCompany || !template.id) return

    try {
      const response = await postingTemplateApi.get(template.id)
      setEditingTemplate(template)
      setTemplateForm(response.data)
      setShowCreateTemplate(true)
    } catch (error) {
      showMessage('Kunde inte ladda mall', 'error')
    }
  }

  const handleSaveTemplate = async () => {
    if (!selectedCompany) return

    if (!templateForm.name || !templateForm.description || templateForm.template_lines.length === 0) {
      showMessage('Fyll i alla obligatoriska fält', 'error')
      return
    }

    // Validate template lines
    for (const line of templateForm.template_lines) {
      if (!line.account_number || !line.formula) {
        showMessage('Alla rader måste ha konto och formel', 'error')
        return
      }
    }

    try {
      setLoading(true)

      if (editingTemplate && editingTemplate.id) {
        await postingTemplateApi.update(editingTemplate.id, templateForm)
        showMessage('Mall uppdaterad', 'success')
      } else {
        await postingTemplateApi.create(templateForm)
        showMessage('Mall skapad', 'success')
      }

      setShowCreateTemplate(false)
      setEditingTemplate(null)
      loadData()
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Kunde inte spara mall', 'error')
    } finally {
      setLoading(false)
    }
  }

  const addTemplateLine = () => {
    setTemplateForm(prev => ({
      ...prev,
      template_lines: [...prev.template_lines, {
        account_number: 0,
        formula: '{total}',
        description: '',
        sort_order: prev.template_lines.length
      }]
    }))
  }

  const removeTemplateLine = (index: number) => {
    setTemplateForm(prev => ({
      ...prev,
      template_lines: prev.template_lines.filter((_, i) => i !== index)
    }))
  }

  const updateTemplateLine = (index: number, field: keyof PostingTemplateLine, value: any) => {
    setTemplateForm(prev => ({
      ...prev,
      template_lines: prev.template_lines.map((line, i) => 
        i === index ? { ...line, [field]: value } : line
      )
    }))
  }

  // Simple drag and drop state
  const [draggedTemplate, setDraggedTemplate] = useState<PostingTemplate | null>(null)
  const [dropIndicator, setDropIndicator] = useState<{ templateId: number; position: 'before' | 'after' } | null>(null)

  const handleDragStart = (e: any, template: PostingTemplate) => {
    setDraggedTemplate(template)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', template.id?.toString() || '')
  }

  const handleDragEnd = () => {
    setDraggedTemplate(null)
    setDropIndicator(null)
  }

  const handleDragOver = (e: any, template: PostingTemplate) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'

    if (!draggedTemplate || !template.id || draggedTemplate.id === template.id) return

    // Calculate if drop should be before or after based on mouse position
    const rect = e.currentTarget.getBoundingClientRect()
    const midY = rect.top + rect.height / 2
    const position = e.clientY < midY ? 'before' : 'after'

    setDropIndicator({ templateId: template.id, position })
  }

  const handleDragLeave = (e: any) => {
    // Only clear if we're leaving the container entirely
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX
    const y = e.clientY
    
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      setDropIndicator(null)
    }
  }

  const handleDrop = async (e: any, targetTemplate: PostingTemplate) => {
    e.preventDefault()

    if (!draggedTemplate || !selectedCompany || draggedTemplate.id === targetTemplate.id || !dropIndicator) {
      handleDragEnd()
      return
    }

    const sortedTemplates = templates.sort((a: any, b: any) => (a.sort_order || 999) - (b.sort_order || 999))
    const draggedIndex = sortedTemplates.findIndex((t: any) => t.id === draggedTemplate.id)
    const targetIndex = sortedTemplates.findIndex((t: any) => t.id === targetTemplate.id)

    if (draggedIndex === -1 || targetIndex === -1) {
      handleDragEnd()
      return
    }

    // Calculate the insertion point based on drop indicator
    let insertIndex = targetIndex
    if (dropIndicator.position === 'after') {
      insertIndex = targetIndex + 1
    }

    // Adjust for removal of dragged item
    if (draggedIndex < insertIndex) {
      insertIndex -= 1
    }

    // Create reordered list
    const reorderedTemplates = Array.from(sortedTemplates)
    const [movedTemplate] = reorderedTemplates.splice(draggedIndex, 1)
    reorderedTemplates.splice(insertIndex, 0, movedTemplate)

    // Update local state immediately for smooth UX
    setTemplates(reorderedTemplates)
    handleDragEnd()

    try {
      // Create the new order array with sort_order values
      const templateOrders = reorderedTemplates.map((template: any, index: number) => ({
        id: template.id,
        sort_order: index + 1
      }))

      await postingTemplateApi.reorder(selectedCompany.id, templateOrders)
      showMessage('Ordning uppdaterad', 'success')
    } catch (error: any) {
      // Revert the local change if API call fails
      setTemplates(templates)
      showMessage('Kunde inte uppdatera ordning', 'error')
    }
  }

  if (!selectedCompany && !loading) {
    return (
      <div className="card">
        <h2 className="text-2xl font-bold mb-4">Inställningar</h2>
        <p className="text-gray-600">
          Inget företag hittat. Skapa ett företag först.
        </p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <h1 className="text-3xl font-bold">Inställningar</h1>
        <FiscalYearSelector />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('company')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'company'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Företag
          </button>
          <button
            onClick={() => setActiveTab('fiscal')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'fiscal'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Räkenskapsår
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'templates'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Konteringsmallar
          </button>
          <button
            onClick={() => setActiveTab('import')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'import'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Import/Export
          </button>
          <button
            onClick={() => setActiveTab('layout')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'layout'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Utseende
          </button>
        </nav>
      </div>

      {message && (
        <div
          className={`mb-4 p-4 rounded ${
            messageType === 'success'
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          <pre className="whitespace-pre-wrap font-sans text-sm">{message}</pre>
        </div>
      )}

      {/* Company Tab */}
      {activeTab === 'company' && (
        <div>
          {/* Company Management Section */}
          <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Building2 className="w-5 h-5" />
            Företagsinformation
          </h2>
          <div className="flex gap-2">
            {!editingCompany && !showCreateCompany && (
              <>
                <button
                  onClick={startEditCompany}
                  disabled={loading}
                  className="btn btn-secondary flex items-center gap-2"
                >
                  <Edit2 className="w-4 h-4" />
                  Redigera
                </button>
                <button
                  onClick={() => setShowCreateCompany(true)}
                  disabled={loading}
                  className="btn btn-primary flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Nytt företag
                </button>
              </>
            )}
          </div>
        </div>

        {/* View Mode */}
        {!editingCompany && !showCreateCompany && selectedCompany && (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Grunduppgifter</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Företagsnamn</label>
                  <p className="text-gray-900">{selectedCompany.name}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Organisationsnummer</label>
                  <p className="text-gray-900">{selectedCompany.org_number}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">VAT-nummer</label>
                  <p className="text-gray-900">{selectedCompany.vat_number || '-'}</p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Kontaktuppgifter</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Adress</label>
                  <p className="text-gray-900">{selectedCompany.address || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Postnummer</label>
                  <p className="text-gray-900">{selectedCompany.postal_code || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Stad</label>
                  <p className="text-gray-900">{selectedCompany.city || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Telefon</label>
                  <p className="text-gray-900">{selectedCompany.phone || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">E-post</label>
                  <p className="text-gray-900">{selectedCompany.email || '-'}</p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Bokföringsinställningar</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Räkenskapsår start</label>
                  <p className="text-gray-900">{selectedCompany.fiscal_year_start}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Räkenskapsår slut</label>
                  <p className="text-gray-900">{selectedCompany.fiscal_year_end}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bokföringsmetod</label>
                  <p className="text-gray-900">
                    {selectedCompany.accounting_basis === 'accrual' ? 'Bokföringsmässiga grunder' : 'Kontantmetoden'}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Momsredovisning</label>
                  <p className="text-gray-900">
                    {selectedCompany.vat_reporting_period === 'monthly' ? 'Månadsvis' :
                     selectedCompany.vat_reporting_period === 'quarterly' ? 'Kvartalsvis' : 'Årlig'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Edit/Create Mode */}
        {(editingCompany || showCreateCompany) && (
          <div className="space-y-6">
            {/* Grunduppgifter */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Grunduppgifter</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Företagsnamn *
                  </label>
                  <input
                    type="text"
                    value={companyForm.name}
                    onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Organisationsnummer *
                  </label>
                  <input
                    type="text"
                    value={companyForm.org_number}
                    onChange={(e) => setCompanyForm({ ...companyForm, org_number: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="123456-7890 eller 1234567890"
                    pattern="^\d{6}-?\d{4}$"
                    required
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    10 siffror, med eller utan bindestreck (t.ex. 123456-7890)
                  </p>
                </div>
              </div>
            </div>

            {/* Kontaktuppgifter */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Kontaktuppgifter</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Adress</label>
                  <input
                    type="text"
                    value={companyForm.address}
                    onChange={(e) => setCompanyForm({ ...companyForm, address: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="Gatunamn 123"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Postnummer</label>
                  <input
                    type="text"
                    value={companyForm.postal_code}
                    onChange={(e) => setCompanyForm({ ...companyForm, postal_code: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="123 45"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Stad</label>
                  <input
                    type="text"
                    value={companyForm.city}
                    onChange={(e) => setCompanyForm({ ...companyForm, city: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="Stockholm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Telefon</label>
                  <input
                    type="tel"
                    value={companyForm.phone}
                    onChange={(e) => setCompanyForm({ ...companyForm, phone: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="08-123 456 78"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">E-post</label>
                  <input
                    type="email"
                    value={companyForm.email}
                    onChange={(e) => setCompanyForm({ ...companyForm, email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="info@företag.se"
                  />
                </div>
              </div>
            </div>

            {/* Bokföringsinställningar */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Bokföringsinställningar</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Räkenskapsår start *
                  </label>
                  <input
                    type="date"
                    value={companyForm.fiscal_year_start}
                    onChange={(e) => setCompanyForm({ ...companyForm, fiscal_year_start: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Räkenskapsår slut *
                  </label>
                  <input
                    type="date"
                    value={companyForm.fiscal_year_end}
                    onChange={(e) => setCompanyForm({ ...companyForm, fiscal_year_end: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Bokföringsmetod
                  </label>
                  <select
                    value={companyForm.accounting_basis}
                    onChange={(e) => setCompanyForm({ ...companyForm, accounting_basis: e.target.value as AccountingBasis })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="accrual">Bokföringsmässiga grunder</option>
                    <option value="cash">Kontantmetoden</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Momsredovisningsperiod
                  </label>
                  <select
                    value={companyForm.vat_reporting_period}
                    onChange={(e) => setCompanyForm({ ...companyForm, vat_reporting_period: e.target.value as VATReportingPeriod })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="monthly">Månadsvis</option>
                    <option value="quarterly">Kvartalsvis</option>
                    <option value="yearly">Årlig</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t">
              <button
                onClick={editingCompany ? handleUpdateCompany : handleCreateCompany}
                disabled={loading || !companyForm.name || !companyForm.org_number}
                className="btn btn-primary flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                {editingCompany ? 'Spara ändringar' : 'Skapa företag'}
              </button>
              <button
                onClick={editingCompany ? cancelEditCompany : () => setShowCreateCompany(false)}
                disabled={loading}
                className="btn btn-secondary flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                Avbryt
              </button>
            </div>
          </div>
        )}

        {/* List of all companies */}
        {companies.length > 1 && !editingCompany && !showCreateCompany && (
          <div className="mt-6 pt-6 border-t">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Alla företag ({companies.length})</h3>
            <div className="space-y-2">
              {companies.map((company) => (
                <div
                  key={company.id}
                  className={`flex items-center justify-between p-3 rounded-lg border ${
                    selectedCompany?.id === company.id
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div>
                    <p className="font-medium text-gray-900">{company.name}</p>
                    <p className="text-sm text-gray-600">Org.nr: {company.org_number}</p>
                  </div>
                  {selectedCompany?.id !== company.id && (
                    <button
                      onClick={() => setSelectedCompany(company)}
                      className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                    >
                      Välj
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* VAT Reporting Period Section */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Momsredovisningsperiod</h2>
        <p className="text-gray-600 mb-4">
          Välj hur ofta ditt företag ska redovisa moms till Skatteverket.
        </p>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            {/* Monthly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'monthly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="monthly"
                checked={selectedCompany?.vat_reporting_period === 'monthly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Månadsvis</div>
                <div className="text-sm text-gray-600 mt-1">
                  För företag med omsättning över 40 miljoner SEK/år. Deklarera varje månad.
                </div>
              </div>
            </label>

            {/* Quarterly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'quarterly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="quarterly"
                checked={selectedCompany?.vat_reporting_period === 'quarterly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Kvartalsvis (Rekommenderat)</div>
                <div className="text-sm text-gray-600 mt-1">
                  Vanligast för små och medelstora företag. Deklarera varje kvartal.
                </div>
              </div>
            </label>

            {/* Yearly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'yearly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="yearly"
                checked={selectedCompany?.vat_reporting_period === 'yearly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Årlig</div>
                <div className="text-sm text-gray-600 mt-1">
                  För företag med omsättning under 1 miljon SEK/år. Deklarera en gång per år.
                </div>
              </div>
            </label>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <p className="text-sm text-blue-800">
              <strong>OBS:</strong> Kontakta Skatteverket om du är osäker på vilken redovisningsperiod
              som gäller för ditt företag. Detta påverkar hur ofta du måste lämna momsdeklaration.
            </p>
          </div>
        </div>
      </div>

          {/* Company Logo Section */}
          {selectedCompany && (
            <div className="card mb-6">
              <h2 className="text-xl font-semibold mb-4">Företagslogotyp</h2>
              <div className="flex items-start space-x-6">
                {selectedCompany.logo_filename ? (
                  <div className="flex-shrink-0">
                    <div className="relative">
                      <img
                        src={companyApi.getLogo(selectedCompany.id)}
                        alt="Företagslogotyp"
                        className="w-40 h-40 object-contain border-2 border-gray-300 rounded-lg bg-white shadow-sm"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement
                          target.style.display = 'none'
                        }}
                      />
                      <div className="absolute -top-2 -right-2 bg-green-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">
                        ✓
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-shrink-0">
                    <div className="w-40 h-40 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center bg-gray-50">
                      <Image className="w-12 h-12 text-gray-400 mb-2" />
                      <span className="text-sm text-gray-500 text-center">Ingen logotyp<br/>uppladdad</span>
                    </div>
                  </div>
                )}
                <div className="flex-1">
                  <div className="flex flex-col space-y-3">
                    <label className="btn btn-primary cursor-pointer inline-flex items-center w-fit">
                      <Upload className="w-4 h-4 mr-2" />
                      {uploadingLogo ? 'Laddar upp...' : (selectedCompany.logo_filename ? 'Byt logotyp' : 'Ladda upp logotyp')}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/jpg"
                        onChange={handleLogoUpload}
                        disabled={uploadingLogo}
                        className="hidden"
                      />
                    </label>
                    {selectedCompany.logo_filename && (
                      <button
                        onClick={handleLogoDelete}
                        disabled={uploadingLogo}
                        className="btn btn-outline-danger w-fit inline-flex items-center"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Ta bort logotyp
                      </button>
                    )}
                  </div>
                  <div className="mt-3">
                    <p className="text-sm text-gray-600 mb-1">
                      Rekommenderad storlek: 200x200 pixlar eller större
                    </p>
                    <p className="text-sm text-gray-500">
                      Filformat: PNG eller JPG, max 5MB
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Import/Export Tab */}
      {activeTab === 'import' && (
        <div>
          {/* Backup Section */}
          <div className="card mb-6">
            <div className="flex items-center gap-2 mb-4">
              <HardDrive className="w-5 h-5 text-gray-600" />
              <h2 className="text-xl font-semibold">Systembackup</h2>
            </div>
            <p className="text-gray-600 mb-4">
              Skapa fullständiga backups av hela systemet, inklusive databas och bilagor.
            </p>

            {/* Create Backup */}
            <div className="mb-6">
              <button
                onClick={handleCreateBackup}
                disabled={creatingBackup || loading}
                className="btn btn-primary inline-flex items-center"
              >
                {creatingBackup ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Skapar backup...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Skapa och ladda ner backup
                  </>
                )}
              </button>
            </div>

            {/* Backup List */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-700">Backups på servern</h3>
                <button
                  onClick={loadBackups}
                  disabled={loadingBackups}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  {loadingBackups ? 'Laddar...' : 'Uppdatera'}
                </button>
              </div>

              {loadingBackups ? (
                <div className="text-center py-4 text-gray-500">
                  <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  Laddar backups...
                </div>
              ) : backups.length === 0 ? (
                <div className="text-center py-4 text-gray-500">
                  <p>Inga backups på servern.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Skapad</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Version</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Schema</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Storlek</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Åtgärder</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {backups.map((backup) => (
                        <tr key={backup.filename} className="hover:bg-gray-50">
                          <td className="px-3 py-2 text-sm text-gray-900">
                            {formatBackupDate(backup.created_at)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-600">{backup.app_version}</td>
                          <td className="px-3 py-2 text-sm text-gray-600">{backup.schema_version}</td>
                          <td className="px-3 py-2 text-sm text-gray-600">
                            {formatFileSize(backup.size_bytes)}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleDownloadBackup(backup.filename)}
                                disabled={downloadingBackup === backup.filename}
                                className="text-blue-600 hover:text-blue-800 p-1"
                                title="Ladda ner"
                              >
                                {downloadingBackup === backup.filename ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Download className="w-4 h-4" />
                                )}
                              </button>
                              <button
                                onClick={() => setShowRestoreModal(true)}
                                className="text-amber-600 hover:text-amber-800 p-1"
                                title="Återställ"
                              >
                                <RotateCcw className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Restore Button */}
            <div className="border-t mt-4 pt-4">
              <button
                onClick={() => setShowRestoreModal(true)}
                className="btn btn-secondary inline-flex items-center"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                Återställ från backup
              </button>
              <p className="mt-2 text-sm text-gray-500">
                Återställ systemet från en backup på servern eller ladda upp en backup-fil.
              </p>
            </div>

            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded">
              <p className="text-sm text-amber-800">
                <strong>Varning:</strong> Återställning ersätter ALL data i systemet. Skapa alltid en backup
                av nuvarande data innan du återställer.
              </p>
            </div>
          </div>

          {/* SIE4 Import/Export Section */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">SIE4 Import/Export</h2>
        <p className="text-gray-600 mb-4">
          Importera eller exportera kontoplan och verifikationer i SIE4-format.
        </p>

        <div className="space-y-4">
          {/* Import */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Importera SIE4-fil
            </label>
            <input
              type="file"
              accept=".se,.si"
              onChange={handleSIE4Import}
              disabled={loading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100
                disabled:opacity-50"
            />
            <p className="mt-1 text-sm text-gray-500">
              Konton och ingående balanser kommer importeras och standardkonton konfigureras automatiskt.
            </p>
          </div>

          {/* Export */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Exportera till SIE4
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => handleSIE4Export(true)}
                disabled={loading}
                className="btn btn-primary"
              >
                Exportera med verifikationer
              </button>
              <button
                onClick={() => handleSIE4Export(false)}
                disabled={loading}
                className="btn btn-secondary"
              >
                Endast kontoplan
              </button>
            </div>
          </div>
        </div>
      </div>
        </div>
      )}

      {/* Fiscal Years Tab */}
      {activeTab === 'fiscal' && (
        <div>
          {/* Fiscal Years Section */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Räkenskapsår</h2>
          <button
            onClick={handleToggleCreateForm}
            disabled={loading}
            className="btn btn-primary inline-flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            Lägg till räkenskapsår
          </button>
        </div>

        <p className="text-gray-600 mb-4">
          Hantera räkenskapsår för att kunna filtrera verifikationer och rapporter per period.
        </p>

        {/* Create Fiscal Year Form */}
        {showCreateFiscalYear && (
          <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
            <h3 className="font-medium mb-3">Skapa nytt räkenskapsår</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">År</label>
                <input
                  type="number"
                  value={newFiscalYear.year}
                  onChange={(e) => handleYearChange(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Benämning</label>
                <input
                  type="text"
                  placeholder="t.ex. 2024"
                  value={newFiscalYear.label}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, label: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Automatiskt ifylld med året</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Startdatum</label>
                <input
                  type="date"
                  value={newFiscalYear.start_date}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, start_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Standard: 1 januari</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Slutdatum</label>
                <input
                  type="date"
                  value={newFiscalYear.end_date}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, end_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Standard: 31 december</p>
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={handleCreateFiscalYear}
                disabled={loading}
                className="btn btn-primary"
              >
                Skapa
              </button>
              <button
                onClick={() => setShowCreateFiscalYear(false)}
                disabled={loading}
                className="btn btn-secondary"
              >
                Avbryt
              </button>
            </div>
          </div>
        )}

        {/* Fiscal Years List */}
        {fiscalYears.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Calendar className="w-12 h-12 mx-auto mb-3 text-gray-400" />
            <p className="mb-4">Inga räkenskapsår konfigurerade.</p>
            <p className="text-sm">
              Skapa ett räkenskapsår för att kunna se verifikationer och rapporter per period.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {fiscalYears.map((fy) => (
              <div
                key={fy.id}
                className={`flex items-center justify-between p-3 border rounded-lg ${
                  fy.is_current ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{fy.label}</span>
                    {fy.is_current && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded">
                        Aktuellt
                      </span>
                    )}
                    {fy.is_closed && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded">
                        Stängt
                      </span>
                    )}
                    <span className="px-2 py-0.5 text-xs font-medium bg-gray-50 text-gray-600 rounded">
                      {accountCountsByFiscalYear[fy.id] || 0} konton
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mt-1">
                    {fy.start_date} till {fy.end_date}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAssignVerifications(fy.id, fy.label)}
                    disabled={loading}
                    className="btn btn-secondary text-sm"
                  >
                    Tilldela verifikationer
                  </button>
                  <button
                    onClick={() => handleDeleteFiscalYear(fy.id, fy.label)}
                    disabled={loading}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
          <p className="text-sm text-blue-800">
            <strong>Tips:</strong> Skapa räkenskapsår för varje år du har bokfört. Använd "Tilldela verifikationer" för att
            automatiskt koppla verifikationer till rätt år baserat på transaktionsdatum.
          </p>
        </div>
      </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div>
          {/* Posting Templates Section */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Konteringsmallar</h2>
          <button
            onClick={handleCreateTemplate}
            disabled={loading}
            className="btn btn-primary inline-flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            Skapa mall
          </button>
        </div>
        

        {templates.length > 0 ? (
          <div className="space-y-2">
            {templates
              .sort((a: any, b: any) => (a.sort_order || 999) - (b.sort_order || 999))
              .map((template: any) => (
                <div key={template.id} className="relative">
                  {/* Drop indicator line BEFORE this template */}
                  {dropIndicator?.templateId === template.id && dropIndicator?.position === 'before' && (
                    <div className="absolute -top-1 left-0 right-0 h-0.5 bg-blue-500 rounded-full shadow-sm z-10" />
                  )}
                  
                  <div
                    draggable
                    onDragStart={(e) => handleDragStart(e, template)}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOver(e, template)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, template)}
                    className={`flex items-center justify-between p-3 border rounded-lg transition-all duration-200 cursor-move relative ${
                      draggedTemplate?.id === template.id 
                        ? 'bg-blue-50 border-blue-300 shadow-lg opacity-50' 
                        : 'bg-white hover:bg-gray-50 hover:shadow-sm border-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing"
                      >
                        <GripVertical className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="font-medium">{template.name}</h3>
                        <p className="text-sm text-gray-500">{template.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEditTemplate(template)}
                        className="text-blue-600 hover:text-blue-800 p-1 rounded"
                        title="Redigera mall (dra handtaget för att ändra ordning)"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={async () => {
                          if (!selectedCompany || !confirm(`Är du säker på att du vill radera mallen "${template.name}"?`)) return

                          try {
                            await postingTemplateApi.delete(template.id)
                            setTemplates((prev: any) => prev.filter((t: any) => t.id !== template.id))
                            showMessage('Mall raderad', 'success')
                          } catch (error: any) {
                            showMessage('Kunde inte radera mall', 'error')
                          }
                        }}
                        className="text-red-600 hover:text-red-800 p-1 rounded"
                        title="Radera mall"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Drop indicator line AFTER this template */}
                  {dropIndicator?.templateId === template.id && dropIndicator?.position === 'after' && (
                    <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-blue-500 rounded-full shadow-sm z-10" />
                  )}
                </div>
              ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <p className="mb-4">Inga konteringsmallar skapade ännu.</p>
            <button
              onClick={handleCreateTemplate}
              className="btn btn-primary"
            >
              Skapa din första mall
            </button>
          </div>
        )}

        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
          <p className="text-sm text-blue-800">
            <strong>Tips:</strong> Skapa mallar för återkommande transaktioner som försäljning, inköp, eller lönutbetalningar.
            Använd formler som {'{amount * 0.25}'} för att automatiska beräkningar.
          </p>
        </div>
      </div>
        </div>
      )}

      {/* Import Summary Modal */}
      {showImportSummary && importSummary && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center mb-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="ml-4 text-lg font-semibold text-gray-900">Import Lyckades!</h3>
              </div>

              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Importsammanfattning:</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Konton skapade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.accounts_created}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Konton uppdaterade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.accounts_updated}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
                    <span className="text-sm text-gray-700">Verifikationer importerade:</span>
                    <span className="text-sm font-semibold text-blue-900">{importSummary.verifications_created}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Standardkonton konfigurerade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.default_accounts_configured}</span>
                  </div>
                </div>

                {/* Errors */}
                {importSummary.errors && importSummary.errors.length > 0 && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                    <h5 className="text-sm font-medium text-red-900 mb-2">Fel:</h5>
                    <ul className="list-disc list-inside space-y-1">
                      {importSummary.errors.map((error, idx) => (
                        <li key={idx} className="text-sm text-red-800">{error}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warnings */}
                {importSummary.warnings && importSummary.warnings.length > 0 && (
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                    <h5 className="text-sm font-medium text-yellow-900 mb-2">Varningar:</h5>
                    <ul className="list-disc list-inside space-y-1">
                      {importSummary.warnings.map((warning, idx) => (
                        <li key={idx} className="text-sm text-yellow-800">{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {importSummary.verifications_created > 0 && (
                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                    <p className="text-sm text-blue-800">
                      <strong>Tips:</strong> Glöm inte att tilldela verifikationerna till räkenskapsår!
                      Scrolla ner till "Räkenskapsår" och klicka "Tilldela verifikationer".
                    </p>
                  </div>
                )}
              </div>

              <button
                onClick={() => setShowImportSummary(false)}
                className="w-full btn btn-primary"
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Template Modal */}
      {showCreateTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-900">
                  {editingTemplate ? 'Redigera mall' : 'Skapa ny mall'}
                </h3>
                <button
                  onClick={() => setShowCreateTemplate(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Namn *
                  </label>
                  <input
                    type="text"
                    value={templateForm.name}
                    onChange={(e) => setTemplateForm(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="t.ex. Inköp med 25% moms"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Beskrivning *
                  </label>
                  <input
                    type="text"
                    value={templateForm.description}
                    onChange={(e) => setTemplateForm(prev => ({ ...prev, description: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="t.ex. Försäljning med 25% moms"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Standard verifikationsserie
                  </label>
                  <input
                    type="text"
                    value={templateForm.default_series || ''}
                    onChange={(e) => setTemplateForm(prev => ({ ...prev, default_series: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="t.ex. A"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Standard verifikationstext
                  </label>
                  <input
                    type="text"
                    value={templateForm.default_journal_text || ''}
                    onChange={(e) => setTemplateForm(prev => ({ ...prev, default_journal_text: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="t.ex. Försäljning"
                  />
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-md font-medium text-gray-900">Konteringsrader</h4>
                  <button
                    onClick={addTemplateLine}
                    className="inline-flex items-center px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Lägg till rad
                  </button>
                </div>

                {templateForm.template_lines.length === 0 ? (
                  <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center">
                    <div className="text-gray-500 mb-2">
                      <Plus className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                      Inga konteringsrader ännu
                    </div>
                    <p className="text-sm text-gray-500 mb-4">
                      Lägg till minst en konteringsrad för att skapa mallen
                    </p>
                    <button
                      onClick={addTemplateLine}
                      className="inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Lägg till första raden
                    </button>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full border border-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 w-12">
                            #
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                            Konto *
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                            Formel *
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 hidden sm:table-cell">
                            Beskrivning
                          </th>
                          <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 w-16">
                            Åtgärd
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {templateForm.template_lines.map((line, index) => (
                          <tr key={index}>
                            <td className="px-4 py-2 text-sm font-medium text-gray-700">
                              {index + 1}
                            </td>
                            <td className="px-4 py-2">
                              <select
                                value={line.account_number}
                                onChange={(e) => updateTemplateLine(index, 'account_number', parseInt(e.target.value))}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                              >
                                <option value={0}>Välj konto...</option>
                                {allAccounts.map((account) => (
                                  <option key={account.account_number} value={account.account_number}>
                                    {account.account_number} - {account.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-4 py-2">
                              <input
                                type="text"
                                value={line.formula}
                                onChange={(e) => updateTemplateLine(index, 'formula', e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
                                placeholder="{total}"
                              />
                            </td>
                            <td className="px-4 py-2 hidden sm:table-cell">
                              <input
                                type="text"
                                value={line.description || ''}
                                onChange={(e) => updateTemplateLine(index, 'description', e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                placeholder="Beskrivning..."
                              />
                            </td>
                            <td className="px-4 py-2 text-center">
                              {templateForm.template_lines.length > 1 && (
                                <button
                                  onClick={() => removeTemplateLine(index)}
                                  className="text-red-600 hover:text-red-800"
                                  title="Ta bort rad"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                  <p className="text-sm text-blue-800">
                    <strong>Formel-tips:</strong> Använd <code>{'{total}'}</code> som variabel i formler. Exempel: <code>{'{total} * 0.25'}</code> för 25% moms, <code>{'{total} * -1'}</code> för negativt belopp, <code>{'100'}</code> för fast belopp.
                  </p>
                  <p className="text-sm text-blue-800 mt-2">
                    Positiva värden bokförs som <strong>debet</strong>, 
                    negativa värden som <strong>kredit</strong>.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowCreateTemplate(false)}
                  className="btn btn-secondary"
                  disabled={loading}
                >
                  Avbryt
                </button>
                <button
                  onClick={handleSaveTemplate}
                  disabled={loading}
                  className="btn btn-primary"
                >
                  {loading ? 'Sparar...' : (editingTemplate ? 'Uppdatera' : 'Skapa')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Layout Tab */}
      {activeTab === 'layout' && (
        <div>
          <div className="card mb-6">
            <div className="flex items-center gap-2 mb-4">
              <Layout className="w-5 h-5 text-gray-600" />
              <h2 className="text-xl font-semibold">Utseende</h2>
            </div>

            {/* Split View Settings */}
            <div className="mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-2">Delad vy</h3>
              <p className="text-gray-600 mb-4">
                Välj på vilken sida bilagor ska visas när du använder delad vy i verifikationer och fakturor.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl">
                <label className={`flex flex-col p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                  layoutSettings.splitViewAttachmentSide === 'left'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <div className="flex items-start">
                    <input
                      type="radio"
                      name="splitViewAttachmentSide"
                      value="left"
                      checked={layoutSettings.splitViewAttachmentSide === 'left'}
                      onChange={() => updateLayoutSettings({ splitViewAttachmentSide: 'left' })}
                      className="mt-1 mr-3"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">Bilagor till vänster</div>
                      <div className="text-sm text-gray-600 mt-1">
                        Bilagan visas på vänster sida, formuläret på höger
                      </div>
                    </div>
                  </div>
                  {/* Visual diagram */}
                  <div className="mt-3 flex gap-1 h-12 rounded overflow-hidden border border-gray-300">
                    <div className={`flex-1 flex items-center justify-center text-xs font-medium ${
                      layoutSettings.splitViewAttachmentSide === 'left' ? 'bg-blue-200 text-blue-800' : 'bg-gray-200 text-gray-600'
                    }`}>
                      Bilaga
                    </div>
                    <div className={`flex-1 flex items-center justify-center text-xs font-medium ${
                      layoutSettings.splitViewAttachmentSide === 'left' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      Formulär
                    </div>
                  </div>
                </label>

                <label className={`flex flex-col p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                  layoutSettings.splitViewAttachmentSide === 'right'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <div className="flex items-start">
                    <input
                      type="radio"
                      name="splitViewAttachmentSide"
                      value="right"
                      checked={layoutSettings.splitViewAttachmentSide === 'right'}
                      onChange={() => updateLayoutSettings({ splitViewAttachmentSide: 'right' })}
                      className="mt-1 mr-3"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">Bilagor till höger</div>
                      <div className="text-sm text-gray-600 mt-1">
                        Bilagan visas på höger sida, formuläret på vänster
                      </div>
                    </div>
                  </div>
                  {/* Visual diagram */}
                  <div className="mt-3 flex gap-1 h-12 rounded overflow-hidden border border-gray-300">
                    <div className={`flex-1 flex items-center justify-center text-xs font-medium ${
                      layoutSettings.splitViewAttachmentSide === 'right' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      Formulär
                    </div>
                    <div className={`flex-1 flex items-center justify-center text-xs font-medium ${
                      layoutSettings.splitViewAttachmentSide === 'right' ? 'bg-blue-200 text-blue-800' : 'bg-gray-200 text-gray-600'
                    }`}>
                      Bilaga
                    </div>
                  </div>
                </label>
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <p className="text-sm text-blue-800">
                <strong>Tips:</strong> Aktivera delad vy genom att klicka på pin-ikonen i verifikations- eller fakturaformuläret
                när du har en bilaga vald.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Restore Modal */}
      <RestoreModal
        isOpen={showRestoreModal}
        onClose={() => setShowRestoreModal(false)}
        backups={backups}
      />

    </div>
  )
}
