import Link from 'next/link';
import Dashboard from '@/components/Dashboard';

export default function Home() {
  return (
    <div>
      <nav className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-6">
          <h1 className="text-lg font-bold text-gray-900">Vigil</h1>
          <div className="flex gap-4">
            <Link href="/signals" className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors">
              Signals
            </Link>
            <Link href="/simulations" className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors">
              Simulations
            </Link>
          </div>
        </div>
      </nav>
      <Dashboard />
    </div>
  );
}
