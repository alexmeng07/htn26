import { useCallback, useRef, useState } from 'react'

/**
 * Records camera + microphone only. The movie audio goes to the headphones and
 * is never captured, so it can't bleed into the voice judge's input.
 *
 * The reference video and this recording start together and run the same
 * length, so second 14 of the take lines up with second 14 of the character's
 * performance -- no alignment step needed.
 *
 * The live stream is held in a ref as well as state, so close() always stops
 * the CURRENT tracks -- a cleanup captured before the camera opened would
 * otherwise see null and leave the camera light on. A newer open() stops the
 * stream it replaces (React's dev double-mount opens twice).
 */
export function useRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [recording, setRecording] = useState(false)

  const open = useCallback(async () => {
    const media = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720, facingMode: 'user' },
      audio: { echoCancellation: true, noiseSuppression: true },
    })
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = media
    setStream(media)
    return media
  }, [])

  const start = useCallback(async () => {
    const media = streamRef.current ?? (await open())
    chunksRef.current = []
    const recorder = new MediaRecorder(media, { mimeType: 'video/webm;codecs=vp8,opus' })
    recorder.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data)
    recorderRef.current = recorder
    recorder.start(250)
    setRecording(true)
  }, [open])

  const stop = useCallback(
    () =>
      new Promise<Blob>((resolve) => {
        const recorder = recorderRef.current
        if (!recorder || recorder.state === 'inactive') return resolve(new Blob())
        recorder.onstop = () => {
          setRecording(false)
          resolve(new Blob(chunksRef.current, { type: 'video/webm' }))
        }
        recorder.stop()
      }),
    [],
  )

  const close = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setStream(null)
  }, [])

  return { stream, recording, open, start, stop, close }
}
