import { useEffect, useState } from 'react'

const SHOW_AFTER_PX = 400

export default function GoToTopButton() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > SHOW_AFTER_PX)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleClick = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (window.location.hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }

  return (
    <button
      onClick={handleClick}
      aria-label="Go to top"
      className={`fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full border border-orange-500/50 bg-surface/90 backdrop-blur text-orange-400 hover:text-orange-300 hover:border-orange-400 hover:bg-orange-500/10 flex items-center justify-center transition-all duration-200 shadow-lg ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'
      }`}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m18 15-6-6-6 6" />
      </svg>
    </button>
  )
}
