import { renderHook, act } from '@testing-library/react'

import { useSpectrumEditor } from '@/features/video/workspace/useSpectrumEditor'

describe('useSpectrumEditor color patch compatibility', () => {
  it('mirrors color-engine edits into both nested and legacy layer fields', () => {
    const setSpectrumLayersLive = vi.fn()

    const { result } = renderHook(() =>
      useSpectrumEditor({
        templateDraft: { style: 'straight-bars' } as never,
        currentTemplate: {},
        editableSpectrumLayers: [
          {
            name: 'Layer 1',
            color: {
              mode: 'gradient',
              gradientColors: ['#ffffff', '#22d3ee'],
              gradientDirection: 'left-to-right',
            },
          },
        ],
        selectedLayerIndex: 0,
        setTemplateDraft: vi.fn(),
        setSpectrumLayersLive,
        setSelectedLayerKey: vi.fn(),
        emitStatus: vi.fn(),
      }),
    )

    act(() => {
      result.current.patchSelectedLayerColor({
        gradientColors: ['#ff8800', '#ff0000'],
        gradientDirection: 'diagonal',
      })
    })

    expect(setSpectrumLayersLive).toHaveBeenCalledWith([
      expect.objectContaining({
        gradientColors: ['#ff8800', '#ff0000'],
        gradientDirection: 'diagonal',
        color: expect.objectContaining({
          gradientColors: ['#ff8800', '#ff0000'],
          gradientDirection: 'diagonal',
        }),
      }),
    ])
  })
})
