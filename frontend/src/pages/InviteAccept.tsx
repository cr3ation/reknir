import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Building2, UserCheck, AlertCircle, CheckCircle } from 'lucide-react'
import api from '../services/api'

interface InvitationValidation {
  valid: boolean
  company_name?: string
  role?: string
  message?: string
}

export default function InviteAccept() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [validation, setValidation] = useState<InvitationValidation | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    password_confirm: ''
  })
  const [error, setError] = useState('')

  useEffect(() => {
    if (token) {
      validateToken()
    }
  }, [token])

  const validateToken = async () => {
    try {
      const response = await api.get(`/api/invitations/validate/${token}`)
      setValidation(response.data)
    } catch (error) {
      setValidation({
        valid: false,
        message: 'Kunde inte validera inbjudan'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validate passwords match
    if (formData.password !== formData.password_confirm) {
      setError('Lösenorden matchar inte')
      return
    }

    // Validate password length
    if (formData.password.length < 6) {
      setError('Lösenordet måste vara minst 6 tecken')
      return
    }

    try {
      setSubmitting(true)
      await api.post(`/api/invitations/accept/${token}`, {
        full_name: formData.full_name,
        email: formData.email,
        password: formData.password
      })
      setSuccess(true)
      // Redirect to login after 2 seconds
      setTimeout(() => {
        navigate('/login')
      }, 2000)
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Kunde inte skapa konto')
    } finally {
      setSubmitting(false)
    }
  }

  const getRoleName = (role?: string) => {
    const roles: Record<string, string> = {
      user: 'Användare',
      accountant: 'Redovisare',
      manager: 'Chef'
    }
    return role ? roles[role] || role : ''
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Validerar inbjudan...</p>
        </div>
      </div>
    )
  }

  if (!validation?.valid) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Ogiltig inbjudan</h1>
          <p className="text-gray-600 mb-6">{validation?.message || 'Denna inbjudan är inte giltig'}</p>
          <button
            onClick={() => navigate('/login')}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            Gå till inloggning
          </button>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Konto skapat!</h1>
          <p className="text-gray-600 mb-4">
            Ditt konto har skapats och du har fått åtkomst till <strong>{validation.company_name}</strong>.
          </p>
          <p className="text-sm text-gray-500">
            Du omdirigeras till inloggningssidan...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <UserCheck className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Välkommen till Reknir!
          </h1>
          <p className="text-gray-600">
            Du har blivit inbjuden att gå med i
          </p>
        </div>

        {/* Company Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-3">
            <Building2 className="w-6 h-6 text-blue-600" />
            <div>
              <p className="font-semibold text-gray-900">{validation.company_name}</p>
              <p className="text-sm text-gray-600">
                Som <span className="font-medium">{getRoleName(validation.role)}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Registration Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Fullständigt namn
            </label>
            <input
              type="text"
              required
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ditt namn"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              E-postadress
            </label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="din@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Lösenord
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Minst 6 tecken"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Bekräfta lösenord
            </label>
            <input
              type="password"
              required
              value={formData.password_confirm}
              onChange={(e) => setFormData({ ...formData, password_confirm: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ange lösenordet igen"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 font-medium transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {submitting ? 'Skapar konto...' : 'Skapa konto och gå med'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Har du redan ett konto?{' '}
          <a href="/login" className="text-blue-600 hover:text-blue-700 font-medium">
            Logga in här
          </a>
        </p>
      </div>
    </div>
  )
}
