import { useState } from 'react'

const DONATION_ADDRESS = '0xf5a6746765476e819c2efB0619cd578b4D95903A'
const DISCORD_HANDLE = '0x_ct'

function DiscordIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path d="M19.27 5.33C17.94 4.71 16.5 4.26 15 4a.09.09 0 0 0-.07.03c-.18.33-.39.76-.53 1.09a16.09 16.09 0 0 0-4.8 0c-.14-.34-.35-.76-.54-1.09c-.01-.02-.04-.03-.07-.03c-1.5.26-2.93.71-4.27 1.33c-.01 0-.02.01-.03.02c-2.72 4.07-3.47 8.03-3.1 11.95c0 .02.01.04.03.05c1.8 1.32 3.53 2.12 5.24 2.65c.03.01.06 0 .07-.02c.4-.55.76-1.13 1.07-1.74c.02-.04 0-.08-.04-.09c-.57-.22-1.11-.48-1.64-.78c-.04-.02-.04-.08-.01-.11c.11-.08.22-.17.33-.25c.02-.02.05-.02.07-.01c3.44 1.57 7.15 1.57 10.55 0c.02-.01.05-.01.07.01c.11.09.22.17.33.26c.04.03.04.09-.01.11c-.52.31-1.07.56-1.64.78c-.04.01-.05.06-.04.09c.32.61.68 1.19 1.07 1.74c.03.01.06.02.09.01c1.72-.53 3.45-1.33 5.25-2.65c.02-.01.03-.03.03-.05c.44-4.53-.73-8.46-3.1-11.95c-.01-.01-.02-.02-.04-.02zM8.52 14.91c-1.03 0-1.89-.95-1.89-2.12s.84-2.12 1.89-2.12c1.06 0 1.9.96 1.89 2.12c0 1.17-.84 2.12-1.89 2.12zm6.97 0c-1.03 0-1.89-.95-1.89-2.12s.84-2.12 1.89-2.12c1.06 0 1.9.96 1.89 2.12c0 1.17-.83 2.12-1.89 2.12z" />
    </svg>
  )
}

export default function Maintainer() {
  const [copied, setCopied] = useState(false)

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(DONATION_ADDRESS)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable — silent */
    }
  }

  return (
    <section id="maintainer" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="mb-5">
        <h2 className="text-lg font-semibold">Maintainer</h2>
        <p className="text-text-dim text-sm">
          If this dashboard helped you make or avoid a trade, find a yield, or just make sense
          of what is going on - a few dollars will help cover maintenance and server time.
          Anonymous tipping welcome, never required.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 sm:gap-6 items-start">
        {/* Profile + Discord */}
        <div className="md:col-span-4 flex items-start gap-4">
          <img
            src="/maintainer/profile.png"
            alt={DISCORD_HANDLE}
            width={88}
            height={88}
            loading="lazy"
            className="rounded-full border-2 border-border bg-surface-2 flex-shrink-0"
          />
          <div className="flex-1 min-w-0">
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Discord
            </div>
            <div className="font-medium text-lg flex items-center gap-2">
              <span style={{ color: '#5865F2' }}>
                <DiscordIcon size={20} />
              </span>
              <span>{DISCORD_HANDLE}</span>
            </div>
            <p className="text-text-dim text-xs mt-2 leading-relaxed">
              Reach out for issues, suggestions, or feedback on the dashboard.
            </p>
          </div>
        </div>

        {/* Donation address */}
        <div className="md:col-span-5 border border-border rounded p-4 bg-surface-2">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-2">
            Donation address (any EVM chain)
          </div>
          <code className="text-sm font-mono break-all block text-text mb-3">
            {DONATION_ADDRESS}
          </code>
          <button
            onClick={copyAddress}
            className="text-xs font-mono uppercase tracking-wider px-3 py-1.5 rounded border border-border hover:border-accent/50 hover:text-accent transition"
          >
            {copied ? '✓ copied' : 'copy address'}
          </button>
          <p className="text-text-dim text-[11px] mt-3 leading-relaxed">
            Send ETH, USDC, USDT, or any ERC-20 on Ethereum, Optimism, Base, Arbitrum — same
            address on every EVM chain.
          </p>
        </div>

        {/* QR code */}
        <div className="md:col-span-3 flex flex-col items-center">
          <div className="bg-white p-2 rounded">
            <img
              src="/maintainer/wallet-qr.png"
              alt={`Donation address ${DONATION_ADDRESS}`}
              width={144}
              height={144}
              loading="lazy"
            />
          </div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mt-2">
            Scan to donate
          </div>
        </div>
      </div>

      {/* Anonymity-as-feature line */}
      <div className="mt-5 pt-4 border-t border-border text-text-dim text-[11px] font-mono uppercase tracking-wider text-center">
        Built independently · no Synthetix affiliation · no VC funding · ships under pseudonym
      </div>
    </section>
  )
}
