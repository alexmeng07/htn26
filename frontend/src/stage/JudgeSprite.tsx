import { useState } from 'react'
import { motion } from 'framer-motion'
import { mediaUrl } from '../api/client'

export type SpriteState = 'idle' | 'talking' | 'yes' | 'no'

/**
 * Four PNGs per judge become a full performance:
 *  idle     -> gentle breathing bob
 *  talking  -> swap talking/idle a few times a second (reads as lip-flap)
 *  yes/no   -> quick scale-pop, then hold
 *
 * Until the sprite art lands in assets/judges/<id>/, a lettered badge stands in
 * so the stage still reads correctly.
 */
export default function JudgeSprite({
  judgeId,
  name,
  state,
  size = 256,
}: {
  judgeId: string
  name?: string
  state: SpriteState
  size?: number
}) {
  const [missing, setMissing] = useState(false)
  // During `talking` the caller alternates the frame; this component only
  // renders whichever state it's handed.
  const src = mediaUrl(`/judges/${judgeId}/${state}.png`)

  const animate =
    state === 'idle'
      ? { y: [0, -6, 0], scale: 1 }
      : state === 'yes' || state === 'no'
        ? { scale: [1, 1.12, 1], y: 0 }
        : { y: 0, scale: 1 }
  const transition =
    state === 'idle'
      ? { repeat: Infinity, duration: 2.4, ease: 'easeInOut' as const }
      : { duration: 0.28 }

  if (missing) {
    const ring =
      state === 'yes' ? 'ring-yes' : state === 'no' ? 'ring-no' : state === 'talking' ? 'ring-spot' : 'ring-white/15'
    return (
      <motion.div
        animate={animate}
        transition={transition}
        style={{ width: size, height: size }}
        className={`grid select-none place-items-center rounded-full bg-stage-deep ring-4 ${ring}`}
      >
        <span className="text-5xl font-black text-white/80">{(name ?? judgeId).charAt(0)}</span>
      </motion.div>
    )
  }

  return (
    <motion.img
      src={src}
      alt=""
      width={size}
      height={size}
      onError={() => setMissing(true)}
      animate={animate}
      transition={transition}
      className="select-none drop-shadow-[0_0_24px_rgba(255,215,111,0.15)]"
    />
  )
}
