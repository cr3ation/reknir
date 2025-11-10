import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom'
import { Home, FileText, PieChart, Settings, Receipt, BookOpen, Users, Wallet } from 'lucide-react'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Verifications from './pages/Verifications'
import Invoices from './pages/Invoices'
import Customers from './pages/Customers'
import Accounts from './pages/Accounts'
import AccountLedger from './pages/AccountLedger'
import Reports from './pages/Reports'
import Expenses from './pages/Expenses'
import SettingsPage from './pages/Settings'
import Setup from './pages/Setup'
import api from './services/api'
import { FiscalYearProvider } from './contexts/FiscalYearContext'
import FiscalYearSelector from './components/FiscalYearSelector'

function App() {
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [backendOffline, setBackendOffline] = useState(false)

  useEffect(() => {
    checkSetupStatus()
  }, [])

  const checkSetupStatus = async () => {
    try {
      const response = await api.get('/api/companies/')
      setSetupComplete(response.data.length > 0)
      setBackendOffline(false)
    } catch (error: any) {
      console.error('Error checking setup status:', error)

      // Check if it's a network error (backend offline)
      if (error.code === 'ERR_NETWORK' || error.message === 'Network Error' || !error.response) {
        setBackendOffline(true)
      } else {
        setSetupComplete(false)
      }
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

  if (backendOffline) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-red-100 p-3">
              <svg className="h-8 w-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Backend är offline</h2>
          <p className="text-gray-600 mb-6">
            Kan inte ansluta till backend-servern. Kontrollera att backend körs med <code className="bg-gray-100 px-2 py-1 rounded text-sm">docker compose up</code>
          </p>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Försök igen
          </button>
        </div>
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
      <FiscalYearProvider>
        <AppContent />
      </FiscalYearProvider>
    </Router>
  )
}

function AppContent() {
  const location = useLocation()

  const menuItems = [
    { path: '/', icon: Home, label: 'Översikt' },
    { path: '/invoices', icon: Receipt, label: 'Fakturor' },
    { path: '/expenses', icon: Wallet, label: 'Utlägg' },
    { path: '/verifications', icon: FileText, label: 'Verifikationer' },
    { path: '/customers', icon: Users, label: 'Kunder' },
    { path: '/accounts', icon: BookOpen, label: 'Kontoplan' },
    { path: '/reports', icon: PieChart, label: 'Rapporter' },
    { path: '/settings', icon: Settings, label: 'Inställningar' },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-primary-600" style={{ fontFamily: "'MedievalSharp', serif" }}>
            REKNIR
          </h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {menuItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path ||
                           (item.path !== '/' && location.pathname.startsWith(item.path))

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Icon className={`w-5 h-5 mr-3 ${isActive ? 'text-primary-600' : 'text-gray-500'}`} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Fiscal Year Selector at bottom */}
        <div className="p-4 border-t border-gray-200">
          <FiscalYearSelector />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/invoices" element={<Invoices />} />
              <Route path="/expenses" element={<Expenses />} />
              <Route path="/verifications" element={<Verifications />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/accounts/:accountId/ledger" element={<AccountLedger />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
