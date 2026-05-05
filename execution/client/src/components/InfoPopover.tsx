import { useEffect, useRef, useState, type ReactNode } from 'react'

/**
 * Small (i) icon trigger that reveals a popover with longer-form content.
 *
 * Used to keep panel headers and methodology footers compact while still
 * exposing the underlying detail on demand. Click the icon to open; click
 * outside or press Escape to close. Popover is positioned below-right of
 * the icon by default, with width capped to the viewport on narrow screens.
 *
 * Usage:
 *   <h2>Title <InfoPopover>Long methodology text…</InfoPopover></h2>
 *
 * The element renders inline so it inherits surrounding text alignment.
 */
export default function InfoPopover({
  children,
  label = 'More info',
  align = 'left',
  size = 'md',
}: {
  children: ReactNode
  label?: string
  align?: 'left' | 'right'
  /** `md` = 20px (panel headers), `sm` = 14px (inline w/ small labels). */
  size?: 'sm' | 'md'
}) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <span ref={wrapRef} className="relative inline-flex items-center align-baseline">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((o) => !o)
        }}
        className={`
          inline-flex items-center justify-center flex-shrink-0
          rounded-full
          border font-serif italic font-bold leading-none
          ml-1.5 align-middle
          transition-all duration-150
          ${size === 'sm' ? 'w-[14px] h-[14px] text-[9px]' : 'w-5 h-5 text-[12px]'}
          ${
            open
              ? 'bg-accent text-bg border-accent shadow-md shadow-accent/40 scale-110'
              : 'bg-accent/15 border-accent/60 text-accent hover:bg-accent/30 hover:border-accent hover:scale-110 hover:shadow hover:shadow-accent/30'
          }
        `}
      >
        i
      </button>
      {open && (
        <div
          className={`
            absolute z-30 top-full mt-2
            w-80 sm:w-96 max-w-[calc(100vw-2rem)]
            border border-border bg-surface rounded-lg shadow-xl
            p-3.5 text-xs text-text-dim leading-relaxed
            ${align === 'right' ? 'right-0' : 'left-0'}
          `}
          role="dialog"
          aria-label={label}
        >
          {children}
        </div>
      )}
    </span>
  )
}
