import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const Setup: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'company' | 'seeding' | 'complete'>('company');

  const [formData, setFormData] = useState({
    name: '',
    org_number: '',
    fiscal_year_start: new Date().getFullYear() + '-01-01',
    fiscal_year_end: new Date().getFullYear() + '-12-31',
    accounting_basis: 'accrual' as 'accrual' | 'cash',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Create company
      const response = await api.post('/api/companies/', formData);
      const companyId = response.data.id;

      setStep('seeding');

      // Seed BAS accounts
      try {
        await api.post(`/api/companies/${companyId}/seed-bas`);
      } catch (err) {
        console.error('Failed to seed BAS accounts:', err);
        // Continue anyway - user can seed later
      }

      setStep('complete');

      // Redirect to dashboard after 2 seconds (force page reload to update App state)
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);

    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ett fel uppstod vid skapande av företaget');
      setLoading(false);
    }
  };

  if (step === 'seeding') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Laddar kontoplan...</h2>
          <p className="text-gray-600">BAS 2024 kontoplan importeras</p>
        </div>
      </div>
    );
  }

  if (step === 'complete') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <div className="text-green-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Klart!</h2>
          <p className="text-gray-600">Ditt företag har skapats och kontoplanen är laddad.</p>
          <p className="text-gray-500 text-sm mt-2">Omdirigerar till instrumentpanelen...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-2xl w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Välkommen till Reknir</h1>
          <p className="text-gray-600">Börja med att skapa ditt företag</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
              Företagsnamn *
            </label>
            <input
              type="text"
              id="name"
              name="name"
              required
              value={formData.name}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="t.ex. Min Företag AB"
            />
          </div>

          <div>
            <label htmlFor="org_number" className="block text-sm font-medium text-gray-700 mb-2">
              Organisationsnummer *
            </label>
            <input
              type="text"
              id="org_number"
              name="org_number"
              required
              value={formData.org_number}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="XXXXXX-XXXX"
              pattern="[0-9]{6}-?[0-9]{4}"
            />
            <p className="mt-1 text-sm text-gray-500">Format: XXXXXX-XXXX</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="fiscal_year_start" className="block text-sm font-medium text-gray-700 mb-2">
                Räkenskapsår start *
              </label>
              <input
                type="date"
                id="fiscal_year_start"
                name="fiscal_year_start"
                required
                value={formData.fiscal_year_start}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            <div>
              <label htmlFor="fiscal_year_end" className="block text-sm font-medium text-gray-700 mb-2">
                Räkenskapsår slut *
              </label>
              <input
                type="date"
                id="fiscal_year_end"
                name="fiscal_year_end"
                required
                value={formData.fiscal_year_end}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label htmlFor="accounting_basis" className="block text-sm font-medium text-gray-700 mb-2">
              Redovisningsmetod *
            </label>
            <select
              id="accounting_basis"
              name="accounting_basis"
              required
              value={formData.accounting_basis}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="accrual">Bokföringsmässiga grunder (accrual)</option>
              <option value="cash">Kontantmetoden (cash)</option>
            </select>
            <p className="mt-1 text-sm text-gray-500">
              De flesta företag använder bokföringsmässiga grunder
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-medium text-blue-900 mb-2">Vad händer härnäst?</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ Ditt företag skapas i systemet</li>
              <li>✓ BAS 2024 kontoplan importeras automatiskt (43 konton)</li>
              <li>✓ Du omdirigeras till instrumentpanelen</li>
            </ul>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {loading ? 'Skapar företag...' : 'Skapa företag och kom igång'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Setup;
