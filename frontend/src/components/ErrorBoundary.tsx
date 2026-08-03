import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
          <div className="bg-white rounded-xl border border-red-200 p-8 max-w-lg w-full">
            <h2 className="text-lg font-semibold text-red-600 mb-2">Something went wrong</h2>
            <pre className="text-xs text-gray-600 bg-gray-100 rounded p-3 overflow-auto whitespace-pre-wrap">
              {this.state.error.message}
            </pre>
            <button
              onClick={() => { localStorage.clear(); window.location.href = '/login' }}
              className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              Clear & go to login
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
