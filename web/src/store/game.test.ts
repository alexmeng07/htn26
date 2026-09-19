import { beforeEach, describe, expect, it } from 'vitest'
import { useGame } from './game'

const reset = () =>
  useGame.setState({ screen: 'title', nickname: '', roundId: null, attempt: 1, result: null })

describe('game store', () => {
  beforeEach(reset)

  it('starts on the title screen', () => {
    expect(useGame.getState().screen).toBe('title')
  })

  it('moves between screens', () => {
    useGame.getState().go('briefing')
    expect(useGame.getState().screen).toBe('briefing')
  })

  it('keeps the nickname across retries and bumps the attempt', () => {
    const { setNickname, retry } = useGame.getState()
    setNickname('alex')
    retry()
    const state = useGame.getState()
    expect(state.nickname).toBe('alex')
    expect(state.attempt).toBe(2)
    expect(state.screen).toBe('ready')
  })

  it('clears the previous result when retrying', () => {
    useGame.setState({ result: { passed: false } as never })
    useGame.getState().retry()
    expect(useGame.getState().result).toBeNull()
  })
})
