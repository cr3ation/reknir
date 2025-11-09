import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom'
import { Home, FileText, PieChart, Settings, Receipt, BookOpen } from 'lucide-react'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Verifications from './pages/Verifications'
import Invoices from './pages/Invoices'
import Accounts from './pages/Accounts'
import Reports from './pages/Reports'
import SettingsPage from './pages/Settings'
import Setup from './pages/Setup'
import api from './services/api'

function App() {
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkSetupStatus()
  }, [])

  const checkSetupStatus = async () => {
    try {
      const response = await api.get('/api/companies/')
      setSetupComplete(response.data.length > 0)
    } catch (error) {
      console.error('Error checking setup status:', error)
      setSetupComplete(false)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (!setupComplete) {
    return (
      <Router>
        <Routes>
          <Route path="/setup" element={<Setup />} />
          <Route path="*" element={<Navigate to="/setup" replace />} />
        </Routes>
      </Router>
    )
  }

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {/* Navigation */}
        <nav className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex">
                <div className="flex-shrink-0 flex items-center">
                  <h1 className="text-2xl font-bold text-primary-600">Reknir</h1>
                </div>
                <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                  <Link
                    to="/"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900 border-b-2 border-primary-500"
                  >
                    <Home className="w-4 h-4 mr-2" />
                    Översikt
                  </Link>
                  <Link
                    to="/invoices"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 hover:border-gray-300 border-b-2 border-transparent"
                  >
                    <Receipt className="w-4 h-4 mr-2" />
                    Fakturor
                  </Link>
                  <Link
                    to="/verifications"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 hover:border-gray-300 border-b-2 border-transparent"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Verifikationer
                  </Link>
                  <Link
                    to="/accounts"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 hover:border-gray-300 border-b-2 border-transparent"
                  >
                    <BookOpen className="w-4 h-4 mr-2" />
                    Kontoplan
                  </Link>
                  <Link
                    to="/reports"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 hover:border-gray-300 border-b-2 border-transparent"
                  >
                    <PieChart className="w-4 h-4 mr-2" />
                    Rapporter
                  </Link>
                  <Link
                    to="/settings"
                    className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 hover:border-gray-300 border-b-2 border-transparent"
                  >
                    <Settings className="w-4 h-4 mr-2" />
                    Inställningar
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/verifications" element={<Verifications />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
