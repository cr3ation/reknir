import { useState, useEffect } from 'react'
import { UserPlus, Copy, Trash2, Check, Clock, ExternalLink } from 'lucide-react'
import api from '../services/api'
import { useCompany } from '../contexts/CompanyContext'

interface Invitation {
  id: number
  company_id: number
  role: string
  token: string
  expires_at: string
  used: boolean
  used_at: string | null
  created_at: string
}

export default function InvitationManager() {
  const { selectedCompany } = useCompany()
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newInvitation, setNewInvitation] = useState({
    role: 'user',
    days_valid: 7
  })
  const [copiedToken, setCopiedToken] = useState<string | null>(null)

  useEffect(() => {
    if (selectedCompany) {
      loadInvitations()
    }
  }, [selectedCompany])

  const loadInvitations = async () => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      const response = await api.get(`/api/invitations/company/${selectedCompany.id}`)
      setInvitations(response.data)
    } catch (error) {
      console.error('Failed to load invitations:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateInvitation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedCompany) return

    try {
      const response = await api.post('/api/invitations/', {
        company_id: selectedCompany.id,
        ...newInvitation
      })
      setInvitations([response.data, ...invitations])
      setShowCreateModal(false)
      setNewInvitation({ role: 'user', days_valid: 7 })
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to create invitation')
    }
  }

  const handleDeleteInvitation = async (invitationId: number) => {
    if (!confirm('Är du säker på att du vill ta bort denna inbjudan?')) return

    try {
      await api.delete(`/api/invitations/${invitationId}`)
      setInvitations(invitations.filter(inv => inv.id !== invitationId))
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete invitation')
    }
  }

  const copyInvitationLink = (token: string) => {
    const url = `${window.location.origin}/invite/${token}`
    navigator.clipboard.writeText(url)
    setCopiedToken(token)
    setTimeout(() => setCopiedToken(null), 2000)
  }

  const getRoleName = (role: string) => {
    const roles: Record<string, string> = {
      user: 'Användare',
      accountant: 'Redovisare',
      manager: 'Chef'
    }
    return roles[role] || role
  }

  const isExpired = (expiresAt: string) => {
    return new Date(expiresAt) < new Date()
  }

  if (!selectedCompany) {
    return (
      <div className="text-gray-500 text-center py-8">
        Välj ett företag för att hantera inbjudningar
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Inbjudningar</h2>
          <p className="text-gray-500 mt-1">
            Skapa inbjudningslänkar för att bjuda in användare till {selectedCompany.name}
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          <UserPlus className="w-5 h-5" />
          Skapa inbjudan
        </button>
      </div>

      {/* Invitations List */}
      {loading ? (
        <div className="text-center py-8 text-gray-500">Laddar inbjudningar...</div>
      ) : invitations.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg">
          <UserPlus className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-500">Inga inbjudningar ännu</p>
          <p className="text-sm text-gray-400 mt-1">
            Skapa en inbjudan för att bjuda in användare
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {invitations.map((invitation) => {
            const expired = isExpired(invitation.expires_at)
            const invitationUrl = `${window.location.origin}/invite/${invitation.token}`

            return (
              <div
                key={invitation.id}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded">
                        {getRoleName(invitation.role)}
                      </span>
                      {invitation.used ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <Check className="w-4 h-4" />
                          Använd
                        </span>
                      ) : expired ? (
                        <span className="flex items-center gap-1 text-xs text-red-600">
                          <Clock className="w-4 h-4" />
                          Utgången
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-gray-600">
                          <Clock className="w-4 h-4" />
                          Aktiv
                        </span>
                      )}
                    </div>

                    <div className="text-sm text-gray-600 mb-2">
                      {invitation.used ? (
                        <span>Använd {new Date(invitation.used_at!).toLocaleDateString('sv-SE')}</span>
                      ) : expired ? (
                        <span>Utgick {new Date(invitation.expires_at).toLocaleDateString('sv-SE')}</span>
                      ) : (
                        <span>Gäller till {new Date(invitation.expires_at).toLocaleDateString('sv-SE')}</span>
                      )}
                    </div>

                    {!invitation.used && !expired && (
                      <div className="flex items-center gap-2 mt-3">
                        <input
                          type="text"
                          value={invitationUrl}
                          readOnly
                          className="flex-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded text-sm font-mono"
                          onClick={(e) => e.currentTarget.select()}
                        />
                        <button
                          onClick={() => copyInvitationLink(invitation.token)}
                          className="flex items-center gap-1 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium transition-colors"
                        >
                          {copiedToken === invitation.token ? (
                            <>
                              <Check className="w-4 h-4 text-green-600" />
                              Kopierad
                            </>
                          ) : (
                            <>
                              <Copy className="w-4 h-4" />
                              Kopiera
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => handleDeleteInvitation(invitation.id)}
                    className="ml-4 text-red-600 hover:text-red-800"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create Invitation Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Skapa inbjudan</h2>
            <form onSubmit={handleCreateInvitation} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Roll
                </label>
                <select
                  value={newInvitation.role}
                  onChange={(e) => setNewInvitation({ ...newInvitation, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="user">Användare</option>
                  <option value="accountant">Redovisare</option>
                  <option value="manager">Chef</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Vilken roll ska den inbjudna användaren ha?
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Giltighetstid (dagar)
                </label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={newInvitation.days_valid}
                  onChange={(e) => setNewInvitation({ ...newInvitation, days_valid: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Hur länge ska inbjudan vara giltig?
                </p>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                  Skapa inbjudan
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300"
                >
                  Avbryt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
