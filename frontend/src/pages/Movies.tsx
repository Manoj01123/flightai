import { useState, useEffect } from 'react'
import { Star, Calendar, Clock, ChevronRight, Film, Search, X } from 'lucide-react'

const TMDB_KEY = import.meta.env.VITE_TMDB_API_KEY
const TMDB = 'https://api.themoviedb.org/3'
const IMG = 'https://image.tmdb.org/t/p'

interface Movie {
  id: number
  title: string
  overview: string
  poster_path: string | null
  backdrop_path: string | null
  release_date: string
  vote_average: number
  vote_count: number
  genre_ids: number[]
  popularity: number
}

interface MovieDetail extends Movie {
  runtime: number | null
  genres: { id: number; name: string }[]
  tagline: string
}

const GENRES: Record<number, string> = {
  28: 'Action', 12: 'Adventure', 16: 'Animation', 35: 'Comedy', 80: 'Crime',
  99: 'Documentary', 18: 'Drama', 10751: 'Family', 14: 'Fantasy', 36: 'History',
  27: 'Horror', 10402: 'Music', 9648: 'Mystery', 10749: 'Romance', 878: 'Sci-Fi',
  10770: 'TV Movie', 53: 'Thriller', 10752: 'War', 37: 'Western',
}

function fandangoUrl(title: string) {
  return `https://www.fandango.com/search?q=${encodeURIComponent(title)}`
}

function formatDate(d: string) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function StarRating({ score }: { score: number }) {
  return (
    <span className="flex items-center gap-1 text-sm font-semibold text-amber-500">
      <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
      {score.toFixed(1)}
      <span className="text-gray-400 font-normal text-xs">/ 10</span>
    </span>
  )
}

function MovieCard({ movie, onClick }: { movie: Movie; onClick: () => void }) {
  const poster = movie.poster_path
    ? `${IMG}/w342${movie.poster_path}`
    : null

  return (
    <button
      onClick={onClick}
      className="bg-white rounded-2xl overflow-hidden shadow-sm border border-gray-100 hover:shadow-md transition-all text-left active:scale-95"
    >
      <div className="aspect-[2/3] bg-gray-100 relative overflow-hidden">
        {poster ? (
          <img src={poster} alt={movie.title} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film className="w-12 h-12 text-gray-300" />
          </div>
        )}
        <div className="absolute top-2 right-2 bg-black/70 backdrop-blur-sm rounded-full px-2 py-0.5 flex items-center gap-1">
          <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
          <span className="text-white text-xs font-bold">{movie.vote_average.toFixed(1)}</span>
        </div>
      </div>
      <div className="p-3">
        <h3 className="font-semibold text-gray-900 text-sm leading-tight line-clamp-2">{movie.title}</h3>
        <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          {formatDate(movie.release_date)}
        </p>
        <div className="flex flex-wrap gap-1 mt-2">
          {movie.genre_ids.slice(0, 2).map(id => (
            <span key={id} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
              {GENRES[id] ?? 'Other'}
            </span>
          ))}
        </div>
      </div>
    </button>
  )
}

function MovieModal({ movie, onClose }: { movie: Movie; onClose: () => void }) {
  const [detail, setDetail] = useState<MovieDetail | null>(null)

  useEffect(() => {
    if (!TMDB_KEY) return
    fetch(`${TMDB}/movie/${movie.id}?api_key=${TMDB_KEY}&language=en-US`)
      .then(r => r.json())
      .then(setDetail)
      .catch(() => {})
  }, [movie.id])

  const backdrop = movie.backdrop_path ? `${IMG}/w780${movie.backdrop_path}` : null
  const poster   = movie.poster_path   ? `${IMG}/w342${movie.poster_path}`   : null

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-3xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Backdrop */}
        <div className="relative h-48 bg-gray-900 flex-shrink-0">
          {backdrop && <img src={backdrop} alt="" className="w-full h-full object-cover opacity-70" />}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm rounded-full p-2 text-white hover:bg-black/70"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto">
          <div className="flex gap-4 p-4 -mt-12 relative">
            {poster && (
              <img src={poster} alt={movie.title} className="w-24 h-36 object-cover rounded-xl shadow-lg flex-shrink-0 border-2 border-white" />
            )}
            <div className="pt-14 flex-1 min-w-0">
              <h2 className="font-bold text-gray-900 text-lg leading-tight">{movie.title}</h2>
              {detail?.tagline && <p className="text-sm text-blue-600 italic mt-0.5">{detail.tagline}</p>}
              <div className="flex items-center gap-3 mt-2 flex-wrap">
                <StarRating score={movie.vote_average} />
                {detail?.runtime && (
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    {Math.floor(detail.runtime / 60)}h {detail.runtime % 60}m
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="px-4 pb-2">
            <div className="flex flex-wrap gap-1.5 mb-3">
              {(detail?.genres ?? movie.genre_ids.map(id => ({ id, name: GENRES[id] ?? 'Other' }))).map(g => (
                <span key={g.id} className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full font-medium">
                  {g.name}
                </span>
              ))}
            </div>

            <p className="text-sm text-gray-600 leading-relaxed mb-4">
              {movie.overview || 'No description available.'}
            </p>

            <div className="bg-gray-50 rounded-xl p-3 mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500">Release date</p>
                <p className="text-sm font-semibold text-gray-900">{formatDate(movie.release_date)}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">Audience score</p>
                <p className="text-sm font-semibold text-gray-900">{Math.round(movie.vote_average * 10)}%</p>
              </div>
            </div>
          </div>

          <div className="px-4 pb-6 grid grid-cols-2 gap-3">
            <a
              href={fandangoUrl(movie.title)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
            >
              Fandango
              <ChevronRight className="w-4 h-4" />
            </a>
            <a
              href={`https://www.amctheatres.com/movies?q=${encodeURIComponent(movie.title)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
            >
              AMC
              <ChevronRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

type Tab = 'upcoming' | 'now_playing' | 'popular'

export default function Movies() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Movie | null>(null)
  const [tab, setTab] = useState<Tab>('upcoming')
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<Movie[]>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    if (!TMDB_KEY) { setError('TMDb API key not configured. Add VITE_TMDB_API_KEY to your environment.'); setLoading(false); return }
    setLoading(true)
    fetch(`${TMDB}/movie/${tab}?api_key=${TMDB_KEY}&language=en-US&region=US&page=1`)
      .then(r => r.json())
      .then(d => { setMovies(d.results ?? []); setLoading(false) })
      .catch(() => { setError('Failed to load movies.'); setLoading(false) })
  }, [tab])

  useEffect(() => {
    if (!search.trim() || !TMDB_KEY) { setSearchResults([]); return }
    const t = setTimeout(() => {
      setSearching(true)
      fetch(`${TMDB}/search/movie?api_key=${TMDB_KEY}&query=${encodeURIComponent(search)}&language=en-US&region=US`)
        .then(r => r.json())
        .then(d => { setSearchResults(d.results ?? []); setSearching(false) })
        .catch(() => setSearching(false))
    }, 400)
    return () => clearTimeout(t)
  }, [search])

  const displayed = search.trim() ? searchResults : movies

  const tabs: { key: Tab; label: string }[] = [
    { key: 'upcoming',    label: 'Coming Soon' },
    { key: 'now_playing', label: 'Now Playing' },
    { key: 'popular',     label: 'Popular' },
  ]

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 pb-24">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Film className="w-6 h-6 text-blue-600" />
          Movies
        </h1>
        <p className="text-sm text-gray-500 mt-1">US theaters — tap any movie to find tickets</p>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search movies…"
          className="w-full pl-9 pr-10 py-2.5 bg-gray-100 border border-transparent rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:bg-white transition-all"
        />
        {search && (
          <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Tabs */}
      {!search && (
        <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-xl">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
                tab === t.key ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 text-sm text-amber-700">
          {error}
        </div>
      )}

      {loading || searching ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-2xl overflow-hidden animate-pulse">
              <div className="aspect-[2/3] bg-gray-200" />
              <div className="p-3 space-y-2">
                <div className="h-3 bg-gray-200 rounded w-3/4" />
                <div className="h-3 bg-gray-200 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : displayed.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Film className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>{search ? 'No results found' : 'No movies available'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {displayed.map(m => (
            <MovieCard key={m.id} movie={m} onClick={() => setSelected(m)} />
          ))}
        </div>
      )}

      {selected && <MovieModal movie={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
