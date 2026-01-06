import { describe, it, expect, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useQueryStore } from '../queryStore'

describe('queryStore', () => {
  beforeEach(() => {
    act(() => {
      useQueryStore.setState({ queryHistory: [], currentQuery: '' })
    })
  })

  it('has initial state', () => {
    const state = useQueryStore.getState()
    expect(state.queryHistory).toEqual([])
    expect(state.currentQuery).toBe('')
  })

  it('sets current query', () => {
    act(() => {
      useQueryStore.getState().setCurrentQuery('test query')
    })
    expect(useQueryStore.getState().currentQuery).toBe('test query')
  })

  it('adds to history', () => {
    const request = { question: 'test question' }
    const response = { answer: 'test answer', confidence: 0.9 }

    act(() => {
      useQueryStore.getState().addToHistory(request as any, response as any)
    })

    const history = useQueryStore.getState().queryHistory
    expect(history).toHaveLength(1)
    expect(history[0].request).toEqual(request)
    expect(history[0].response).toEqual(response)
    expect(history[0].id).toBeDefined()
    expect(history[0].timestamp).toBeDefined()
  })

  it('limits history to 50 items', () => {
    act(() => {
      for (let i = 0; i < 55; i++) {
        useQueryStore.getState().addToHistory(
          { question: `q${i}` } as any,
          { answer: `a${i}` } as any
        )
      }
    })

    expect(useQueryStore.getState().queryHistory).toHaveLength(50)
  })

  it('clears history', () => {
    act(() => {
      useQueryStore.getState().addToHistory(
        { question: 'test' } as any,
        { answer: 'test' } as any
      )
      useQueryStore.getState().clearHistory()
    })

    expect(useQueryStore.getState().queryHistory).toEqual([])
  })

  it('prepends new items to history', () => {
    act(() => {
      useQueryStore.getState().addToHistory({ question: 'first' } as any, {} as any)
      useQueryStore.getState().addToHistory({ question: 'second' } as any, {} as any)
    })

    const history = useQueryStore.getState().queryHistory
    expect(history[0].request.question).toBe('second')
    expect(history[1].request.question).toBe('first')
  })
})
