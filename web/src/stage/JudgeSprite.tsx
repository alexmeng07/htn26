import { motion } from 'framer-motion'

export type SpriteState = 'idle' | 'talking' | 'yes' | 'no'

/**
 * Four PNGs per judge become a full performance:
 *  idle     -> gentle breathing bob
 *  talking  -> swap talking/idle a few times a second (reads as lip-flap)
 *  yes/no   -> quick scale-pop, then hold
 *
 * Lane B: drive `state` from the verdict sequence and wire the ding/buzzer SFX.
 */
export default function JudgeSprite({
  judgeId,
  state,
  size = 256,
}: {
  judgeId: string
  state: SpriteState
  size?: number
}) {
  // During `talking` the caller alternates the frame; this component only
  // renders whichever state it's handed.
  const src = `/judges/${judgeId}/${state}.png`
  return (
    <motion.img
      src={src}
      alt=""
      width={size}
      height={size}
      animate={
        state === 'idle'
          ? { y: [0, -6, 0] }
          : state === 'yes' || state === 'no'
            ? { scale: [1, 1.12, 1] }
            : { y: 0 }
      }
      transition={
        state === 'idle'
          ? { repeat: Infinity, duration: 2.4, ease: 'easeInOut' }
          : { duration: 0.28 }
      }
      className="select-none drop-shadow-[0_0_24px_rgba(255,215,111,0.15)]"
    />
  )
}
