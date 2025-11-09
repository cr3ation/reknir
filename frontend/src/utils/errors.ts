/**
 * Extracts error message from API error response
 * Handles both Pydantic validation errors (array of objects) and simple string errors
 */
export function getErrorMessage(err: any, fallback: string = 'Ett fel uppstod'): string {
  const detail = err.response?.data?.detail

  if (Array.isArray(detail)) {
    // Pydantic validation errors
    return detail.map((e: any) => {
      const field = e.loc?.slice(1).join('.') || 'field'
      return `${field}: ${e.msg}`
    }).join(', ')
  } else if (typeof detail === 'string') {
    return detail
  } else {
    return fallback
  }
}
