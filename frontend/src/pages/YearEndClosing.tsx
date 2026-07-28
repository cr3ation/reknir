import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, AlertTriangle, CheckCircle, Lock, ChevronRight } from 'lucide-react'
import { yearEndClosingApi, accountApi } from '@/services/api'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { useCompany } from '@/contexts/CompanyContext'
import { useToast } from '@/contexts/ToastContext'
import { getErrorMessage } from '@/utils/errors'
import FiscalYearSelector from '@/components/FiscalYearSelector'
import type {
  YearEndClosing as Closing,
  ClosingAdjustmentInput,
  ClosingCheck,
  ClosingStep,
  AdjustmentType,
} from '@/types'

const STEP_LABELS: Record<ClosingStep, string> = {
  preparation: 'Förberedelser',
  adjustments: 'Justeringar',
  tax: 'Skatt och resultat',
  review: 'Granska och slutför',
}

const STEP_ORDER: ClosingStep[] = ['preparation', 'adjustments', 'tax', 'review']

/** The bits of an account the adjustment picker needs. */
interface AccountOption {
  id: number
  account_number: number
  name: string
  account_type: string
}

/**
 * The adjustment questions, phrased the way an accountant would ask them out loud.
 * The user answers with an amount; which accounts get debited and credited is the
 * server's problem, not theirs.
 */
const ADJUSTMENT_QUESTIONS: Array<{
  type: AdjustmentType
  question: string
  help: string
  amountLabel: string
  /** Which accounts the user picks between, or null when the posting is fixed. */
  accountKind: 'cost' | 'revenue' | null
  accountLabel?: string
}> = [
  {
    type: 'stock',
    question: 'Hade du ett varulager den sista dagen på året?',
    help: 'Varor du köpt in men ännu inte sålt. De är inte en kostnad förrän de säljs, så de ska räknas som en tillgång istället.',
    amountLabel: 'Vad var lagret värt?',
    accountKind: null,
  },
  {
    type: 'accrued_expense',
    question: 'Har du fått fakturor efter årsskiftet som gäller arbete som utfördes förra året?',
    help: 'Till exempel en elräkning för december som kom i januari. Kostnaden hör till förra året även om fakturan kom senare.',
    amountLabel: 'Hur mycket sammanlagt?',
    accountKind: 'cost',
    accountLabel: 'Vad gällde kostnaden?',
  },
  {
    type: 'prepaid_expense',
    question: 'Har du betalat något i förskott som gäller nästa år?',
    help: 'Till exempel lokalhyra för januari som du betalade i december. Den kostnaden hör till nästa år.',
    amountLabel: 'Hur mycket sammanlagt?',
    accountKind: 'cost',
    accountLabel: 'Vad gällde kostnaden?',
  },
  {
    type: 'accrued_revenue',
    question: 'Har du utfört arbete förra året som du fakturerar först i år?',
    help: 'Intäkten hör till det år arbetet gjordes, inte det år fakturan skickades.',
    amountLabel: 'Hur mycket sammanlagt?',
    accountKind: 'revenue',
    accountLabel: 'Vilken typ av intäkt?',
  },
  {
    type: 'prepaid_revenue',
    question: 'Har du fått betalt i förskott för något du levererar nästa år?',
    help: 'Pengarna är inte en intäkt förrän du levererat. Fram till dess är de en skuld till kunden.',
    amountLabel: 'Hur mycket sammanlagt?',
    accountKind: 'revenue',
    accountLabel: 'Vilken typ av intäkt?',
  },
]

const COST_ACCOUNT_TYPES = ['cost_goods', 'cost_local', 'cost_other', 'cost_personnel']

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('sv-SE', {
    style: 'currency',
    currency: 'SEK',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

function CheckList({
  checks,
  acknowledged,
  onAcknowledge,
  readOnly,
}: {
  checks: ClosingCheck[]
  acknowledged: string[]
  onAcknowledge: (code: string) => void
  readOnly: boolean
}) {
  if (checks.length === 0) return null

  const style: Record<string, { box: string; icon: JSX.Element }> = {
    red: {
      box: 'border-red-300 bg-red-50',
      icon: <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />,
    },
    yellow: {
      box: 'border-amber-300 bg-amber-50',
      icon: <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />,
    },
    green: {
      box: 'border-green-300 bg-green-50',
      icon: <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />,
    },
  }

  return (
    <div className="space-y-3">
      {checks.map((check) => (
        <div
          key={check.code}
          className={`flex gap-3 p-4 border rounded-md ${style[check.severity]?.box ?? 'border-gray-300'}`}
        >
          {style[check.severity]?.icon}
          <div className="flex-1">
            <p className="font-medium text-gray-900">{check.message}</p>
            {check.detail && <p className="mt-1 text-sm text-gray-700">{check.detail}</p>}
            {check.severity === 'yellow' && !readOnly && (
              <label className="mt-2 inline-flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={acknowledged.includes(check.code)}
                  onChange={() => onAcknowledge(check.code)}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <span>Jag har kollat, gå vidare ändå</span>
              </label>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function YearEndClosing() {
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear, loadFiscalYears } = useFiscalYear()
  const { showToast } = useToast()

  const [closing, setClosing] = useState<Closing | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [step, setStep] = useState<ClosingStep>('preparation')

  // Local edit state for the free-text answers, so typing does not fire a request per
  // keystroke. Each adjustment keeps an amount and, where it matters, the account the
  // user picked for it.
  const [bankBalance, setBankBalance] = useState('')
  const [answers, setAnswers] = useState<
    Partial<Record<AdjustmentType, { amount: string; resultAccountId: string }>>
  >({})
  const [accounts, setAccounts] = useState<AccountOption[]>([])

  const fiscalYearId = selectedFiscalYear?.id

  const applyClosing = useCallback((data: Closing) => {
    setClosing(data)
    setBankBalance(data.bank_statement_balance ?? '')
    const next: Partial<Record<AdjustmentType, { amount: string; resultAccountId: string }>> = {}
    for (const adjustment of data.adjustments) {
      next[adjustment.adjustment_type] = {
        amount: adjustment.amount,
        resultAccountId: adjustment.result_account_id ? String(adjustment.result_account_id) : '',
      }
    }
    setAnswers(next)
  }, [])

  const load = useCallback(async () => {
    if (!fiscalYearId || !selectedCompany) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [closingResponse, accountsResponse] = await Promise.all([
        yearEndClosingApi.get(fiscalYearId),
        accountApi.list(selectedCompany.id, fiscalYearId, { active_only: true }),
      ])
      applyClosing(closingResponse.data)
      setStep(closingResponse.data.current_step)
      setAccounts(
        accountsResponse.data.map((a) => ({
          id: a.id,
          account_number: a.account_number,
          name: a.name,
          account_type: a.account_type as string,
        }))
      )
    } catch (error) {
      showToast(getErrorMessage(error), 'error')
    } finally {
      setLoading(false)
    }
  }, [fiscalYearId, selectedCompany, applyClosing, showToast])

  useEffect(() => {
    load()
  }, [load])

  const save = async (changes: Parameters<typeof yearEndClosingApi.update>[1]) => {
    if (!fiscalYearId) return
    setSaving(true)
    try {
      const response = await yearEndClosingApi.update(fiscalYearId, changes)
      applyClosing(response.data)
      return response.data
    } catch (error) {
      showToast(getErrorMessage(error), 'error')
    } finally {
      setSaving(false)
    }
  }

  const saveAdjustments = async (
    next: Partial<Record<AdjustmentType, { amount: string; resultAccountId: string }>>
  ) => {
    const adjustments: ClosingAdjustmentInput[] = ADJUSTMENT_QUESTIONS.filter((q) => {
      const answer = next[q.type]
      return answer && answer.amount !== '' && Number(answer.amount) !== 0
    }).map((q) => {
      const answer = next[q.type] as { amount: string; resultAccountId: string }
      return {
        adjustment_type: q.type,
        amount: answer.amount,
        result_account_id: answer.resultAccountId ? Number(answer.resultAccountId) : null,
      }
    })
    await save({ adjustments })
  }

  const setAnswer = (
    type: AdjustmentType,
    patch: Partial<{ amount: string; resultAccountId: string }>
  ) => {
    setAnswers((current) => ({
      ...current,
      [type]: { amount: '', resultAccountId: '', ...current[type], ...patch },
    }))
  }

  const toggleAcknowledge = async (code: string) => {
    if (!closing) return
    const current = closing.acknowledged_warnings
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code]
    await save({ acknowledged_warnings: next })
  }

  const handleComplete = async () => {
    if (!fiscalYearId) return
    const confirmed = window.confirm(
      'När bokslutet är klart låses hela räkenskapsåret. Efter det går det inte att ändra eller lägga till något i året. Vill du fortsätta?'
    )
    if (!confirmed) return

    setSaving(true)
    try {
      const response = await yearEndClosingApi.complete(fiscalYearId)
      applyClosing(response.data)
      // Refresh the fiscal years so the rest of the app sees the year as closed.
      if (selectedCompany) {
        await loadFiscalYears(selectedCompany.id)
      }
      showToast('Bokslutet är klart och året är låst', 'success')
    } catch (error) {
      showToast(getErrorMessage(error), 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar bokslut...</p>
      </div>
    )
  }

  if (!selectedCompany || !selectedFiscalYear) {
    return (
      <div className="card">
        <p className="text-gray-600">Välj ett företag och ett räkenskapsår för att göra bokslut.</p>
      </div>
    )
  }

  if (!closing) return null

  const isCompleted = closing.status === 'completed'
  const unlocked = Object.fromEntries(closing.steps.map((s) => [s.step, s.is_unlocked])) as Record<
    ClosingStep,
    boolean
  >
  const blocking = closing.checks.filter((c) => c.severity === 'red')
  const warnings = closing.checks.filter((c) => c.severity === 'yellow')

  return (
    <div className="max-w-4xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">Bokslut {closing.fiscal_year_label}</h1>
          <p className="mt-1 text-gray-600">
            Vi går igenom året tillsammans, steg för steg. Du svarar på frågor — bokföringen sköter vi.
          </p>
        </div>
        <FiscalYearSelector />
      </div>

      {isCompleted && (
        <div className="mb-6 flex gap-3 p-4 border border-green-300 bg-green-50 rounded-md">
          <Lock className="w-5 h-5 text-green-700 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-green-900">
              Bokslutet är klart och räkenskapsåret är låst.
            </p>
            <p className="mt-1 text-sm text-green-800">
              Ingenting i {closing.fiscal_year_label} går längre att ändra. Behöver du rätta något
              bokför du en korrigering i det nya året. Bokslutsverifikaten ligger i serie B under{' '}
              <Link to="/verifications" className="underline">
                Verifikationer
              </Link>
              , och du hittar resultat- och balansräkning under{' '}
              <Link to="/reports" className="underline">
                Rapporter
              </Link>
              .
            </p>
          </div>
        </div>
      )}

      {/* Step indicator */}
      <nav className="mb-6 flex flex-wrap items-center gap-2">
        {STEP_ORDER.map((s, index) => {
          const isCurrent = s === step
          const canOpen = unlocked[s]
          return (
            <div key={s} className="flex items-center gap-2">
              {index > 0 && <ChevronRight className="w-4 h-4 text-gray-400" />}
              <button
                type="button"
                disabled={!canOpen}
                onClick={() => setStep(s)}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isCurrent
                    ? 'bg-primary-600 text-white'
                    : canOpen
                      ? 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {index + 1}. {STEP_LABELS[s]}
              </button>
            </div>
          )
        })}
      </nav>

      {/* Traffic light summary */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-3">Hur ser det ut?</h2>
        <CheckList
          checks={closing.checks}
          acknowledged={closing.acknowledged_warnings}
          onAcknowledge={toggleAcknowledge}
          readOnly={isCompleted}
        />
      </div>

      {step === 'preparation' && (
        <div className="card space-y-5">
          <div>
            <h2 className="text-xl font-semibold">Steg 1 — Är allt bokfört?</h2>
            <p className="mt-1 text-gray-600">
              Innan vi kan stänga året måste den löpande bokföringen vara färdig. Har du kvar
              fakturor eller kvitton som hör till {closing.fiscal_year_label} ska de bokföras först.
            </p>
          </div>

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={closing.preparation_confirmed}
              disabled={isCompleted}
              onChange={(e) => save({ preparation_confirmed: e.target.checked })}
              className="w-4 h-4 mt-1 rounded border-gray-300"
            />
            <span className="text-gray-900">
              Jag har bokfört allt som hör till {closing.fiscal_year_label}
            </span>
          </label>

          <div>
            <label className="label">
              Vad stod det på ditt bankkonto den {selectedFiscalYear.end_date}?
            </label>
            <p className="mb-2 text-sm text-gray-600">
              Titta i din internetbank. Vi jämför med vad bokföringen säger — skiljer det sig har
              något missats.
            </p>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="0.01"
                value={bankBalance}
                disabled={isCompleted}
                onChange={(e) => setBankBalance(e.target.value)}
                onBlur={() => save({ bank_statement_balance: bankBalance || null })}
                className="input w-56"
                placeholder="0,00"
              />
              <span className="text-gray-500">kr</span>
              {closing.booked_bank_balance != null && (
                <span className="text-sm text-gray-600">
                  Bokfört saldo: {formatCurrency(Number(closing.booked_bank_balance))}
                </span>
              )}
            </div>
          </div>

          {!isCompleted && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={!unlocked.adjustments || saving}
              onClick={() => setStep('adjustments')}
            >
              Nästa steg
            </button>
          )}
        </div>
      )}

      {step === 'adjustments' && (
        <div className="card space-y-6">
          <div>
            <h2 className="text-xl font-semibold">Steg 2 — Hör allt till rätt år?</h2>
            <p className="mt-1 text-gray-600">
              Några saker hamnar lätt på fel år. Svara på frågorna nedan — hoppa över dem som inte
              gäller dig genom att lämna fältet tomt.
            </p>
          </div>

          {ADJUSTMENT_QUESTIONS.map((question) => {
            const answer = answers[question.type]
            const hasAmount = Boolean(answer?.amount && Number(answer.amount) !== 0)
            const options =
              question.accountKind === 'cost'
                ? accounts.filter((a) => COST_ACCOUNT_TYPES.includes(a.account_type))
                : question.accountKind === 'revenue'
                  ? accounts.filter((a) => a.account_type === 'revenue')
                  : []

            return (
              <div
                key={question.type}
                className="border-t border-gray-200 pt-5 first:border-t-0 first:pt-0"
              >
                <p className="font-medium text-gray-900">{question.question}</p>
                <p className="mt-1 text-sm text-gray-600">{question.help}</p>
                <div className="mt-3 flex items-center gap-3">
                  <label className="text-sm text-gray-700 w-48">{question.amountLabel}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={answer?.amount ?? ''}
                    disabled={isCompleted}
                    onChange={(e) => setAnswer(question.type, { amount: e.target.value })}
                    onBlur={() => saveAdjustments(answers)}
                    className="input w-48"
                    placeholder="Lämna tomt om nej"
                  />
                  <span className="text-gray-500">kr</span>
                </div>

                {/* Only ask what it was for once there is an amount — otherwise the
                    question is noise for everyone it does not apply to. */}
                {question.accountKind && hasAmount && (
                  <div className="mt-3 flex items-center gap-3">
                    <label className="text-sm text-gray-700 w-48">{question.accountLabel}</label>
                    <select
                      value={answer?.resultAccountId ?? ''}
                      disabled={isCompleted}
                      onChange={(e) => setAnswer(question.type, { resultAccountId: e.target.value })}
                      onBlur={() => saveAdjustments(answers)}
                      className="input w-96"
                    >
                      <option value="">Välj konto</option>
                      {options.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.account_number} {account.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )
          })}

          {!isCompleted && (
            <button type="button" className="btn btn-primary" disabled={saving} onClick={() => setStep('tax')}>
              Nästa steg
            </button>
          )}
        </div>
      )}

      {step === 'tax' && (
        <div className="card space-y-5">
          <div>
            <h2 className="text-xl font-semibold">Steg 3 — Hur gick det för företaget?</h2>
          </div>

          <div className="space-y-3">
            <div className="flex justify-between border-b border-gray-200 pb-2">
              <span className="text-gray-700">Resultat före skatt</span>
              <span className="font-medium">{formatCurrency(Number(closing.result_before_tax))}</span>
            </div>
            <div className="flex justify-between border-b border-gray-200 pb-2">
              <span className="text-gray-700">Beräknad skatt</span>
              <span className="font-medium">{formatCurrency(Number(closing.tax))}</span>
            </div>
            <div className="flex justify-between text-lg">
              <span className="font-semibold">Kvar efter skatt</span>
              <span className="font-bold">{formatCurrency(Number(closing.result_after_tax))}</span>
            </div>
          </div>

          <p className="text-gray-600">
            {Number(closing.result_after_tax) >= 0
              ? `Företaget gick med vinst under ${closing.fiscal_year_label}.`
              : `Företaget gick med förlust under ${closing.fiscal_year_label}. Det är inget fel i sig — förlusten minskar det egna kapitalet.`}
            {Number(closing.tax) === 0 && (
              <>
                {' '}
                Ingen bolagsskatt bokförs för din företagsform — skatten hanteras i din egen
                deklaration.
              </>
            )}
          </p>

          {!isCompleted && (
            <button type="button" className="btn btn-primary" disabled={saving} onClick={() => setStep('review')}>
              Nästa steg
            </button>
          )}
        </div>
      )}

      {step === 'review' && (
        <div className="card space-y-5">
          <div>
            <h2 className="text-xl font-semibold">Steg 4 — Så här bokförs bokslutet</h2>
            <p className="mt-1 text-gray-600">
              Det här är verifikaten vi skapar när du slutför. De hamnar i en egen serie (B) så att
              de inte blandas ihop med din löpande bokföring.
            </p>
          </div>

          {closing.postings.length === 0 && (
            <p className="text-gray-600">Inget behöver bokföras — året går ihop som det är.</p>
          )}

          {closing.postings.map((posting, index) => (
            <div key={index} className="border border-gray-200 rounded-md overflow-hidden">
              <div className="bg-gray-50 px-4 py-2 font-medium text-gray-900">{posting.description}</div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="px-4 py-2 font-medium">Konto</th>
                    <th className="px-4 py-2 font-medium text-right">Debet</th>
                    <th className="px-4 py-2 font-medium text-right">Kredit</th>
                  </tr>
                </thead>
                <tbody>
                  {posting.lines.map((line, lineIndex) => (
                    <tr key={lineIndex} className="border-t border-gray-100">
                      <td className="px-4 py-2">
                        {line.account_number} {line.account_name}
                        {line.account_will_be_created && (
                          <span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                            skapas
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {Number(line.debit) !== 0 ? formatCurrency(Number(line.debit)) : ''}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {Number(line.credit) !== 0 ? formatCurrency(Number(line.credit)) : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {closing.postings.some((p) => p.lines.some((l) => l.account_will_be_created)) && (
            <p className="text-sm text-gray-600">
              Konton märkta <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">skapas</span>{' '}
              finns inte i din kontoplan än. Vi lägger till dem åt dig när du slutför.
            </p>
          )}

          {!isCompleted && (
            <div className="border-t border-gray-200 pt-5">
              {blocking.length > 0 && (
                <p className="mb-3 text-sm text-red-700">
                  Det finns {blocking.length} sak{blocking.length === 1 ? '' : 'er'} som måste
                  åtgärdas innan du kan slutföra. Se listan högst upp.
                </p>
              )}
              {blocking.length === 0 && warnings.some((w) => !closing.acknowledged_warnings.includes(w.code)) && (
                <p className="mb-3 text-sm text-amber-700">
                  Kryssa i varningarna högst upp för att bekräfta att du kollat dem.
                </p>
              )}
              <button
                type="button"
                className="btn btn-primary"
                disabled={!closing.can_complete || saving}
                onClick={handleComplete}
              >
                {saving ? 'Slutför...' : 'Slutför bokslutet och lås året'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
