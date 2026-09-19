import { useCallback, useRef, useState } from 'react'

/**
 * Records camera + microphone only. The movie audio goes to the headphones and
 * is never captured, so it can't bleed into the voice judge's input.
 *
 * The reference video and this recording start together and run the same
 * length, so second 14 of the take lines up with second 14 of the character's
 * performance -- no alignment step needed.
 */
export function useRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [recording, setRecording] = useState(false)

  const open = useCallback(async () => {
    const media = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720, facingMode: 'user' },
      audio: { echoCancellation: true, noiseSuppression: true },
    })
    setStream(media)
    return media
  }, [])

  const start = useCallback(async () => {
    const media = stream ?? (await open())
    chunksRef.current = []
    const recorder = new MediaRecorder(media, { mimeType: 'video/webm;codecs=vp8,opus' })
    recorder.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data)
    recorderRef.current = recorder
    recorder.start(250)
    setRecording(true)
  }, [stream, open])

  const stop = useCallback(
    () =>
      new Promise<Blob>((resolve) => {
        const recorder = recorderRef.current
        if (!recorder) return resolve(new Blob())
        recorder.onstop = () => {
          setRecording(false)
          resolve(new Blob(chunksRef.current, { type: 'video/webm' }))
        }
        recorder.stop()
      }),
    [],
  )

  const close = useCallback(() => {
    stream?.getTracks().forEach((t) => t.stop())
    setStream(null)
  }, [stream])

  return { stream, recording, open, start, stop, close }
}
