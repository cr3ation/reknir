import { useState, useEffect } from 'react'
import { Users as UsersIcon, Plus, Building2, Trash2 } from 'lucide-react'
import api from '../services/api'
import { getErrorMessage } from '../utils/errors'

interface User {
  id: number
  email: string
  full_name: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

interface Company {
  id: number
  name: string
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([])
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [showCompanyModal, setShowCompanyModal] = useState(false)
  const [userCompanies, setUserCompanies] = useState<Company[]>([])

  // Form states
  const [newUser, setNewUser] = useState({
    email: '',
    full_name: '',
    password: ''
  })
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null)
  const [selectedRole, setSelectedRole] = useState('user')

  useEffect(() => {
    loadUsers()
    loadCompanies()
  }, [])

  const loadUsers = async () => {
    try {
      const response = await api.get('/auth/users')
      setUsers(response.data)
    } catch (error) {
      console.error('Failed to load users:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCompanies = async () => {
    try {
      const response = await api.get('/auth/me/companies')
      setCompanies(response.data)
    } catch (error) {
      console.error('Failed to load companies:', error)
    }
  }

  const loadUserCompanies = async (userId: number) => {
    try {
      const response = await api.get(`/auth/users/${userId}/companies`)
      setUserCompanies(response.data)
    } catch (error) {
      console.error('Failed to load user companies:', error)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/auth/users', newUser)
      setShowCreateModal(false)
      setNewUser({ email: '', full_name: '', password: '' })
      loadUsers()
    } catch (error) {
      alert(getErrorMessage(error, 'Failed to create user'))
    }
  }

  const handleGrantAccess = async () => {
    if (!selectedUser || !selectedCompanyId) return

    try {
      await api.post(
        `/auth/users/${selectedUser.id}/companies/${selectedCompanyId}`,
        { role: selectedRole }
      )
      loadUserCompanies(selectedUser.id)
      setSelectedCompanyId(null)
    } catch (error) {
      alert(getErrorMessage(error, 'Failed to grant access'))
    }
  }

  const handleRevokeAccess = async (userId: number, companyId: number) => {
    if (!confirm('Är du säker på att du vill ta bort åtkomst till detta företag?')) return

    try {
      await api.delete(`/auth/users/${userId}/companies/${companyId}`)
      if (selectedUser) {
        loadUserCompanies(selectedUser.id)
      }
    } catch (error) {
      alert(getErrorMessage(error, 'Failed to revoke access'))
    }
  }

  const openCompanyModal = async (user: User) => {
    setSelectedUser(user)
    await loadUserCompanies(user.id)
    setShowCompanyModal(true)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Laddar användare...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Användare</h1>
          <p className="text-gray-500 mt-1">Hantera användare och deras företagsbehörigheter</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-5 h-5" />
          Ny användare
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Användare
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                E-post
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Roll
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Åtgärder
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <UsersIcon className="h-5 w-5 text-blue-600" />
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-gray-900">{user.full_name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.email}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      user.is_admin
                        ? 'bg-purple-100 text-purple-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {user.is_admin ? 'Admin' : 'Användare'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {user.is_active ? 'Aktiv' : 'Inaktiv'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <button
                    onClick={() => openCompanyModal(user)}
                    className="text-blue-600 hover:text-blue-900 flex items-center gap-1"
                  >
                    <Building2 className="w-4 h-4" />
                    Hantera företag
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Skapa ny användare</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Namn
                </label>
                <input
                  type="text"
                  value={newUser.full_name}
                  onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  E-post
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Lösenord
                </label>
                <input
                  type="password"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  required
                  minLength={6}
                />
              </div>
              <div className="flex gap-3 mt-6">
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                  Skapa
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

      {/* Manage Companies Modal */}
      {showCompanyModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl">
            <h2 className="text-xl font-bold mb-4">
              Företagsbehörigheter för {selectedUser.full_name}
            </h2>

            {selectedUser.is_admin ? (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4">
                <p className="text-purple-800">
                  <strong>Admin-användare</strong> har automatiskt åtkomst till alla företag.
                </p>
              </div>
            ) : (
              <>
                {/* User's Companies */}
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Nuvarande företag</h3>
                  {userCompanies.length === 0 ? (
                    <p className="text-gray-500 text-sm">Användaren har ingen företagsbehörighet än.</p>
                  ) : (
                    <div className="space-y-2">
                      {userCompanies.map((company) => (
                        <div
                          key={company.id}
                          className="flex items-center justify-between bg-gray-50 p-3 rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            <Building2 className="w-4 h-4 text-gray-500" />
                            <span className="text-sm font-medium">{company.name}</span>
                          </div>
                          <button
                            onClick={() => handleRevokeAccess(selectedUser.id, company.id)}
                            className="text-red-600 hover:text-red-800"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Add Company Access */}
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Lägg till företag</h3>
                  <div className="flex gap-2">
                    <select
                      value={selectedCompanyId || ''}
                      onChange={(e) => setSelectedCompanyId(Number(e.target.value))}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="">Välj företag...</option>
                      {companies
                        .filter((c) => !userCompanies.find((uc) => uc.id === c.id))
                        .map((company) => (
                          <option key={company.id} value={company.id}>
                            {company.name}
                          </option>
                        ))}
                    </select>
                    <select
                      value={selectedRole}
                      onChange={(e) => setSelectedRole(e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="user">Användare</option>
                      <option value="accountant">Redovisare</option>
                      <option value="manager">Chef</option>
                    </select>
                    <button
                      onClick={handleGrantAccess}
                      disabled={!selectedCompanyId}
                      className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                      Lägg till
                    </button>
                  </div>
                </div>
              </>
            )}

            <div className="flex justify-end mt-6">
              <button
                onClick={() => {
                  setShowCompanyModal(false)
                  setSelectedUser(null)
                  setUserCompanies([])
                }}
                className="bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300"
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
